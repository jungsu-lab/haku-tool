from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

from temporal_continuity_qc import attach_temporal_continuity_qc


def run(command: list[str], timeout: int = 900) -> str:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(command)
            + "\n"
            + (completed.stderr or completed.stdout)
        )
    return completed.stdout


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


def probe_duration(ffprobe: Path, video: Path) -> float:
    return float(
        run(
            [
                str(ffprobe),
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video),
            ]
        ).strip()
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def probe_frames_and_canvas(ffprobe: Path, video: Path) -> dict[str, Any]:
    return json.loads(
        run(
            [
                str(ffprobe),
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-count_frames",
                "-show_entries",
                "stream=width,height,r_frame_rate,nb_read_frames",
                "-of",
                "json",
                str(video),
            ]
        )
    )["streams"][0]


def expected_variant_frames(recipe: dict[str, Any], name: str) -> int:
    variant = recipe["variants"][name]
    units = variant.get("segments", variant.get("clips"))
    if not units:
        raise ValueError(f"{name} variant must contain segments or clips")
    return sum(int(item["frames"]) for item in units)


def schema_1_variant_source_usage(
    recipe_path: Path, recipe: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for variant_name in ("plain", "proof"):
        result[variant_name] = []
        for clip in recipe["variants"][variant_name]["clips"]:
            source = Path(clip["source"])
            if not source.is_absolute():
                source = (recipe_path.parent / source).resolve()
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


def validate_reused_render(
    recipe_path: Path,
    recipe: dict[str, Any],
    output_dir: Path,
    ffprobe: Path,
) -> dict[str, Any]:
    report_path = output_dir / "render-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("project_id") != recipe.get("project_id"):
        raise ValueError("Reused render project_id does not match recipe")
    if str(report.get("schema_version")) != str(recipe.get("schema_version")):
        raise ValueError("Reused render schema_version does not match recipe")
    if report.get("audio_policy") != recipe.get("audio_policy"):
        raise ValueError("Reused render audio_policy does not match recipe")

    recipe_hash = sha256(recipe_path)
    recorded_hash = report.get("recipe_sha256")
    if not recorded_hash:
        raise ValueError(
            "Reused render has no immutable recipe_sha256; render a new version"
        )
    if recorded_hash.upper() != recipe_hash:
        raise ValueError("Reused render recipe hash does not match")

    recorded_recipe = report.get("recipe")
    if recorded_recipe and Path(recorded_recipe).resolve() != recipe_path:
        raise ValueError("Reused render recipe path does not match")

    canvas = recipe["canvas"]
    for name in ("plain", "proof"):
        video = output_dir / f"{name}.mp4"
        expected_frames = expected_variant_frames(recipe, name)
        if int(report[name]["frames"]) != expected_frames:
            raise ValueError(f"Reused {name} report frame total does not match recipe")
        probe = probe_frames_and_canvas(ffprobe, video)
        if int(probe["nb_read_frames"]) != expected_frames:
            raise ValueError(f"Reused {name} video frame total does not match recipe")
        if (
            int(probe["width"]) != int(canvas["width"])
            or int(probe["height"]) != int(canvas["height"])
        ):
            raise ValueError(f"Reused {name} canvas does not match recipe")
        if Fraction(probe["r_frame_rate"]) != Fraction(int(canvas["fps"]), 1):
            raise ValueError(f"Reused {name} frame rate does not match recipe")
        recorded_output_hash = report[name].get("sha256")
        if not recorded_output_hash:
            raise ValueError(
                f"Reused {name} has no rendered-output hash; render a new version"
            )
        if recorded_output_hash.upper() != sha256(video):
            raise ValueError(f"Reused {name} output bytes do not match report")

    if recipe.get("schema_version") == "1.1":
        material_ledger = report.get("same_source_set_verified", {}).get(
            "material_ledger", {}
        )
        if set(material_ledger) != set(recipe["materials"]):
            raise ValueError("Reused material ledger IDs do not match recipe")
        for material_id, item in recipe["materials"].items():
            source = Path(item["source"])
            if not source.is_absolute():
                source = (recipe_path.parent / source).resolve()
            ledger_item = material_ledger[material_id]
            if Path(ledger_item["source"]).resolve() != source:
                raise ValueError(f"Reused source path differs for {material_id}")
            if float(ledger_item["source_in"]) != float(item.get("source_in", 0)):
                raise ValueError(f"Reused source anchor differs for {material_id}")
            if ledger_item["sha256"].upper() != sha256(source):
                raise ValueError(f"Reused source hash differs for {material_id}")
    elif recipe.get("schema_version") == "1.0":
        recorded_usage = report.get("variant_source_usage")
        if not recorded_usage:
            raise ValueError(
                "Reused schema 1.0 render has no source usage hashes; "
                "render a new version"
            )
        if recorded_usage != schema_1_variant_source_usage(recipe_path, recipe):
            raise ValueError(
                "Reused schema 1.0 source path, anchor, order, frame usage, "
                "grade, crop focus, or hash differs from recipe"
            )

    return {
        "project_id": report["project_id"],
        "schema_version": report["schema_version"],
        "recipe_sha256": recipe_hash,
        "recipe_hash_recorded_by_renderer": bool(recorded_hash),
        "legacy_recipe_path_match": bool(recorded_recipe),
        "frame_canvas_and_source_identity_verified": True,
    }


def build_dense_sheet(
    ffmpeg: Path,
    ffprobe: Path,
    video: Path,
    output: Path,
    requested_fps: float,
    max_samples: int,
) -> dict[str, Any]:
    duration = probe_duration(ffprobe, video)
    sample_fps = min(requested_fps, max_samples / max(duration, 0.001))
    sample_count = max(1, int(math.floor(duration * sample_fps)))
    columns = 8
    rows = int(math.ceil(sample_count / columns))
    output.parent.mkdir(parents=True, exist_ok=True)
    filter_graph = (
        f"fps={sample_fps:.6f},"
        "scale=158:282:flags=lanczos:force_original_aspect_ratio=decrease,"
        "pad=160:284:(ow-iw)/2:(oh-ih)/2:black,"
        "setsar=1,"
        "drawtext=text='%{pts\\:hms}':x=5:y=h-th-5:"
        "fontsize=14:fontcolor=white:box=1:boxcolor=black@0.65,"
        f"tile={columns}x{rows}:nb_frames={sample_count}:padding=3:margin=3"
    )
    run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-nostdin",
            "-y",
            "-i",
            str(video),
            "-vf",
            filter_graph,
            "-frames:v",
            "1",
            "-update",
            "1",
            "-threads",
            "2",
            str(output),
        ]
    )
    return {
        "path": str(output),
        "sample_fps": sample_fps,
        "sample_count": sample_count,
        "coverage_seconds": duration,
    }


