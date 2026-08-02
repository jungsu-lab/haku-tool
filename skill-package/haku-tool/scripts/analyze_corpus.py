#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def run_dynamics(
    item: dict[str, Any],
    source_root: Path,
    output_root: Path,
    dynamics_script: Path,
    ffmpeg: Path,
) -> tuple[str, Path]:
    code = str(item["post_id"])
    video_path = source_root / str(item["filename"])
    reel_dir = output_root / "reels" / code
    dynamics_path = reel_dir / "edit-dynamics.json"
    reel_dir.mkdir(parents=True, exist_ok=True)
    if not dynamics_path.is_file():
        completed = subprocess.run(
            [
                sys.executable,
                str(dynamics_script),
                str(video_path),
                "--output",
                str(dynamics_path),
                "--ffmpeg",
                str(ffmpeg),
            ],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"Dynamics failed for {code}: "
                f"{completed.stderr or completed.stdout}"
            )
    return code, dynamics_path


def evenly_pick(values: list[float], maximum: int) -> list[float]:
    if len(values) <= maximum:
        return values
    indices = np.linspace(0, len(values) - 1, maximum)
    return [values[int(round(index))] for index in indices]


def shot_midpoints(dynamics: dict[str, Any], maximum: int = 24) -> list[float]:
    duration = float(dynamics["video"]["duration"])
    cuts = [
        float(value)
        for value in dynamics["video"]["cut_detection"].get("times", [])
        if 0.0 < float(value) < duration
    ]
    boundaries = [0.0, *cuts, duration]
    midpoints = [
        (boundaries[index] + boundaries[index + 1]) * 0.5
        for index in range(len(boundaries) - 1)
    ]
    if len(midpoints) < min(12, maximum):
        uniform = np.linspace(0.05, max(0.05, duration - 0.05), min(16, maximum))
        midpoints = sorted(set([*midpoints, *uniform.tolist()]))
    return evenly_pick(midpoints, maximum)


def read_frame(capture: cv2.VideoCapture, time_seconds: float) -> np.ndarray:
    capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, time_seconds) * 1000.0)
    ok, frame = capture.read()
    if not ok:
        raise RuntimeError(f"Unable to decode frame at {time_seconds:.3f}s")
    return frame


