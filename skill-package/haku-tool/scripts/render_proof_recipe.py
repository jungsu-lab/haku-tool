from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from licensed_audio import mux_licensed_audio, prepare_licensed_audio, report_audio
from temporal_continuity_qc import attach_temporal_continuity_qc


GRADE_FILTERS = {
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
    "haku-green": (
        "eq=contrast=0.995:brightness=-0.002:saturation=0.76:gamma=1.015,"
        "colorbalance=rs=0.010:gs=0.006:bs=-0.010:"
        "rh=0.016:gh=0.004:bh=-0.014,"
        "curves=master='0/0.022 0.18/0.20 0.75/0.77 1/0.965'"
    ),
    "haku-sky": (
        "eq=contrast=0.97:brightness=0.006:saturation=0.68:gamma=1.025,"
        "colorbalance=rs=0.012:gs=0.002:bs=-0.010:"
        "rh=0.018:gh=0.004:bh=-0.012,"
        "curves=master='0/0.026 0.18/0.205 0.75/0.77 1/0.96'"
    ),
    "haku-warm": (
        "eq=contrast=0.97:brightness=0.006:saturation=0.68:gamma=1.025,"
        "colorbalance=rs=0.014:gs=0.003:bs=-0.012:"
        "rh=0.018:gh=0.004:bh=-0.012,"
        "curves=master='0/0.026 0.18/0.205 0.75/0.77 1/0.96'"
    ),
    "haku-cool": (
        "eq=contrast=0.97:brightness=0.008:saturation=0.68:gamma=1.03,"
        "colorbalance=rs=0.006:gs=0.004:bs=0.004:"
        "rh=0.012:gh=0.004:bh=-0.008,"
        "curves=master='0/0.028 0.18/0.205 0.75/0.77 1/0.96'"
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render same-source Haku plain/proof comparisons from a JSON recipe."
    )
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path)
    parser.add_argument("--ffprobe", type=Path)
    return parser.parse_args()


def resolve_binary(explicit: Path | None, name: str) -> Path:
    if explicit:
        result = explicit.resolve()
        if not result.is_file():
            raise FileNotFoundError(result)
        return result
    found = shutil.which(name)
    if found:
        return Path(found)
    raise FileNotFoundError(
        f"{name} was not found. Pass --{name} with an explicit executable path."
    )


def run(
    command: list[str],
    *,
    timeout: int = 600,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env={**os.environ, "OMP_NUM_THREADS": "2"},
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(command)
            + "\n"
            + (completed.stderr or completed.stdout or "")
        )
    return completed