def proof_events(recipe: dict[str, Any]) -> list[dict[str, Any]]:
    fps = int(recipe["canvas"]["fps"])
    proof_variant = recipe["variants"]["proof"]
    segments = proof_variant.get("segments", proof_variant.get("clips"))
    if not segments:
        raise ValueError("proof variant must contain segments or clips")
    events: list[dict[str, Any]] = []
    cursor = 0
    for index, segment in enumerate(segments):
        frames = int(segment["frames"])
        segment_type = segment.get("type", "single")
        if index:
            events.append(
                {
                    "id": f"boundary-{index:02d}-{segment['id']}",
                    "kind": "segment_boundary",
                    "frame": cursor,
                    "seconds": cursor / fps,
                }
            )
        if segment_type == "bounded-video-trace":
            active_ranges = [
                ("trace", [int(value) for value in segment["active_frames"]])
            ]
        elif segment_type == "memory-window-reveal":
            active_ranges = [
                (window["id"], [int(value) for value in window["active_frames"]])
                for window in segment["windows"]
            ]
        elif segment_type == "functional-panels":
            active_ranges = [
                (
                    panel["id"],
                    [
                        int(value)
                        for value in panel.get("active_frames", [0, frames])
                    ],
                )
                for panel in segment["panels"]
            ]
        else:
            active_ranges = []
        for event_id, (start, end) in active_ranges:
            for edge, local_frame in (("start", start), ("end", end)):
                absolute_frame = cursor + local_frame
                if 0 < absolute_frame < cursor + frames:
                    events.append(
                        {
                            "id": (
                                f"internal-{segment['id']}-{event_id}-{edge}"
                            ),
                            "kind": "internal_event",
                            "frame": absolute_frame,
                            "seconds": absolute_frame / fps,
                        }
                    )
        cursor += frames
    return events


