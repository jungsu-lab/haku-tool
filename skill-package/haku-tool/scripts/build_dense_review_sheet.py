from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path


def run(command: list[str]) -> str:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=300,
    )
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout


def probe_video(ffprobe: Path, video: Path) -> tuple[float, int, int]:
    payload = run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=width,height",
            "-select_streams",
            "v:0",
            "-of",
            "json",
            str(video),
        ]
    )
    data = json.loads(payload)
    stream = data["streams"][0]
    return (
        float(data["format"]["duration"]),
        int(stream["width"]),
        int(stream["height"]),
    )


def choose_sampling_plan(
    duration: float,
    requested_fps: float,
    max_samples: int,
) -> tuple[float, int]:
    if duration < 0:
        raise ValueError("duration must not be negative")
    if requested_fps <= 0:
        raise ValueError("requested_fps must be greater than zero")
    if max_samples <= 0:
        raise ValueError("max_samples must be greater than zero")
    sample_fps = min(
        requested_fps,
        max_samples / max(duration, 0.001),
    )
    sample_count = max(
        1,
        min(max_samples, int(math.floor(duration * sample_fps))),
    )
    return sample_fps, sample_count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("videos", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--ffprobe", type=Path, required=True)
    parser.add_argument("--max-samples", type=int, default=160)
    parser.add_argument(
        "--sample-fps",
        type=float,
        default=None,
        help="Requested visual sampling rate. It is reduced only to respect max-samples.",
    )
    args = parser.parse_args()
    if args.max_samples <= 0:
        parser.error("--max-samples must be greater than zero")
    if args.sample_fps is not None and args.sample_fps <= 0:
        parser.error("--sample-fps must be greater than zero")
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    reports = []

    for video_arg in args.videos:
        video = video_arg.resolve()
        duration, source_width, source_height = probe_video(
            args.ffprobe.resolve(), video
        )
        requested_fps = args.sample_fps if args.sample_fps is not None else 4.0
        sample_fps, sample_count = choose_sampling_plan(
            duration,
            requested_fps,
            args.max_samples,
        )
        columns = 10
        rows = int(math.ceil(sample_count / columns))
        if source_width >= source_height:
            cell_width, cell_height = 240, 135
        else:
            cell_width, cell_height = 160, 284
        output = output_dir / f"{video.stem}-dense.jpg"
        filter_graph = (
            f"fps={sample_fps:.6f},"
            f"scale={cell_width - 2}:{cell_height - 2}:flags=lanczos:"
            "force_original_aspect_ratio=decrease,"
            f"pad={cell_width}:{cell_height}:(ow-iw)/2:(oh-ih)/2:black,"
            "setsar=1,"
            "drawtext=text='%{pts\\:hms}':x=6:y=h-th-6:"
            "fontsize=15:fontcolor=white:box=1:boxcolor=black@0.65,"
            f"tile={columns}x{rows}:nb_frames={sample_count}:padding=3:margin=3"
        )
        run(
            [
                str(args.ffmpeg.resolve()),
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
        reports.append(
            {
                "video": str(video),
                "duration_seconds": duration,
                "source_resolution": {
                    "width": source_width,
                    "height": source_height,
                },
                "sample_fps": sample_fps,
                "sample_count": sample_count,
                "sheet": str(output),
            }
        )

    report_path = output_dir / "dense-review-report.json"
    report_path.write_text(
        json.dumps({"items": reports}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"built": len(reports), "report": str(report_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
