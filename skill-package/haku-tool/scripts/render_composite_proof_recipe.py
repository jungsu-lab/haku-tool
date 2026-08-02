from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from licensed_audio import mux_licensed_audio, prepare_licensed_audio, report_audio
from temporal_continuity_qc import attach_temporal_continuity_qc


GRADES = {
    "haku-lupine": (
        "eq=contrast=0.95:brightness=-0.004:saturation=0.78:gamma=1.02,"
        "colorbalance=rs=0.008:gs=0.002:bs=-0.006:"
        "rm=0.010:gm=0.002:bm=-0.008:"
        "rh=0.016:gh=0.004:bh=-0.012,"
        "curves=master='0/0.026 0.18/0.205 0.50/0.51 0.78/0.785 1/0.950'"
    ),
    "haku-memory": (
        "eq=contrast=0.94:brightness=0.004:saturation=0.60:gamma=1.025,"
        "colorbalance=rs=0.014:gs=0.004:bs=-0.012:"
        "rm=0.012:gm=0.003:bm=-0.010:"
        "rh=0.020:gh=0.006:bh=-0.016,"
        "curves=master='0/0.030 0.18/0.205 0.50/0.52 0.78/0.79 1/0.955'"
    ),
    "haku-neutral": (
        "eq=contrast=0.99:brightness=0.002:saturation=0.80:gamma=1.015,"
        "colorbalance=rs=0.010:gs=0.002:bs=-0.006:"
        "rh=0.010:gh=0.002:bh=-0.008,"
        "curves=master='0/0.024 0.18/0.20 0.75/0.77 1/0.965'"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render Haku cover, non-cover, panel, trace, and copy proof recipes."
    )
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path)
    parser.add_argument("--ffprobe", type=Path)
    return parser.parse_args()


def resolve_binary(explicit: Path | None, name: str) -> Path:
    if explicit:
        value = explicit.resolve()
        if value.is_file():
            return value
        raise FileNotFoundError(value)
    found = shutil.which(name)
    if found:
        return Path(found)
    raise FileNotFoundError(f"{name} not found")


def run(command: list[str], timeout: int = 900) -> str:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env={**os.environ, "OMP_NUM_THREADS": "2"},
    )
    if completed.returncode:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(command)
            + "\n"
            + (completed.stderr or completed.stdout)
        )
    return completed.stdout


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def probe(ffprobe: Path, path: Path) -> dict[str, Any]:
    payload = run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-count_frames",
            "-show_entries",
            "stream=width,height,r_frame_rate,nb_read_frames:format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    return json.loads(payload)