def read_recipe(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("audio_policy") not in {
        "deferred_by_user", "deferred_by_rights", "licensed_library_track"
    }:
        raise ValueError("Unsupported audio_policy for proof rendering.")
    if set(payload.get("variants", {})) != {"plain", "proof"}:
        raise ValueError("Recipe must contain exactly plain and proof variants.")
    return payload


def resolve_source(recipe_path: Path, source: str) -> Path:
    result = Path(source)
    if not result.is_absolute():
        result = (recipe_path.parent / result).resolve()
    if not result.is_file():
        raise FileNotFoundError(result)
    return result


def validate_recipe(recipe_path: Path, recipe: dict[str, Any]) -> None:
    fps = int(recipe["canvas"]["fps"])
    if fps <= 0:
        raise ValueError("canvas.fps must be positive.")
    if int(recipe["render_policy"]["max_threads"]) > 2:
        raise ValueError("max_threads must not exceed 2.")

    source_sets: dict[str, set[str]] = {}
    for variant_name, variant in recipe["variants"].items():
        clips = variant.get("clips", [])
        if not clips:
            raise ValueError(f"{variant_name} has no clips.")
        source_sets[variant_name] = set()
        for clip in clips:
            source = resolve_source(recipe_path, clip["source"])
            source_sets[variant_name].add(str(source).casefold())
            if int(clip["frames"]) <= 0:
                raise ValueError(f"{variant_name}/{clip['id']} has invalid frames.")
            if float(clip["source_in"]) < 0:
                raise ValueError(f"{variant_name}/{clip['id']} has invalid source_in.")
            grade = clip.get("grade", "haku-neutral")
            if grade not in GRADE_FILTERS:
                raise ValueError(f"Unknown grade preset: {grade}")

    if source_sets["plain"] != source_sets["proof"]:
        raise ValueError(
            "plain and proof must use the same source set. "
            f"plain-only={source_sets['plain'] - source_sets['proof']}, "
            f"proof-only={source_sets['proof'] - source_sets['plain']}"
        )

    plain_frames = sum(int(item["frames"]) for item in recipe["variants"]["plain"]["clips"])
    proof_frames = sum(int(item["frames"]) for item in recipe["variants"]["proof"]["clips"])
    if plain_frames != proof_frames:
        raise ValueError(
            f"plain/proof frame totals differ: {plain_frames} vs {proof_frames}"
        )


def variant_source_usage(
    recipe_path: Path, recipe: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for variant_name in ("plain", "proof"):
        result[variant_name] = []
        for clip in recipe["variants"][variant_name]["clips"]:
            source = resolve_source(recipe_path, clip["source"])
            result[variant_name].append(
                {
                    "clip_id": clip["id"],
                    "source": str(source),
                    "source_in": float(clip["source_in"]),
                    "frames": int(clip["frames"]),
                    "focus_x": float(clip.get("focus_x", 0.5)),
                    "focus_y": float(clip.get("focus_y", 0.5)),
                    "grade": clip.get("grade", "haku-neutral"),
                    "sha256": sha256(source),
                }
            )
    return result


def crop_filter(
    width: int,
    height: int,
    focus_x: float,
    focus_y: float,
) -> str:
    aspect = width / height
    crop_w = f"floor(min(iw,ih*{aspect:.10f})/2)*2"
    crop_h = f"floor(min(ih,iw/{aspect:.10f})/2)*2"
    crop_x = f"max(0,min(iw-out_w,iw*{focus_x:.6f}-out_w/2))"
    crop_y = f"max(0,min(ih-out_h,ih*{focus_y:.6f}-out_h/2))"
    return (
        f"crop=w='{crop_w}':h='{crop_h}':x='{crop_x}':y='{crop_y}',"
        f"scale={width}:{height}:flags=lanczos"
    )


def render_variant(
    ffmpeg: Path,
    recipe_path: Path,
    recipe: dict[str, Any],
    variant_name: str,
    target: Path,
) -> dict[str, Any]:
    canvas = recipe["canvas"]
    fps = int(canvas["fps"])
    width = int(canvas["width"])
    height = int(canvas["height"])
    clips = recipe["variants"][variant_name]["clips"]
    total_frames = sum(int(item["frames"]) for item in clips)

    command = [str(ffmpeg), "-hide_banner", "-nostdin", "-y"]
    filters: list[str] = []
    labels: list[str] = []
    boundaries: list[dict[str, Any]] = []
    frame_cursor = 0

    for index, clip in enumerate(clips):
        source = resolve_source(recipe_path, clip["source"])
        command.extend(["-i", str(source)])
        frames = int(clip["frames"])
        source_in = float(clip["source_in"])
        focus_x = float(clip.get("focus_x", 0.5))
        focus_y = float(clip.get("focus_y", 0.5))
        grade_filter = GRADE_FILTERS[clip.get("grade", "haku-neutral")]
        output_label = f"v{index}"
        filters.append(
            f"[{index}:v]"
            f"trim=start={source_in:.6f}:duration={(frames / fps):.6f},"
            "setpts=PTS-STARTPTS,"
            f"fps={fps},trim=end_frame={frames},"
            f"settb=1/{fps},setpts=N/({fps}*TB),"
            + crop_filter(width, height, focus_x, focus_y)
            + ","
            + grade_filter
            + ",format=yuv420p"
            + f"[{output_label}]"
        )
        labels.append(f"[{output_label}]")
        if index:
            boundaries.append(
                {
                    "after_clip_id": clips[index - 1]["id"],
                    "before_clip_id": clip["id"],
                    "frame": frame_cursor,
                    "time_seconds": round(frame_cursor / fps, 6),
                }
            )
        frame_cursor += frames

    filters.append(
        "".join(labels)
        + f"concat=n={len(labels)}:v=1:a=0,"
        + f"trim=end_frame={total_frames},setpts=N/({fps}*TB)[outv]"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-an",
            "-frames:v",
            str(total_frames),
            "-c:v",
            "libx264",
            "-preset",
            recipe["render_policy"].get("preset", "medium"),
            "-crf",
            str(recipe["render_policy"].get("crf", 17)),
            "-threads",
            str(recipe["render_policy"]["max_threads"]),
            "-movflags",
            "+faststart",
            "-pix_fmt",
            "yuv420p",
            str(target),
        ]
    )
    run(command)
    return {
        "variant": variant_name,
        "path": str(target),
        "frames": total_frames,
        "duration_seconds": round(total_frames / fps, 6),
        "boundaries": boundaries,
    }


def build_storyboard(
    ffmpeg: Path,
    video: Path,
    target: Path,
    duration: float,
) -> None:
    interval = max(0.4, duration / 36)
    frame_count = max(1, math.ceil(duration / interval))
    columns = 6
    rows = math.ceil(frame_count / columns)
    target.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-nostdin",
            "-y",
            "-threads",
            "2",
            "-i",
            str(video),
            "-an",
            "-vf",
            (
                f"fps=1/{interval:.6f},scale=240:-2:flags=lanczos,"
                f"tile={columns}x{rows}:padding=4:margin=4:color=white"
            ),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(target),
        ]
    )