def frame_metrics(frame: np.ndarray) -> dict[str, float]:
    small = cv2.resize(frame, (240, 135), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    b, g, r = cv2.split(small.astype(np.float32))
    edges = cv2.Canny(gray, 80, 160)
    height, width = gray.shape
    y0, y1 = int(height * 0.25), int(height * 0.75)
    x0, x1 = int(width * 0.25), int(width * 0.75)
    center_edges = edges[y0:y1, x0:x1]
    return {
        "brightness": float(np.mean(gray) / 255.0),
        "contrast": float(np.std(gray) / 255.0),
        "saturation": float(np.mean(hsv[..., 1]) / 255.0),
        "warmth": float(np.mean(r - b) / 255.0),
        "green_bias": float(np.mean(g - (r + b) * 0.5) / 255.0),
        "edge_density": float(np.mean(edges > 0)),
        "center_edge_density": float(np.mean(center_edges > 0)),
    }


def summarize_frame_metrics(rows: list[dict[str, float]]) -> dict[str, float]:
    if not rows:
        return {}
    return {
        key: round(float(np.mean([row[key] for row in rows])), 6)
        for key in rows[0]
    }


def motion_direction(video_path: Path) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Unable to open {video_path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(2, int(round(fps * 0.20)))
    directions = {"left": 0, "right": 0, "up": 0, "down": 0, "static": 0}
    vectors: list[tuple[float, float]] = []
    previous: np.ndarray | None = None
    index = 0
    while index < frame_count:
        ok, frame = capture.read()
        if not ok:
            break
        if index % step:
            index += 1
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (160, 90), interpolation=cv2.INTER_AREA)
        if previous is not None:
            flow = cv2.calcOpticalFlowFarneback(
                previous,
                gray,
                None,
                0.5,
                2,
                15,
                2,
                5,
                1.1,
                0,
            )
            x = float(np.median(flow[..., 0]))
            y = float(np.median(flow[..., 1]))
            vectors.append((x, y))
            magnitude = math.hypot(x, y)
            if magnitude < 0.12:
                directions["static"] += 1
            elif abs(x) >= abs(y):
                directions["right" if x > 0 else "left"] += 1
            else:
                directions["down" if y > 0 else "up"] += 1
        previous = gray
        index += 1
    capture.release()
    dominant = max(directions, key=directions.get) if vectors else "unknown"
    return {
        "dominant": dominant,
        "counts": directions,
        "median_x": round(float(np.median([value[0] for value in vectors])), 6)
        if vectors
        else None,
        "median_y": round(float(np.median([value[1] for value in vectors])), 6)
        if vectors
        else None,
    }


def make_storyboard(
    video_path: Path,
    times: list[float],
    output_path: Path,
    columns: int = 6,
) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Unable to open {video_path}")
    tile_width = 240
    tile_height = 426
    label_height = 34
    tiles: list[np.ndarray] = []
    metric_rows: list[dict[str, float]] = []
    for time_seconds in times:
        frame = read_frame(capture, time_seconds)
        metric_rows.append(frame_metrics(frame))
        height, width = frame.shape[:2]
        target_ratio = tile_width / tile_height
        source_ratio = width / max(height, 1)
        if source_ratio > target_ratio:
            crop_width = max(2, int(round(height * target_ratio)))
            x = (width - crop_width) // 2
            frame = frame[:, x : x + crop_width]
        else:
            crop_height = max(2, int(round(width / target_ratio)))
            y = (height - crop_height) // 2
            frame = frame[y : y + crop_height, :]
        image = cv2.resize(
            frame,
            (tile_width, tile_height),
            interpolation=cv2.INTER_AREA,
        )
        tile = np.full(
            (tile_height + label_height, tile_width, 3),
            248,
            dtype=np.uint8,
        )
        tile[:tile_height] = image
        cv2.putText(
            tile,
            f"{time_seconds:06.2f}s",
            (8, tile_height + 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (20, 20, 20),
            1,
            cv2.LINE_AA,
        )
        tiles.append(tile)
    capture.release()
    rows = int(math.ceil(len(tiles) / columns))
    blank = np.full_like(tiles[0], 245)
    while len(tiles) < rows * columns:
        tiles.append(blank.copy())
    storyboard = np.vstack(
        [
            np.hstack(tiles[row * columns : (row + 1) * columns])
            for row in range(rows)
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(
        ".jpg",
        storyboard,
        [int(cv2.IMWRITE_JPEG_QUALITY), 92],
    )
    if not success:
        raise RuntimeError(f"Unable to write storyboard: {output_path}")
    encoded.tofile(str(output_path))
    return {
        "sample_times": [round(value, 6) for value in times],
        "frame_metrics": summarize_frame_metrics(metric_rows),
        "storyboard": str(output_path),
    }


def quantiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"p25": None, "median": None, "p75": None}
    array = np.asarray(values, dtype=np.float64)
    return {
        "p25": round(float(np.percentile(array, 25)), 6),
        "median": round(float(np.median(array)), 6),
        "p75": round(float(np.percentile(array, 75)), 6),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze the 40-Reel haku_.photo corpus and build storyboards."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--dynamics-script", required=True)
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve()
    source_root = Path(args.source_root).expanduser().resolve()
    output_root = Path(args.output_root).expanduser().resolve()
    dynamics_script = Path(args.dynamics_script).expanduser().resolve()
    ffmpeg = Path(args.ffmpeg).expanduser().resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    items = list(manifest.get("items", []))
    if len(items) < 40:
        raise RuntimeError(f"Expected 40 manifest items, found {len(items)}")
    for required in (dynamics_script, ffmpeg):
        if not required.is_file():
            parser.error(f"required tool not found: {required}")
    output_root.mkdir(parents=True, exist_ok=True)

    dynamics_paths: dict[str, Path] = {}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(
                run_dynamics,
                item,
                source_root,
                output_root,
                dynamics_script,
                ffmpeg,
            ): str(item["post_id"])
            for item in items
        }
        for future in as_completed(futures):
            code, path = future.result()
            dynamics_paths[code] = path
            print(f"Dynamics {len(dynamics_paths)}/{len(items)}: {code}")

    reel_rows: list[dict[str, Any]] = []
    all_shot_lengths: list[float] = []
    all_cuts: list[int] = []
    all_freeze: list[float] = []
    all_sync: list[float] = []
    for index, item in enumerate(items, start=1):
        code = str(item["post_id"])
        video_path = source_root / str(item["filename"])
        dynamics = json.loads(
            dynamics_paths[code].read_text(encoding="utf-8")
        )
        times = shot_midpoints(dynamics)
        storyboard_data = make_storyboard(
            video_path,
            times,
            output_root / "storyboards" / f"{index:02d}_{code}.jpg",
        )
        direction = motion_direction(video_path)
        duration = float(dynamics["video"]["duration"])
        cut_times = [
            float(value)
            for value in dynamics["video"]["cut_detection"].get("times", [])
        ]
        boundaries = [0.0, *cut_times, duration]
        shot_lengths = [
            boundaries[position + 1] - boundaries[position]
            for position in range(len(boundaries) - 1)
        ]
        cut_count = len(cut_times)
        freeze_fraction = float(
            dynamics["video"]["freeze"].get("frame_fraction") or 0.0
        )
        sync_fraction = dynamics.get("synchronization", {}).get(
            "within_100ms_fraction"
        )
        all_shot_lengths.extend(shot_lengths)
        all_cuts.append(cut_count)
        all_freeze.append(freeze_fraction)
        if sync_fraction is not None:
            all_sync.append(float(sync_fraction))
        card = {
            "index": index,
            "reel_id": code,
            "source_filename": item["filename"],
            "original_url": item.get("original_url"),
            "taken_at": item.get("taken_at"),
            "rights": item.get("rights"),
            "duration": round(duration, 6),
            "cut_count": cut_count,
            "shot_count": cut_count + 1,
            "shot_length": quantiles(shot_lengths),
            "under_0_25_fraction": round(
                float(np.mean(np.asarray(shot_lengths) < 0.25)), 4
            ),
            "under_0_5_fraction": round(
                float(np.mean(np.asarray(shot_lengths) < 0.5)), 4
            ),
            "under_1_0_fraction": round(
                float(np.mean(np.asarray(shot_lengths) < 1.0)), 4
            ),
            "freeze_fraction": round(freeze_fraction, 4),
            "black_range_count": len(
                dynamics["video"]["flashes"].get("black_ranges", [])
            ),
            "white_range_count": len(
                dynamics["video"]["flashes"].get("white_ranges", [])
            ),
            "audio_onset_count": dynamics.get("audio", {}).get("onset_count"),
            "estimated_bpm": dynamics.get("audio", {}).get("estimated_bpm"),
            "cut_audio_sync_100ms": sync_fraction,
            "motion_direction": direction,
            "visual_metrics": storyboard_data["frame_metrics"],
            "storyboard": storyboard_data["storyboard"],
            "semantic_analysis": {
                "status": "pending_visual_review",
                "narrative": [],
                "subject_direction": [],
                "camera": [],
                "composition": [],
                "light_color_texture": [],
                "transition_meaning": [],
                "sound_image": [],
                "coverage_requirements": [],
                "confidence": None,
                "evidence": [],
            },
        }
        card_path = output_root / "reel-cards" / f"{code}.json"
        card_path.parent.mkdir(parents=True, exist_ok=True)
        card_path.write_text(
            json.dumps(card, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        reel_rows.append(card)
        print(f"Storyboard {index}/{len(items)}: {code}")

    corpus = {
        "schema_version": "1.0",
        "manifest": str(manifest_path),
        "reel_count": len(reel_rows),
        "hypothesis_set_count": 10,
        "validation_set_count": len(reel_rows) - 10,
        "totals": {
            "duration_seconds": round(
                sum(float(row["duration"]) for row in reel_rows),
                3,
            ),
            "cut_count": sum(int(row["cut_count"]) for row in reel_rows),
            "shot_count": sum(int(row["shot_count"]) for row in reel_rows),
        },
        "distributions": {
            "shot_length_seconds": quantiles(all_shot_lengths),
            "cuts_per_reel": quantiles([float(value) for value in all_cuts]),
            "freeze_fraction": quantiles(all_freeze),
            "cut_audio_sync_100ms": quantiles(all_sync),
        },
        "reels": reel_rows,
    }
    corpus_path = output_root / "corpus-metrics.json"
    corpus_path.write_text(
        json.dumps(corpus, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "success": True,
                "reel_count": len(reel_rows),
                "corpus_metrics": str(corpus_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