def resolve_source(recipe_path: Path, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (recipe_path.parent / path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def material_ids(segment: dict[str, Any]) -> set[str]:
    kind = segment["type"]
    if kind in {"single", "fit-single", "copy-overlay"}:
        return {segment["material"]}
    if kind == "triptych":
        return {panel["material"] for panel in segment["panels"]}
    if kind == "bounded-video-trace":
        return {segment["background"], segment["trace"]}
    if kind == "luminous-reflection-relay":
        return {segment["background"], segment["reflection"]}
    if kind == "memory-window-reveal":
        return {
            segment["background"],
            *(window["material"] for window in segment["windows"]),
        }
    if kind == "functional-panels":
        return {panel["material"] for panel in segment["panels"]}
    raise ValueError(f"Unsupported segment type: {kind}")


def validate(recipe_path: Path, recipe: dict[str, Any]) -> dict[str, Path]:
    if recipe.get("schema_version") != "1.1":
        raise ValueError("schema_version must be 1.1")
    if recipe.get("audio_policy") not in {
        "deferred_by_user", "deferred_by_rights", "licensed_library_track"
    }:
        raise ValueError("unsupported audio_policy")
    policy = recipe["render_policy"]
    if int(policy["max_threads"]) not in (1, 2):
        raise ValueError("max_threads must be 1 or 2")
    if policy.get("motion_policy") != "source-motion-only":
        raise ValueError("motion_policy must be source-motion-only")
    forbidden = {
        "freeze",
        "retime",
        "reverse",
        "animated_crop",
        "animated_scale",
        "last_frame_padding",
    }
    if not forbidden.issubset(set(policy.get("forbid", []))):
        raise ValueError("render_policy.forbid is incomplete")
    if recipe.get("audio_policy") == "licensed_library_track" and "music" in set(policy.get("forbid", [])):
        raise ValueError("licensed_library_track conflicts with render_policy.forbid=music")

    canvas = recipe["canvas"]
    if int(canvas["fps"]) <= 0 or int(canvas["width"]) <= 0 or int(canvas["height"]) <= 0:
        raise ValueError("invalid canvas")
    width = int(canvas["width"])
    height = int(canvas["height"])

    materials: dict[str, Path] = {}
    for material_id, item in recipe["materials"].items():
        forbidden_fields = {"rate", "reverse", "hold", "zoom", "crop_start", "crop_end"}
        if forbidden_fields.intersection(item):
            raise ValueError(f"{material_id} contains forbidden motion fields")
        if float(item.get("source_in", 0)) < 0:
            raise ValueError(f"{material_id} has negative source_in")
        if item.get("grade", "haku-neutral") not in GRADES:
            raise ValueError(f"{material_id} has unknown grade")
        materials[material_id] = resolve_source(recipe_path, item["source"])

    totals: dict[str, int] = {}
    sets: dict[str, set[str]] = {}
    for variant_name in ("plain", "proof"):
        segments = recipe["variants"][variant_name]["segments"]
        if not segments:
            raise ValueError(f"{variant_name} has no segments")
        totals[variant_name] = 0
        sets[variant_name] = set()
        seen: set[str] = set()
        for segment in segments:
            if segment["id"] in seen:
                raise ValueError(f"duplicate segment id: {segment['id']}")
            seen.add(segment["id"])
            frames = int(segment["frames"])
            if frames <= 0:
                raise ValueError(f"{segment['id']} has invalid frames")
            if (
                segment["type"] in {"single", "fit-single", "copy-overlay"}
                and "source_in" in segment
                and float(segment["source_in"]) < 0
            ):
                raise ValueError(f"{segment['id']} has negative source_in")
            totals[variant_name] += frames
            ids = material_ids(segment)
            if not ids.issubset(materials):
                raise ValueError(f"{segment['id']} references unknown materials")
            sets[variant_name].update(ids)
            if segment["type"] == "triptych":
                panels = segment["panels"]
                if len(panels) != 3:
                    raise ValueError("triptych must contain exactly three panels")
                if len({item["id"] for item in panels}) != 3:
                    raise ValueError("triptych panel ids must be unique")
            if segment["type"] == "bounded-video-trace":
                start, end = segment["active_frames"]
                if not (0 <= int(start) < int(end) <= frames):
                    raise ValueError("trace active_frames outside segment")
                opacity = float(segment.get("opacity", 0.18))
                if not 0 < opacity <= 0.35:
                    raise ValueError("trace opacity must be >0 and <=0.35")
            if segment["type"] == "luminous-reflection-relay":
                if segment.get("blend_mode") != "screen":
                    raise ValueError("luminous-reflection-relay requires blend_mode=screen")
                opacity = float(segment.get("opacity", 0.28))
                if not 0.12 <= opacity <= 0.42:
                    raise ValueError(
                        "luminous-reflection-relay opacity must be between 0.12 and 0.42"
                    )
                relation = segment.get("reflection_relation")
                if not isinstance(relation, dict):
                    raise ValueError("luminous-reflection-relay requires reflection_relation evidence")
                required_relation_fields = ("base_reflection_visible", "physical_surface", "action_trigger", "light_relation", "release_reason")
                missing_relation_fields = [field for field in required_relation_fields if field not in relation]
                if missing_relation_fields:
                    raise ValueError("luminous-reflection-relay reflection_relation missing: " + ", ".join(missing_relation_fields))
                if relation["base_reflection_visible"] is not True:
                    raise ValueError("luminous-reflection-relay requires a visible base-shot reflection")
                if relation["physical_surface"] not in {"glass", "water", "mirror", "metal", "other_reflective_surface"}:
                    raise ValueError("luminous-reflection-relay physical_surface must name a reflective surface")
                for field in ("action_trigger", "light_relation", "release_reason"):
                    if not isinstance(relation[field], str) or not relation[field].strip():
                        raise ValueError("luminous-reflection-relay " + field + " must be non-empty")
                fade_in = float(segment.get("fade_in_seconds", 0.35))
                fade_out = float(segment.get("fade_out_seconds", 0.35))
                if not 0.20 <= fade_in <= 1.00 or not 0.20 <= fade_out <= 1.00:
                    raise ValueError("luminous-reflection-relay fade_in_seconds and fade_out_seconds must each be between 0.20 and 1.00")
                if fade_in + fade_out >= frames / int(canvas["fps"]):
                    raise ValueError("luminous-reflection-relay fades leave no held reflection interval")
            if segment["type"] == "memory-window-reveal":
                windows = segment["windows"]
                if not 1 <= len(windows) <= 3:
                    raise ValueError("memory-window-reveal requires 1 to 3 windows")
                if len({item["id"] for item in windows}) != len(windows):
                    raise ValueError("memory window ids must be unique")
                for window in windows:
                    start, end = [int(value) for value in window["active_frames"]]
                    if not (0 <= start < end <= frames):
                        raise ValueError("window active_frames outside segment")
                    rect = [float(value) for value in window["rect"]]
                    if len(rect) != 4:
                        raise ValueError("window rect must be [x,y,w,h]")
                    x, y, w, h = rect
                    if not (
                        0 <= x < 1
                        and 0 <= y < 1
                        and 0 < w <= 1
                        and 0 < h <= 1
                        and x + w <= 1
                        and y + h <= 1
                    ):
                        raise ValueError("window rect must fit normalized canvas")
                    fade = int(window.get("fade_in_frames", 4))
                    if not 0 <= fade <= end - start:
                        raise ValueError("fade_in_frames outside window duration")
            if segment["type"] == "functional-panels":
                panels = segment["panels"]
                if not 2 <= len(panels) <= 4:
                    raise ValueError("functional-panels requires 2 to 4 panels")
                if len({item["id"] for item in panels}) != len(panels):
                    raise ValueError("functional panel ids must be unique")
                common_anchor = str(segment.get("common_anchor", "")).strip()
                if not common_anchor:
                    raise ValueError("functional-panels requires a non-empty common_anchor")
                roles = [str(panel.get("role", "")).strip() for panel in panels]
                if not all(roles):
                    raise ValueError("each functional panel requires a non-empty role")
                if len(set(roles)) != len(roles):
                    raise ValueError("functional panel roles must be distinct")
                panel_ranges: list[tuple[int, int]] = []
                for panel in panels:
                    rect = [float(value) for value in panel["rect"]]
                    if len(rect) != 4:
                        raise ValueError("functional panel rect must be [x,y,w,h]")
                    x, y, w, h = rect
                    if not (
                        0 <= x < 1
                        and 0 <= y < 1
                        and 0 < w <= 1
                        and 0 < h <= 1
                        and x + w <= 1
                        and y + h <= 1
                    ):
                        raise ValueError("functional panel rect must fit normalized canvas")
                    start, end = [
                        int(value) for value in panel.get("active_frames", [0, frames])
                    ]
                    if not (0 <= start < end <= frames):
                        raise ValueError("functional panel active_frames outside segment")
                    span = end - start
                    if span < 6:
                        raise ValueError("functional panel needs at least 6 active frames")
                    default_fade = min(6, max(2, span // 3))
                    fade_in = int(panel.get("fade_in_frames", default_fade))
                    fade_out = int(panel.get("fade_out_frames", default_fade))
                    if not (2 <= fade_in and 2 <= fade_out and fade_in + fade_out < span):
                        raise ValueError("functional panel fades must leave a visible hold")
                    panel_ranges.append((start, end))
                if not any(start > 0 for start, _end in panel_ranges):
                    raise ValueError("functional-panels requires at least one sequential panel entry")
                black_breath = segment.get("intentional_black_breath_frames")
                if black_breath is not None:
                    breath_start, breath_end = [int(value) for value in black_breath]
                    max_breath = int(round(int(canvas["fps"]) * 1.5))
                    if not (
                        0 <= breath_start < breath_end == frames
                        and breath_end - breath_start <= max_breath
                    ):
                        raise ValueError(
                            "intentional_black_breath_frames must be a final 1.5s-or-shorter interval"
                        )
                    if any(end > breath_start for _start, end in panel_ranges):
                        raise ValueError(
                            "intentional black breath must begin after every functional panel ends"
                        )
            if segment["type"] == "copy-overlay":
                copies = segment.get("copies", [])
                if not 1 <= len(copies) <= 3:
                    raise ValueError("copy-overlay requires 1 to 3 copy entries")
                for copy in copies:
                    text = str(copy.get("text", "")).strip()
                    if not text or len(text) > 80:
                        raise ValueError("copy text must contain 1 to 80 characters")
                    if any(character in text for character in "\r\n"):
                        raise ValueError("copy text must be a single line")
                    start, end = [int(value) for value in copy["active_frames"]]
                    if not (0 <= start < end <= frames):
                        raise ValueError("copy active_frames outside segment")
                    x = float(copy.get("x", 0.08))
                    y = float(copy.get("y", 0.82))
                    if not (0 <= x <= 1 and 0 <= y <= 1):
                        raise ValueError("copy x/y must be normalized")
                    font_size = int(copy.get("font_size", max(24, height // 28)))
                    if not 12 <= font_size <= max(width, height) // 5:
                        raise ValueError("copy font_size outside safe range")
                    if copy.get("font", "sans") not in {"sans", "serif"}:
                        raise ValueError("copy font must be sans or serif")
                    if copy.get("font_weight", "bold") not in {"normal", "bold"}:
                        raise ValueError("copy font_weight must be normal or bold")
                    shadow_opacity = float(copy.get("shadow_opacity", 0.65))
                    shadow_x = int(copy.get("shadow_x", 2))
                    shadow_y = int(copy.get("shadow_y", 2))
                    if not 0 <= shadow_opacity <= 0.9:
                        raise ValueError(
                            "copy shadow_opacity must be between 0 and 0.9"
                        )
                    if not (0 <= shadow_x <= 8 and 0 <= shadow_y <= 8):
                        raise ValueError("copy shadow offsets must be between 0 and 8")
            if segment["type"] == "fit-single":
                canvas_color = str(segment.get("canvas_color", "0x080808"))
                if not (
                    len(canvas_color) == 8
                    and canvas_color.startswith("0x")
                    and all(
                        character in "0123456789abcdefABCDEF"
                        for character in canvas_color[2:]
                    )
                ):
                    raise ValueError("fit-single canvas_color must be 0xRRGGBB")
    if totals["plain"] != totals["proof"]:
        raise ValueError("plain/proof frame totals differ")
    if sets["plain"] != sets["proof"]:
        raise ValueError(
            f"plain/proof material sets differ: {sets['plain']} vs {sets['proof']}"
        )
    return materials


def variant_usage_ledger(
    recipe: dict[str, Any], variant_name: str
) -> dict[str, Any]:
    fps = int(recipe["canvas"]["fps"])
    timeline_frame = 0
    occurrences: list[dict[str, Any]] = []
    for segment in recipe["variants"][variant_name]["segments"]:
        frames = int(segment["frames"])
        kind = segment["type"]

        def append_occurrence(
            material_id: str,
            role: str,
            used_frames: int,
            visible_start: int,
            visible_end: int,
            source_in_override: float | None = None,
        ) -> None:
            source_in = (
                float(recipe["materials"][material_id].get("source_in", 0))
                if source_in_override is None
                else float(source_in_override)
            )
            occurrences.append(
                {
                    "segment_id": segment["id"],
                    "segment_type": kind,
                    "role": role,
                    "material_id": material_id,
                    "source_in_seconds": source_in,
                    "source_out_seconds": source_in + used_frames / fps,
                    "duration_frames": used_frames,
                    "timeline_visible_frames": [
                        timeline_frame + visible_start,
                        timeline_frame + visible_end,
                    ],
                }
            )

        if kind in {"single", "fit-single", "copy-overlay"}:
            role = "full_frame_fit" if kind == "fit-single" else "full_frame"
            append_occurrence(
                segment["material"],
                role,
                frames,
                0,
                frames,
                segment.get("source_in"),
            )
        elif kind == "triptych":
            for panel in segment["panels"]:
                append_occurrence(panel["material"], panel["id"], frames, 0, frames)
        elif kind == "bounded-video-trace":
            append_occurrence(segment["background"], "background", frames, 0, frames)
            start, end = [int(value) for value in segment["active_frames"]]
            append_occurrence(segment["trace"], "trace", frames, start, end)
        elif kind == "luminous-reflection-relay":
            append_occurrence(segment["background"], "background", frames, 0, frames)
            append_occurrence(segment["reflection"], "screen_reflection", frames, 0, frames)
        elif kind == "memory-window-reveal":
            append_occurrence(segment["background"], "background", frames, 0, frames)
            for window in segment["windows"]:
                start, end = [int(value) for value in window["active_frames"]]
                append_occurrence(
                    window["material"], window["id"], end - start, start, end
                )
        elif kind == "functional-panels":
            for panel in segment["panels"]:
                start, end = [
                    int(value)
                    for value in panel.get("active_frames", [0, frames])
                ]
                append_occurrence(
                    panel["material"], panel["id"], end - start, start, end
                )
        timeline_frame += frames

    counts: dict[str, int] = {}
    for item in occurrences:
        material_id = item["material_id"]
        counts[material_id] = counts.get(material_id, 0) + 1
    return {"occurrences": occurrences, "usage_count_by_material": counts}


def crop_filter(width: int, height: int, focus_x: float, focus_y: float) -> str:
    aspect = width / height
    crop_w = f"floor(min(iw,ih*{aspect:.10f})/2)*2"
    crop_h = f"floor(min(ih,iw/{aspect:.10f})/2)*2"
    crop_x = f"max(0,min(iw-out_w,iw*{focus_x:.6f}-out_w/2))"
    crop_y = f"max(0,min(ih-out_h,ih*{focus_y:.6f}-out_h/2))"
    return (
        f"crop=w='{crop_w}':h='{crop_h}':x='{crop_x}':y='{crop_y}',"
        f"scale={width}:{height}:flags=lanczos"
    )


def source_chain(
    item: dict[str, Any],
    frames: int,
    fps: int,
    width: int,
    height: int,
    label: str,
) -> str:
    return (
        f"trim=start={float(item.get('source_in', 0)):.6f}:"
        f"duration={(frames / fps):.6f},"
        "setpts=PTS-STARTPTS,"
        f"fps={fps},trim=end_frame={frames},"
        f"settb=1/{fps},setpts=N/({fps}*TB),"
        + crop_filter(
            width,
            height,
            float(item.get("focus_x", 0.5)),
            float(item.get("focus_y", 0.5)),
        )
        + ","
        + GRADES[item.get("grade", "haku-neutral")]
        + f",format=yuv420p[{label}]"
    )


def fit_source_chain(
    item: dict[str, Any],
    frames: int,
    fps: int,
    width: int,
    height: int,
    canvas_color: str,
    label: str,
) -> str:
    return (
        f"trim=start={float(item.get('source_in', 0)):.6f}:"
        f"duration={(frames / fps):.6f},"
        "setpts=PTS-STARTPTS,"
        f"fps={fps},trim=end_frame={frames},"
        f"settb=1/{fps},setpts=N/({fps}*TB),"
        + GRADES[item.get("grade", "haku-neutral")]
        + ","
        + f"scale={width}:{height}:flags=lanczos:"
        "force_original_aspect_ratio=decrease,"
        + f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={canvas_color},"
        + f"format=yuv420p[{label}]"
    )


def escape_drawtext(value: str) -> str:
    return (
        value.replace("\\", r"\\")
        .replace(":", r"\:")
        .replace("'", r"\'")
        .replace("%", r"\%")
    )


def window_chain(
    item: dict[str, Any],
    duration_frames: int,
    start_frame: int,
    fade_in_frames: int,
    fps: int,
    width: int,
    height: int,
    border: int,
    label: str,
) -> str:
    inner_width = max(2, width - border * 2)
    inner_height = max(2, height - border * 2)
    fade = (
        f",fade=t=in:st=0:d={fade_in_frames / fps:.6f}:alpha=1"
        if fade_in_frames
        else ""
    )
    return (
        f"trim=start={float(item.get('source_in', 0)):.6f}:"
        f"duration={duration_frames / fps:.6f},"
        "setpts=PTS-STARTPTS,"
        f"fps={fps},trim=end_frame={duration_frames},"
        f"settb=1/{fps},setpts=N/({fps}*TB),"
        + crop_filter(
            inner_width,
            inner_height,
            float(item.get("focus_x", 0.5)),
            float(item.get("focus_y", 0.5)),
        )
        + ","
        + GRADES[item.get("grade", "haku-neutral")]
        + f",pad={width}:{height}:{border}:{border}:color=0xf3eee4,"
        + "format=rgba"
        + fade
        + f",setpts=PTS+{start_frame}/({fps}*TB)[{label}]"
    )


def functional_panel_chain(
    item: dict[str, Any],
    duration_frames: int,
    start_frame: int,
    fade_in_frames: int,
    fade_out_frames: int,
    fps: int,
    width: int,
    height: int,
    label: str,
) -> str:
    """Start source time at panel entry, then place the faded panel on the timeline."""
    fade_out_start = (duration_frames - fade_out_frames) / fps
    return (
        f"trim=start={float(item.get('source_in', 0)):.6f}:"
        f"duration={duration_frames / fps:.6f},"
        "setpts=PTS-STARTPTS,"
        f"fps={fps},trim=end_frame={duration_frames},"
        f"settb=1/{fps},setpts=N/({fps}*TB),"
        + crop_filter(
            width,
            height,
            float(item.get("focus_x", 0.5)),
            float(item.get("focus_y", 0.5)),
        )
        + ","
        + GRADES[item.get("grade", "haku-neutral")]
        + ",format=rgba,"
        + f"fade=t=in:st=0:d={fade_in_frames / fps:.6f}:alpha=1,"
        + f"fade=t=out:st={fade_out_start:.6f}:d={fade_out_frames / fps:.6f}:alpha=1,"
        + f"setpts=PTS+{start_frame}/({fps}*TB)[{label}]"
    )


def render_segment(
    ffmpeg: Path,
    recipe: dict[str, Any],
    materials: dict[str, Path],
    segment: dict[str, Any],
    target: Path,
) -> dict[str, Any]:
    canvas = recipe["canvas"]
    fps = int(canvas["fps"])
    width = int(canvas["width"])
    height = int(canvas["height"])
    frames = int(segment["frames"])
    kind = segment["type"]
    commands = [str(ffmpeg), "-hide_banner", "-nostdin", "-y"]
    filters: list[str] = []

    if kind == "single":
        material_id = segment["material"]
        commands.extend(["-i", str(materials[material_id])])
        item = {**recipe["materials"][material_id]}
        if "source_in" in segment:
            item["source_in"] = float(segment["source_in"])
        filters.append(source_chain(item, frames, fps, width, height, "outv"))

    elif kind == "fit-single":
        material_id = segment["material"]
        commands.extend(["-i", str(materials[material_id])])
        item = {**recipe["materials"][material_id]}
        if "source_in" in segment:
            item["source_in"] = float(segment["source_in"])
        filters.append(
            fit_source_chain(
                item,
                frames,
                fps,
                width,
                height,
                str(segment.get("canvas_color", "0x080808")),
                "outv",
            )
        )

    elif kind == "copy-overlay":
        material_id = segment["material"]
        commands.extend(["-i", str(materials[material_id])])
        item = {**recipe["materials"][material_id]}
        if "source_in" in segment:
            item["source_in"] = float(segment["source_in"])
        filters.append(source_chain(item, frames, fps, width, height, "copybase"))
        current = "copybase"
        copies = segment["copies"]
        for index, copy in enumerate(copies):
            start, end = [int(value) for value in copy["active_frames"]]
            font_size = int(copy.get("font_size", max(24, height // 28)))
            x = int(float(copy.get("x", 0.08)) * width)
            y = int(float(copy.get("y", 0.82)) * height)
            font_color = copy.get("font_color", "0xf4efe6")
            box_color = copy.get("box_color", "0x080808")
            box_opacity = float(copy.get("box_opacity", 0.56))
            if not 0 <= box_opacity <= 0.9:
                raise ValueError("copy box_opacity must be between 0 and 0.9")
            font_family = copy.get("font", "sans")
            font_weight = copy.get("font_weight", "bold")
            font_file = {
                ("serif", "normal"): "C\\:/Windows/Fonts/times.ttf",
                ("serif", "bold"): "C\\:/Windows/Fonts/timesbd.ttf",
                ("sans", "normal"): "C\\:/Windows/Fonts/arial.ttf",
                ("sans", "bold"): "C\\:/Windows/Fonts/arialbd.ttf",
            }[(font_family, font_weight)]
            shadow_opacity = float(copy.get("shadow_opacity", 0.65))
            shadow_x = int(copy.get("shadow_x", 2))
            shadow_y = int(copy.get("shadow_y", 2))
            output_label = "outv" if index == len(copies) - 1 else f"copy{index}"
            text = escape_drawtext(str(copy["text"]).strip())
            filters.append(
                f"[{current}]drawtext="
                f"fontfile='{font_file}':"
                f"text='{text}':x={x}:y={y}:fontsize={font_size}:"
                f"fontcolor={font_color}:box=1:boxcolor={box_color}@{box_opacity:.3f}:"
                f"boxborderw={max(8, font_size // 3)}:"
                f"shadowcolor=black@{shadow_opacity:.3f}:"
                f"shadowx={shadow_x}:shadowy={shadow_y}:"
                f"enable='between(n,{start},{end - 1})',"
                f"format=yuv420p[{output_label}]"
            )
            current = output_label

    elif kind == "triptych":
        panel_height = height // 3
        panel_heights = [panel_height, panel_height, height - panel_height * 2]
        labels: list[str] = []
        for index, panel in enumerate(segment["panels"]):
            material_id = panel["material"]
            commands.extend(["-i", str(materials[material_id])])
            item = recipe["materials"][material_id]
            label = f"p{index}"
            filters.append(
                f"[{index}:v]"
                + source_chain(
                    item,
                    frames,
                    fps,
                    width,
                    panel_heights[index],
                    label,
                )
            )
            labels.append(f"[{label}]")
        filters.append("".join(labels) + "vstack=inputs=3,format=yuv420p[outv]")

    elif kind == "bounded-video-trace":
        bg_id = segment["background"]
        trace_id = segment["trace"]
        commands.extend(["-i", str(materials[bg_id]), "-i", str(materials[trace_id])])
        filters.append(
            "[0:v]"
            + source_chain(
                recipe["materials"][bg_id], frames, fps, width, height, "bg"
            )
        )
        filters.append(
            "[1:v]"
            + source_chain(
                recipe["materials"][trace_id], frames, fps, width, height, "trace0"
            )
        )
        start, end = [int(value) for value in segment["active_frames"]]
        opacity = float(segment.get("opacity", 0.18))
        fade_frames = max(1, int(segment.get("fade_out_frames", max(1, end - start))))
        fade_start = max(start, end - fade_frames) / fps
        fade_duration = max(1, end - max(start, end - fade_frames)) / fps
        filters.append(
            "[trace0]format=rgba,"
            f"colorchannelmixer=aa={opacity:.6f},"
            f"fade=t=out:st={fade_start:.6f}:d={fade_duration:.6f}:alpha=1"
            "[trace]"
        )
        filters.append(
            "[bg][trace]overlay=x=0:y=0:"
            f"enable='between(n,{start},{end - 1})',format=yuv420p[outv]"
        )
    elif kind == "luminous-reflection-relay":
        bg_id = segment["background"]
        reflection_id = segment["reflection"]
        fade_in = float(segment.get("fade_in_seconds", 0.35))
        fade_out = float(segment.get("fade_out_seconds", 0.35))
        duration_seconds = frames / fps
        opacity = float(segment.get("opacity", 0.28))
        envelope = f"min(1\\,T/{fade_in:.6f})*min(1\\,({duration_seconds:.6f}-T)/{fade_out:.6f})"
        effective_opacity = f"({opacity:.6f}*{envelope})"
        screen_expression = f"A*(1-{effective_opacity})+(255-(255-A)*(255-B)/255)*{effective_opacity}"
        commands.extend(["-i", str(materials[bg_id]), "-i", str(materials[reflection_id])])
        filters.append(
            "[0:v]"
            + source_chain(
                recipe["materials"][bg_id], frames, fps, width, height, "bg"
            )
        )
        filters.append(
            "[1:v]"
            + source_chain(
                recipe["materials"][reflection_id], frames, fps, width, height, "reflection"
            )
        )
        filters.append(
            "[bg][reflection]blend=all_expr='" + screen_expression + "':shortest=1,"
            "format=yuv420p[outv]"
        )
    elif kind == "memory-window-reveal":
        bg_id = segment["background"]
        commands.extend(["-i", str(materials[bg_id])])
        filters.append(
            "[0:v]"
            + source_chain(
                recipe["materials"][bg_id], frames, fps, width, height, "bg"
            )
        )
        current = "bg"
        for index, window in enumerate(segment["windows"], 1):
            material_id = window["material"]
            commands.extend(["-i", str(materials[material_id])])
            start, end = [int(value) for value in window["active_frames"]]
            x, y, w, h = [float(value) for value in window["rect"]]
            window_width = max(4, int(width * w) // 2 * 2)
            window_height = max(4, int(height * h) // 2 * 2)
            window_x = int(width * x)
            window_y = int(height * y)
            window_label = f"window{index}"
            filters.append(
                f"[{index}:v]"
                + window_chain(
                    recipe["materials"][material_id],
                    end - start,
                    start,
                    int(window.get("fade_in_frames", 4)),
                    fps,
                    window_width,
                    window_height,
                    int(window.get("border", 6)),
                    window_label,
                )
            )
            output_label = "outv" if index == len(segment["windows"]) else f"mix{index}"
            tail = ",format=yuv420p" if output_label == "outv" else ""
            filters.append(
                f"[{current}][{window_label}]overlay=x={window_x}:y={window_y}:"
                f"eof_action=pass:enable='between(n,{start},{end - 1})'"
                f"{tail}[{output_label}]"
            )
            current = output_label
    elif kind == "functional-panels":
        color = segment.get("canvas_color", "0x080808")
        filters.append(
            f"color=c={color}:s={width}x{height}:r={fps}:d={frames / fps:.6f},"
            f"trim=end_frame={frames},settb=1/{fps},setpts=N/({fps}*TB),"
            "format=yuv420p[panelcanvas]"
        )
        current = "panelcanvas"
        for index, panel in enumerate(segment["panels"]):
            material_id = panel["material"]
            commands.extend(["-i", str(materials[material_id])])
            x, y, w, h = [float(value) for value in panel["rect"]]
            panel_width = max(4, int(width * w) // 2 * 2)
            panel_height = max(4, int(height * h) // 2 * 2)
            panel_x = int(width * x)
            panel_y = int(height * y)
            panel_label = f"functional{index}"
            start, end = [
                int(value) for value in panel.get("active_frames", [0, frames])
            ]
            span = end - start
            default_fade = min(6, max(2, span // 3))
            fade_in = int(panel.get("fade_in_frames", default_fade))
            fade_out = int(panel.get("fade_out_frames", default_fade))
            filters.append(
                f"[{index}:v]"
                + functional_panel_chain(
                    recipe["materials"][material_id],
                    span,
                    start,
                    fade_in,
                    fade_out,
                    fps,
                    panel_width,
                    panel_height,
                    panel_label,
                )
            )
            output_label = (
                "outv" if index == len(segment["panels"]) - 1 else f"panelmix{index}"
            )
            tail = ",format=yuv420p" if output_label == "outv" else ""
            filters.append(
                f"[{current}][{panel_label}]overlay=x={panel_x}:y={panel_y}:"
                f"eof_action=pass:enable='between(n,{start},{end - 1})'"
                f"{tail}[{output_label}]"
            )
            current = output_label
    else:
        raise ValueError(kind)

    target.parent.mkdir(parents=True, exist_ok=True)
    commands.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-an",
            "-frames:v",
            str(frames),
            "-c:v",
            "libx264",
            "-preset",
            recipe["render_policy"].get("preset", "medium"),
            "-crf",
            str(recipe["render_policy"].get("crf", 17)),
            "-threads",
            str(recipe["render_policy"]["max_threads"]),
            "-filter_threads",
            str(recipe["render_policy"]["max_threads"]),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(target),
        ]
    )
    run(commands)
    report = {
        "segment_id": segment["id"],
        "type": kind,
        "frames": frames,
        "materials": sorted(material_ids(segment)),
        "path": str(target),
    }
    if "intentional_black_breath_frames" in segment:
        report["intentional_black_breath_frames"] = [
            int(value) for value in segment["intentional_black_breath_frames"]
        ]
    return report


def render_variant(
    ffmpeg: Path,
    ffprobe: Path,
    recipe: dict[str, Any],
    materials: dict[str, Path],
    variant_name: str,
    work_dir: Path,
    output: Path,
) -> dict[str, Any]:
    segment_reports = []
    segment_paths = []
    for index, segment in enumerate(recipe["variants"][variant_name]["segments"], 1):
        path = work_dir / variant_name / f"{index:02d}-{segment['id']}.mp4"
        segment_reports.append(
            render_segment(ffmpeg, recipe, materials, segment, path)
        )
        segment_paths.append(path)

    concat_file = work_dir / variant_name / "concat.txt"
    concat_file.write_text(
        "".join(f"file '{path.as_posix()}'\n" for path in segment_paths),
        encoding="utf-8",
    )
    run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-nostdin",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    result = probe(ffprobe, output)
    expected = sum(item["frames"] for item in segment_reports)
    actual = int(result["streams"][0]["nb_read_frames"])
    if actual != expected:
        raise RuntimeError(f"{variant_name}: expected {expected} frames, got {actual}")
    return {
        "variant": variant_name,
        "path": str(output),
        "frames": actual,
        "duration_seconds": expected / int(recipe["canvas"]["fps"]),
        "segments": segment_reports,
        "probe": result,
    }


def render_comparison(
    ffmpeg: Path, plain: Path, proof: Path, output: Path, include_audio: bool
) -> None:
    command = [
            str(ffmpeg),
            "-hide_banner",
            "-nostdin",
            "-y",
            "-i",
            str(plain),
            "-i",
            str(proof),
            "-filter_complex",
            "[0:v]scale=540:960:flags=lanczos[p];"
            "[1:v]scale=540:960:flags=lanczos[q];"
            "[p][q]hstack=inputs=2,format=yuv420p[outv]",
            "-map",
            "[outv]",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "17",
            "-threads",
            "2",
            "-filter_threads",
            "2",
            "-movflags",
            "+faststart",
    ]
    if include_audio:
        command.extend(["-map", "0:a:0", "-c:a", "aac", "-b:a", "192k"])
    else:
        command.append("-an")
    command.append(str(output))
    run(command)


def render_storyboard(ffmpeg: Path, video: Path, output: Path) -> None:
    run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-nostdin",
            "-y",
            "-i",
            str(video),
            "-vf",
            "fps=2,scale=216:-2:flags=lanczos,"
            "drawtext=text='%{pts\\:hms}':x=8:y=h-th-8:"
            "fontsize=18:fontcolor=white:box=1:boxcolor=black@0.6,"
            "tile=5x8:padding=4:margin=4",
            "-frames:v",
            "1",
            "-threads",
            "2",
            str(output),
        ]
    )


def normalized_range_usage(ledger: dict[str, Any]) -> list[tuple[Any, ...]]:
    return sorted(
        (
            item["material_id"],
            float(item["source_in_seconds"]),
            float(item["source_out_seconds"]),
            int(item["duration_frames"]),
            tuple(int(value) for value in item["timeline_visible_frames"]),
        )
        for item in ledger["occurrences"]
    )


def validate_source_range_durations(
    recipe: dict[str, Any], source_durations: dict[str, float]
) -> None:
    fps = int(recipe["canvas"]["fps"])
    tolerance = 0.5 / fps
    for variant_name in ("plain", "proof"):
        ledger = variant_usage_ledger(recipe, variant_name)
        for occurrence in ledger["occurrences"]:
            material_id = occurrence["material_id"]
            if material_id not in source_durations:
                raise ValueError(f"missing probed duration for {material_id}")
            source_out = float(occurrence["source_out_seconds"])
            duration = float(source_durations[material_id])
            if source_out > duration + tolerance:
                raise ValueError(
                    f"{variant_name}:{occurrence['segment_id']} exceeds source "
                    f"duration for {material_id}: {source_out:.6f}s > "
                    f"{duration:.6f}s"
                )


def validate_source_ranges(
    ffprobe: Path,
    recipe: dict[str, Any],
    materials: dict[str, Path],
) -> dict[str, float]:
    durations = {
        material_id: float(probe(ffprobe, source)["format"]["duration"])
        for material_id, source in materials.items()
    }
    validate_source_range_durations(recipe, durations)
    return durations


def main() -> int:
    args = parse_args()
    recipe_path = args.recipe.resolve()
    output_dir = args.output_dir.resolve()
    ffmpeg = resolve_binary(args.ffmpeg, "ffmpeg")
    ffprobe = resolve_binary(args.ffprobe, "ffprobe")
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    materials = validate(recipe_path, recipe)
    validate_source_ranges(ffprobe, recipe, materials)

    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir = output_dir / "_segments"
    plain_path = output_dir / "plain.mp4"
    proof_path = output_dir / "proof.mp4"
    plain = render_variant(
        ffmpeg, ffprobe, recipe, materials, "plain", work_dir, plain_path
    )
    proof = render_variant(
        ffmpeg, ffprobe, recipe, materials, "proof", work_dir, proof_path
    )
    duration = float(plain["duration_seconds"])
    licensed_audio = prepare_licensed_audio(recipe_path, recipe, duration)
    if licensed_audio is not None:
        max_threads = int(recipe["render_policy"]["max_threads"])
        mux_licensed_audio(ffmpeg, plain_path, licensed_audio, run, max_threads)
        mux_licensed_audio(ffmpeg, proof_path, licensed_audio, run, max_threads)
    comparison = output_dir / "plain-vs-proof.mp4"
    render_comparison(
        ffmpeg, plain_path, proof_path, comparison,
        include_audio=licensed_audio is not None,
    )
    storyboards = output_dir / "storyboards"
    storyboards.mkdir(exist_ok=True)
    render_storyboard(ffmpeg, plain_path, storyboards / "plain.jpg")
    render_storyboard(ffmpeg, proof_path, storyboards / "proof.jpg")

    material_ledger = {}
    for material_id, source in materials.items():
        item = recipe["materials"][material_id]
        material_ledger[material_id] = {
            "source": str(source),
            "source_in": float(item.get("source_in", 0)),
            "sha256": sha256(source),
        }
    usage_ledgers = {
        name: variant_usage_ledger(recipe, name) for name in ("plain", "proof")
    }
    usage_range_equality = normalized_range_usage(
        usage_ledgers["plain"]
    ) == normalized_range_usage(usage_ledgers["proof"])

    report = {
        "schema_version": "1.1",
        "project_id": recipe["project_id"],
        "recipe": str(recipe_path),
        "recipe_sha256": sha256(recipe_path),
        "audio_policy": recipe["audio_policy"],
        "audio_render": report_audio(licensed_audio, recipe["audio_policy"]),
        "render_policy": recipe["render_policy"],
        "same_source_set_verified": {
            "passed": True,
            "material_ids": sorted(materials),
            "material_ledger": material_ledger,
        },
        "source_identity": {
            "same_material_id_set": True,
            "same_absolute_path_by_material_id": True,
            "same_file_hash_by_material_id": True,
            "same_source_anchor_by_material_id": True,
            "usage_range_equality": usage_range_equality,
            "note": (
                "Material identity and source anchors match. Exact occurrence, "
                "duration, and timeline usage are reported separately and are "
                "not implied by material-set equality."
            ),
        },
        "variant_usage_ledgers": usage_ledgers,
        "plain": {**plain, "sha256": sha256(plain_path)},
        "proof": {**proof, "sha256": sha256(proof_path)},
        "comparison": str(comparison),
        "storyboards": {
            "plain": str(storyboards / "plain.jpg"),
            "proof": str(storyboards / "proof.jpg"),
        },
        "visual_review": {
            "status": "pending_main_agent_review",
            "originals_reviewed": False,
            "plain_reviewed": False,
            "proof_reviewed": False,
            "internal_events_reviewed": False,
            "full_playback_reviewed": False,
        },
        "user_verdict": {
            "status": "pending",
            "allowed_values": ["accepted", "partial", "rejected"],
        },
    }
    report_path = output_dir / "render-report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    continuity = attach_temporal_continuity_qc(
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
        render_report=report_path,
    )
    if any(
        item["automated_verdict"]["status"] == "fail"
        for item in continuity.values()
    ):
        raise RuntimeError(
            "Temporal continuity gate failed; inspect render-report.json and evidence strips"
        )
    print(json.dumps({"success": True, "output": str(output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