def build_transition_strips(
    ffmpeg: Path,
    video: Path,
    target_dir: Path,
    boundaries: list[dict[str, Any]],
    fps: int,
) -> list[str]:
    target_dir.mkdir(parents=True, exist_ok=True)
    for stale in target_dir.glob("transition-*.jpg"):
        stale.unlink()
    outputs: list[str] = []
    for index, boundary in enumerate(boundaries, start=1):
        center = float(boundary["time_seconds"])
        start = max(0.0, center - 5 / fps)
        target = target_dir / f"transition-{index:02d}-{center:.3f}s.jpg"
        run(
            [
                str(ffmpeg),
                "-hide_banner",
                "-nostdin",
                "-y",
                "-threads",
                "2",
                "-ss",
                f"{start:.6f}",
                "-i",
                str(video),
                "-an",
                "-vf",
                "fps=24,scale=180:-2:flags=lanczos,tile=10x1:padding=4:margin=4:color=white",
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(target),
            ]
        )
        outputs.append(str(target))
    return outputs


def build_comparison(
    ffmpeg: Path,
    plain: Path,
    proof: Path,
    target: Path,
    frames: int,
    include_audio: bool,
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    filter_complex = (
        "[0:v]scale=506:900:flags=lanczos[p];"
        "[1:v]scale=506:900:flags=lanczos[q];"
        "color=c=0x171719:s=1920x1080:r=24[bg];"
        "[bg][p]overlay=x=374:y=130[tmp];"
        "[tmp][q]overlay=x=1040:y=130,"
        "drawtext=fontfile='C\\:/Windows/Fonts/arialbd.ttf':"
        "text='PLAIN':x=550:y=48:fontsize=42:fontcolor=white,"
        "drawtext=fontfile='C\\:/Windows/Fonts/arialbd.ttf':"
        "text='HAKU PROOF':x=1150:y=48:fontsize=42:fontcolor=white,"
        "format=yuv420p[outv]"
    )
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
            filter_complex,
            "-map",
            "[outv]",
            "-frames:v",
            str(frames),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "17",
            "-threads",
            "2",
            "-movflags",
            "+faststart",
    ]
    if include_audio:
        command.extend(["-map", "0:a:0", "-c:a", "aac", "-b:a", "192k"])
    else:
        command.append("-an")
    command.append(str(target))
    run(command)


def probe_video(ffprobe: Path, video: Path) -> dict[str, Any]:
    completed = run(
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
            str(video),
        ]
    )
    return json.loads(completed.stdout)