def build_boundary_strip(
    ffmpeg: Path,
    video: Path,
    event: dict[str, Any],
    output: Path,
    fps: int,
) -> dict[str, Any]:
    radius_frames = 6
    start = max(0.0, (int(event["frame"]) - radius_frames) / fps)
    duration = (radius_frames * 2 + 1) / fps
    filter_graph = (
        f"fps={fps},"
        "scale=142:254:flags=lanczos:force_original_aspect_ratio=decrease,"
        "pad=144:256:(ow-iw)/2:(oh-ih)/2:black,"
        "drawtext=text='%{pts\\:hms}':x=4:y=h-th-4:"
        "fontsize=13:fontcolor=white:box=1:boxcolor=black@0.65,"
        "tile=13x1:padding=2:margin=2"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-nostdin",
            "-y",
            "-ss",
            f"{start:.6f}",
            "-i",
            str(video),
            "-t",
            f"{duration:.6f}",
            "-vf",
            filter_graph,
            "-frames:v",
            "1",
            "-update",
            "1",
            "-threads",
            "2",
            str(output),
        ]
    )
    return {
        **event,
        "strip": str(output),
        "range_seconds": [
            start,
            start + duration,
        ],
        "review_status": "pending_direct_visual_review",
    }


def write_critique_template(
    path: Path,
    recipe: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    hypotheses = "\n".join(
        f"- [ ] {item}" for item in recipe.get("hypotheses_under_test", [])
    ) or "- [ ] Add a falsifiable hypothesis."
    path.write_text(
        (
            f"# {recipe['project_id']} — direct visual critique\n\n"
            "## Verdict\n\n"
            "`pending_direct_visual_review`\n\n"
            "This is not user acceptance and does not advance promotion.\n\n"
            "## Mandatory review scope\n\n"
            "- [ ] Every unedited source from start to end\n"
            "- [ ] Plain dense sheet from start to end\n"
            "- [ ] Proof dense sheet from start to end\n"
            "- [ ] Every boundary and internal-event strip\n"
            "- [ ] Plain versus proof at matching timeline positions\n"
            "- [ ] Full-speed playback, or explicitly record that it was unavailable\n\n"
            "## Hypotheses\n\n"
            f"{hypotheses}\n\n"
            "## Observations\n\n"
            "- Add timestamped observations only. Do not mix inference here.\n\n"
            "## Inferences\n\n"
            "- Explain why each observed relation helps or hurts the stated purpose.\n\n"
            "## Failure and counterexample check\n\n"
            "- Freeze or last-frame padding:\n"
            "- Motion-direction or pose reset:\n"
            "- Crop/scale twitch:\n"
            "- Black-frame accident:\n"
            "- Decorative rather than causal in-frame edit:\n"
            "- Material-fit mismatch:\n\n"
            "## Research verdict\n\n"
            "- `pass`, `partial_pass`, or `fail`:\n"
            "- Evidence:\n"
            "- Next revision, maximum four causal changes:\n\n"
            "## User verdict\n\n"
            "`pending` — only the user may set `accepted`, `partial`, or `rejected`.\n\n"
            f"Review manifest: `{Path(manifest['manifest_path']).name}`\n"
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Render a Haku proof and prepare mandatory visual-review evidence. "
            "This command never marks a proof as visually approved."
        )
    )
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path)
    parser.add_argument("--ffprobe", type=Path)
    parser.add_argument("--renderer", type=Path)
    parser.add_argument(
        "--reuse-render",
        action="store_true",
        help="Reuse existing plain.mp4, proof.mp4, and render-report.json.",
    )
    args = parser.parse_args()

    ffmpeg = resolve_binary(args.ffmpeg, "ffmpeg")
    ffprobe = resolve_binary(args.ffprobe, "ffprobe")
    recipe_path = args.recipe.resolve()
    output_dir = args.output_dir.resolve()
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    if args.renderer:
        renderer = args.renderer.resolve()
    elif recipe.get("schema_version") == "1.0":
        renderer = Path(__file__).with_name("render_proof_recipe.py")
    else:
        renderer = Path(__file__).with_name("render_composite_proof_recipe.py")

    if args.reuse_render:
        required = [
            output_dir / "plain.mp4",
            output_dir / "proof.mp4",
            output_dir / "render-report.json",
        ]
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise FileNotFoundError("Missing reusable render files: " + ", ".join(missing))
        reuse_provenance = validate_reused_render(
            recipe_path, recipe, output_dir, ffprobe
        )
    else:
        if output_dir.exists() and any(output_dir.iterdir()):
            raise FileExistsError(
                f"{output_dir} is not empty; use a new version or --reuse-render"
            )
        run(
            [
                sys.executable,
                str(renderer),
                str(recipe_path),
                "--output-dir",
                str(output_dir),
                "--ffmpeg",
                str(ffmpeg),
                "--ffprobe",
                str(ffprobe),
            ]
        )
        reuse_provenance = {
            "project_id": recipe["project_id"],
            "schema_version": recipe["schema_version"],
            "recipe_sha256": sha256(recipe_path),
            "fresh_render": True,
        }

    review_dir = output_dir / "review-auto"
    manifest_path = review_dir / "review-manifest.json"
    if manifest_path.exists():
        raise FileExistsError(
            f"{manifest_path} already exists; use a new versioned output directory "
            "instead of resetting completed or pending review state"
        )
    dense = {
        "plain": build_dense_sheet(
            ffmpeg,
            ffprobe,
            output_dir / "plain.mp4",
            review_dir / "plain-8fps.jpg",
            8.0,
            160,
        ),
        "proof": build_dense_sheet(
            ffmpeg,
            ffprobe,
            output_dir / "proof.mp4",
            review_dir / "proof-8fps.jpg",
            8.0,
            160,
        ),
    }
    fps = int(recipe["canvas"]["fps"])
    boundary_reports = [
        build_boundary_strip(
            ffmpeg,
            output_dir / "proof.mp4",
            event,
            review_dir / "boundaries" / f"{event['id']}.jpg",
            fps,
        )
        for event in proof_events(recipe)
    ]
    # Keep review manifests portable and avoid Windows cwd/locale corruption in
    # absolute paths. Every evidence path is resolved from the manifest folder.
    dense["plain"]["path"] = "plain-8fps.jpg"
    dense["proof"]["path"] = "proof-8fps.jpg"
    for report in boundary_reports:
        report["strip"] = str(Path("boundaries") / Path(report["strip"]).name)

    manifest = {
        "schema_version": "1.0",
        "project_id": recipe["project_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "recipe": str(Path("..") / ".." / recipe_path.name),
        "render_report": str(Path("..") / "render-report.json"),
        "render_provenance_verification": reuse_provenance,
        "manifest_path": manifest_path.name,
        "dense_full_sequence_evidence": dense,
        "boundary_and_internal_event_evidence": boundary_reports,
        "direct_visual_review": {
            "status": "pending_main_agent_review",
            "originals_reviewed": False,
            "plain_reviewed": False,
            "proof_reviewed": False,
            "all_boundary_strips_reviewed": False,
            "full_playback_reviewed": False,
        },
        "research_verdict": {
            "status": "pending",
            "allowed_values": ["pass", "partial_pass", "fail"],
        },
        "user_verdict": {
            "status": "pending",
            "allowed_values": ["accepted", "partial", "rejected"],
        },
        "promotion_increment": 0,
        "guardrail": (
            "Generated evidence is not direct review. Only the main agent may record "
            "research review; only the user may record acceptance."
        ),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    continuity = attach_temporal_continuity_qc(
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
        render_report=output_dir / "render-report.json",
        review_manifest=manifest_path,
        evidence_root=review_dir / "temporal-qc",
    )
    continuity_status = (
        "fail"
        if any(
            item["automated_verdict"]["status"] == "fail"
            for item in continuity.values()
        )
        else "review_required"
        if any(
            item["automated_verdict"]["status"] == "review_required"
            for item in continuity.values()
        )
        else "pass"
    )
    manifest["temporal_continuity_qc"] = {
        "status": continuity_status,
        "plain": str(Path("temporal-qc") / "plain.json"),
        "proof": str(Path("temporal-qc") / "proof.json"),
        "fail_closed": True,
        "main_agent_review_required": True,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if continuity_status == "fail":
        raise RuntimeError(
            "Temporal continuity gate failed; proof cycle is not review-ready"
        )
    write_critique_template(review_dir / "CRITIQUE.template.md", recipe, manifest)
    print(
        json.dumps(
            {
                "success": True,
                "manifest": str(manifest_path),
                "event_strips": len(boundary_reports),
                "review_status": "pending_main_agent_review",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
