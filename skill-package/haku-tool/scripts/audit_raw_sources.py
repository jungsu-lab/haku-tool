from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


DURATION_RE = re.compile(
    r"Duration:\s*(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+(?:\.\d+)?)"
)
VIDEO_RE = re.compile(
    r"Video:\s*(?P<codec>[^,]+).*?(?P<width>\d{2,5})x(?P<height>\d{2,5})"
    r".*?(?P<fps>\d+(?:\.\d+)?)\s*fps",
    re.IGNORECASE,
)
SCENE_RE = re.compile(r"pts_time:(?P<time>\d+(?:\.\d+)?)")
FREEZE_START_RE = re.compile(r"freeze_start:\s*(?P<time>-?\d+(?:\.\d+)?)")
FREEZE_END_RE = re.compile(r"freeze_end:\s*(?P<time>-?\d+(?:\.\d+)?)")
BLACK_START_RE = re.compile(r"black_start:(?P<time>\d+(?:\.\d+)?)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit raw proof sources without treating metrics as a verdict."
    )
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path)
    return parser.parse_args()


def resolve_ffmpeg(explicit: Path | None) -> Path:
    if explicit:
        result = explicit.resolve()
        if not result.is_file():
            raise FileNotFoundError(result)
        return result
    found = shutil.which("ffmpeg")
    if found:
        return Path(found)
    raise FileNotFoundError("ffmpeg not found; pass --ffmpeg explicitly.")


def run(
    ffmpeg: Path,
    args: list[str],
    *,
    timeout: int = 240,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(ffmpeg), "-hide_banner", "-nostdin", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env={**os.environ, "OMP_NUM_THREADS": "2"},
    )


def probe(ffmpeg: Path, source: Path) -> dict[str, Any]:
    completed = run(ffmpeg, ["-i", str(source)])
    duration_match = DURATION_RE.search(completed.stderr)
    video_match = VIDEO_RE.search(completed.stderr)
    if not duration_match or not video_match:
        raise RuntimeError(f"Could not parse metadata for {source.name}")
    duration = (
        int(duration_match.group("hours")) * 3600
        + int(duration_match.group("minutes")) * 60
        + float(duration_match.group("seconds"))
    )
    return {
        "duration_seconds": round(duration, 3),
        "codec": video_match.group("codec").strip(),
        "width": int(video_match.group("width")),
        "height": int(video_match.group("height")),
        "fps": float(video_match.group("fps")),
        "bytes": source.stat().st_size,
    }


def detect_events(ffmpeg: Path, source: Path) -> dict[str, list[float]]:
    scene = run(
        ffmpeg,
        [
            "-threads",
            "2",
            "-i",
            str(source),
            "-an",
            "-vf",
            "scale=360:-2:flags=bilinear,select='gt(scene,0.28)',showinfo",
            "-f",
            "null",
            "-",
        ],
    )
    freeze = run(
        ffmpeg,
        [
            "-threads",
            "2",
            "-i",
            str(source),
            "-an",
            "-vf",
            "scale=360:-2:flags=bilinear,freezedetect=n=0.002:d=0.30",
            "-f",
            "null",
            "-",
        ],
    )
    black = run(
        ffmpeg,
        [
            "-threads",
            "2",
            "-i",
            str(source),
            "-an",
            "-vf",
            "scale=360:-2:flags=bilinear,blackdetect=d=0.20:pix_th=0.08",
            "-f",
            "null",
            "-",
        ],
    )
    return {
        "scene_change_candidates": sorted(
            {
                round(float(match.group("time")), 3)
                for match in SCENE_RE.finditer(scene.stderr)
            }
        ),
        "freeze_start_candidates": [
            round(float(match.group("time")), 3)
            for match in FREEZE_START_RE.finditer(freeze.stderr)
        ],
        "freeze_end_candidates": [
            round(float(match.group("time")), 3)
            for match in FREEZE_END_RE.finditer(freeze.stderr)
        ],
        "black_start_candidates": [
            round(float(match.group("time")), 3)
            for match in BLACK_START_RE.finditer(black.stderr)
        ],
    }


def build_storyboard(
    ffmpeg: Path,
    source: Path,
    target: Path,
    duration: float,
) -> dict[str, Any]:
    max_frames = 48
    interval = max(0.5, duration / max_frames)
    expected_frames = max(1, math.ceil(duration / interval))
    columns = 6
    rows = math.ceil(expected_frames / columns)
    target.parent.mkdir(parents=True, exist_ok=True)
    completed = run(
        ffmpeg,
        [
            "-threads",
            "2",
            "-i",
            str(source),
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
            "-y",
            str(target),
        ],
    )
    if completed.returncode != 0 or not target.is_file():
        raise RuntimeError(
            f"Storyboard failed for {source.name}: {completed.stderr[-1200:]}"
        )
    return {
        "path": str(target),
        "interval_seconds": round(interval, 4),
        "expected_frames": expected_frames,
        "grid": {"columns": columns, "rows": rows},
    }


def main() -> int:
    args = parse_args()
    source_dir = args.source_dir.resolve()
    output_dir = args.output_dir.resolve()
    storyboard_dir = output_dir / "storyboards"
    ffmpeg = resolve_ffmpeg(args.ffmpeg)
    output_dir.mkdir(parents=True, exist_ok=True)

    sources: list[dict[str, Any]] = []
    for source in sorted(source_dir.glob("*.mp4")):
        print(f"Auditing {source.name}", flush=True)
        metadata = probe(ffmpeg, source)
        sources.append(
            {
                "source": {"path": str(source), "filename": source.name},
                "metadata": metadata,
                "automated_preflight": detect_events(ffmpeg, source),
                "storyboard": build_storyboard(
                    ffmpeg,
                    source,
                    storyboard_dir / f"{source.stem}.jpg",
                    float(metadata["duration_seconds"]),
                ),
                "visual_review": {
                    "status": "pending_main_agent_review",
                    "single_take": None,
                    "existing_edit_detected": None,
                    "haku_material_fit": None,
                    "notes": [],
                },
            }
        )

    report = {
        "schema_version": "1.0",
        "audit_policy": {
            "metrics_are_advisory_only": True,
            "main_agent_visual_review_required": True,
            "scene_threshold": 0.28,
            "freeze_threshold": {"noise": 0.002, "duration_seconds": 0.30},
            "max_decode_threads": 2,
        },
        "sources": sources,
    }
    target = output_dir / "source-audit-auto.json"
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