def detect_freeze_and_black(ffmpeg: Path, video: Path) -> dict[str, list[str]]:
    completed = subprocess.run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-nostdin",
            "-threads",
            "2",
            "-i",
            str(video),
            "-an",
            "-vf",
            "freezedetect=n=0.002:d=0.30,blackdetect=d=0.20:pix_th=0.08",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
        env={**os.environ, "OMP_NUM_THREADS": "2"},
    )
    lines = completed.stderr.splitlines()
    return {
        "freeze_events": [line for line in lines if "freezedetect" in line and "freeze_" in line],
        "black_events": [line for line in lines if "blackdetect" in line and "black_" in line],
    }


def main() -> int:
    args = parse_args()
    recipe_path = args.recipe.resolve()
    output_dir = args.output_dir.resolve()
    ffmpeg = resolve_binary(args.ffmpeg, "ffmpeg")
    ffprobe = resolve_binary(args.ffprobe, "ffprobe")
    recipe = read_recipe(recipe_path)
    validate_recipe(recipe_path, recipe)

    output_dir.mkdir(parents=True, exist_ok=True)
    plain_path = output_dir / "plain.mp4"
    proof_path = output_dir / "proof.mp4"
    plain_report = render_variant(ffmpeg, recipe_path, recipe, "plain", plain_path)
    proof_report = render_variant(ffmpeg, recipe_path, recipe, "proof", proof_path)

    frames = int(plain_report["frames"])
    duration = float(plain_report["duration_seconds"])
    licensed_audio = prepare_licensed_audio(recipe_path, recipe, duration)
    if licensed_audio is not None:
        max_threads = int(recipe["render_policy"]["max_threads"])
        mux_licensed_audio(ffmpeg, plain_path, licensed_audio, run, max_threads)
        mux_licensed_audio(ffmpeg, proof_path, licensed_audio, run, max_threads)
    comparison_path = output_dir / "plain-vs-proof.mp4"
    build_comparison(
        ffmpeg, plain_path, proof_path, comparison_path, frames,
        include_audio=licensed_audio is not None,
    )

    storyboard_dir = output_dir / "storyboards"
    build_storyboard(
        ffmpeg,
        plain_path,
        storyboard_dir / "plain-storyboard.jpg",
        duration,
    )
    build_storyboard(
        ffmpeg,
        proof_path,
        storyboard_dir / "proof-storyboard.jpg",
        duration,
    )
    transition_paths = build_transition_strips(
        ffmpeg,
        proof_path,
        output_dir / "transition-strips",
        proof_report["boundaries"],
        int(recipe["canvas"]["fps"]),
    )

    report = {
        "schema_version": "1.0",
        "project_id": recipe["project_id"],
        "recipe": str(recipe_path),
        "recipe_sha256": sha256(recipe_path),
        "audio_policy": recipe["audio_policy"],
        "audio_render": report_audio(licensed_audio, recipe["audio_policy"]),
        "render_policy": recipe["render_policy"],
        "same_source_set_verified": True,
        "variant_source_usage": variant_source_usage(recipe_path, recipe),
        "plain": {
            **plain_report,
            "sha256": sha256(plain_path),
            "probe": probe_video(ffprobe, plain_path),
            "automated_qc": detect_freeze_and_black(ffmpeg, plain_path),
        },
        "proof": {
            **proof_report,
            "sha256": sha256(proof_path),
            "probe": probe_video(ffprobe, proof_path),
            "automated_qc": detect_freeze_and_black(ffmpeg, proof_path),
        },
        "comparison": str(comparison_path),
        "storyboards": {
            "plain": str(storyboard_dir / "plain-storyboard.jpg"),
            "proof": str(storyboard_dir / "proof-storyboard.jpg"),
        },
        "transition_strips": transition_paths,
        "visual_review": {
            "status": "pending_main_agent_review",
            "originals_reviewed": False,
            "plain_reviewed": False,
            "proof_reviewed": False,
            "every_transition_reviewed": False,
            "notes": [],
        },
        "user_verdict": {
            "status": "pending",
            "allowed_values": ["accepted", "partial", "rejected"],
        },
    }
    report_path = output_dir / "render-report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
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
    report = json.loads(report_path.read_text(encoding="utf-8"))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
