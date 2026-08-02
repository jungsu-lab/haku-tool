from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import statistics
import subprocess
from pathlib import Path
from typing import Any, Iterable


ANALYSIS_WIDTH = 160
ANALYSIS_HEIGHT = 90
SCALE_WIDTH = 80
SCALE_HEIGHT = 45
SCALE_CANDIDATES = (0.96, 0.98, 1.0, 1.02, 1.04)
NEAR_STATIC_MAD_THRESHOLD = 0.1
NEAR_STATIC_FAILURE_TRANSITIONS = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Detect repeated frames, terminal padding, motion spikes, and "
            "single-frame scale jumps without inferring aesthetic quality."
        )
    )
    parser.add_argument("video", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path)
    parser.add_argument("--ffprobe", type=Path)
    parser.add_argument("--render-report", type=Path)
    parser.add_argument("--review-manifest", type=Path)
    parser.add_argument("--variant", choices=("plain", "proof"))
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--no-strips", action="store_true")
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


def run(command: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
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
    return completed


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def parse_rate(value: str) -> float:
    numerator, separator, denominator = value.partition("/")
    if not separator:
        return float(value)
    denominator_value = float(denominator)
    if denominator_value == 0:
        raise ValueError(f"invalid frame rate: {value}")
    return float(numerator) / denominator_value


def probe_video(ffprobe: Path, video: Path) -> dict[str, Any]:
    payload = json.loads(
        run(
            [
                str(ffprobe),
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-count_frames",
                "-show_entries",
                "stream=width,height,r_frame_rate,avg_frame_rate,nb_read_frames:format=duration",
                "-of",
                "json",
                str(video),
            ]
        ).stdout
    )
    stream = payload["streams"][0]
    fps = parse_rate(stream.get("avg_frame_rate") or stream["r_frame_rate"])
    frames = int(stream.get("nb_read_frames") or round(float(payload["format"]["duration"]) * fps))
    return {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "fps": fps,
        "frames": frames,
        "duration_seconds": float(payload["format"]["duration"]),
    }


def decoded_frame_hashes(ffmpeg: Path, video: Path) -> list[str]:
    completed = run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-nostdin",
            "-threads",
            "2",
            "-i",
            str(video),
            "-map",
            "0:v:0",
            "-an",
            "-f",
            "framemd5",
            "-",
        ]
    )
    hashes: list[str] = []
    for line in completed.stdout.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = [field.strip() for field in stripped.split(",")]
        if len(fields) >= 6:
            hashes.append(fields[-1])
    return hashes


def duplicate_runs(hashes: list[str]) -> list[dict[str, int]]:
    runs: list[dict[str, int]] = []
    start: int | None = None
    for frame in range(1, len(hashes)):
        repeated = hashes[frame] == hashes[frame - 1]
        if repeated and start is None:
            start = frame - 1
        if start is not None and (not repeated or frame == len(hashes) - 1):
            end = frame if repeated and frame == len(hashes) - 1 else frame - 1
            runs.append(
                {
                    "start_frame": start,
                    "end_frame_inclusive": end,
                    "repeated_transitions": end - start,
                    "identical_frame_count": end - start + 1,
                }
            )
            start = None
    return runs


def near_static_runs(differences: list[float]) -> list[dict[str, int]]:
    """Find visually static gray-frame runs that codecs may chroma-alternate."""
    runs: list[dict[str, int]] = []
    start: int | None = None
    for transition_index, difference in enumerate(differences, start=1):
        repeated = difference <= NEAR_STATIC_MAD_THRESHOLD
        if repeated and start is None:
            start = transition_index - 1
        is_last = transition_index == len(differences)
        if start is not None and (not repeated or is_last):
            end = transition_index if repeated and is_last else transition_index - 1
            runs.append(
                {
                    "start_frame": start,
                    "end_frame_inclusive": end,
                    "repeated_transitions": end - start,
                    "identical_frame_count": end - start + 1,
                }
            )
            start = None
    return runs


def read_gray_frames(ffmpeg: Path, video: Path) -> list[bytes]:
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-threads",
        "2",
        "-i",
        str(video),
        "-an",
        "-vf",
        f"scale={ANALYSIS_WIDTH}:{ANALYSIS_HEIGHT}:flags=area,format=gray",
        "-pix_fmt",
        "gray",
        "-f",
        "rawvideo",
        "-",
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "OMP_NUM_THREADS": "2"},
    )
    assert process.stdout is not None
    frame_size = ANALYSIS_WIDTH * ANALYSIS_HEIGHT
    frames: list[bytes] = []
    while True:
        data = process.stdout.read(frame_size)
        if not data:
            break
        if len(data) != frame_size:
            process.kill()
            raise RuntimeError("ffmpeg returned a partial raw frame")
        frames.append(data)
    stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
    return_code = process.wait(timeout=300)
    if return_code:
        raise RuntimeError(f"raw frame decode failed: {stderr}")
    return frames


def mean_absolute_difference(left: bytes, right: bytes) -> float:
    return sum(abs(a - b) for a, b in zip(left, right)) / len(left)


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def allowed_event_frames(
    report_path: Path | None,
    manifest_path: Path | None,
    variant: str | None,
    video: Path,
) -> tuple[set[int], list[dict[str, Any]], str | None, list[dict[str, Any]]]:
    frames: set[int] = set()
    evidence: list[dict[str, Any]] = []
    declared_black_breaths: list[dict[str, Any]] = []
    resolved_variant = variant
    if report_path and report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if resolved_variant is None:
            for candidate in ("plain", "proof"):
                candidate_path = report.get(candidate, {}).get("path")
                if candidate_path and Path(candidate_path).resolve() == video.resolve():
                    resolved_variant = candidate
                    break
        if resolved_variant in {"plain", "proof"}:
            cursor = 0
            segments = report.get(resolved_variant, {}).get("segments", [])
            for index, segment in enumerate(segments):
                segment_start = cursor
                segment_frames = int(segment.get("frames", 0))
                black_breath = segment.get("intentional_black_breath_frames")
                if isinstance(black_breath, list) and len(black_breath) == 2:
                    start, end = [int(value) for value in black_breath]
                    declared_black_breaths.append(
                        {
                            "start_frame": segment_start + start,
                            "end_frame_exclusive": segment_start + end,
                            "segment_id": segment.get("segment_id", f"segment-{index}"),
                            "declared_range_relative_frames": [start, end],
                        }
                    )
                    evidence.append(
                        {
                            "frame": segment_start + start,
                            "kind": "declared_intentional_black_breath",
                            "id": f"report-{resolved_variant}-{segment.get('segment_id', index)}-black-breath",
                        }
                    )
                cursor += segment_frames
                if index < len(segments) - 1:
                    frames.add(cursor)
                    evidence.append(
                        {
                            "frame": cursor,
                            "kind": "segment_boundary",
                            "id": f"report-{resolved_variant}-{segment.get('segment_id', cursor)}-end",
                        }
                    )
    if manifest_path and manifest_path.is_file() and resolved_variant == "proof":
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for item in manifest.get("boundary_and_internal_event_evidence", []):
            frame = int(item["frame"])
            frames.add(frame)
            evidence.append(
                {
                    "frame": frame,
                    "kind": item.get("kind", "recorded_event"),
                    "id": item.get("id", f"manifest-event-{frame}"),
                }
            )
    return frames, evidence, resolved_variant, declared_black_breaths


def run_within_declared_black_breath(
    run: dict[str, Any], declared_black_breaths: list[dict[str, Any]]
) -> bool:
    return any(
        int(item["start_frame"]) <= int(run["start_frame"])
        and int(run["end_frame_inclusive"]) < int(item["end_frame_exclusive"])
        for item in declared_black_breaths
    )


def near_allowed(frame: int, allowed: set[int], radius: int = 1) -> bool:
    return any(abs(frame - event_frame) <= radius for event_frame in allowed)


def motion_spikes(
    differences: list[float], allowed: set[int], fps: float
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, value in enumerate(differences, start=1):
        if near_allowed(index, allowed, radius=1):
            continue
        neighbors = [
            differences[position - 1]
            for position in range(max(1, index - 5), min(len(differences), index + 5) + 1)
            if position != index and not near_allowed(position, allowed, radius=1)
        ]
        if len(neighbors) < 3:
            continue
        local_median = statistics.median(neighbors)
        threshold = max(8.0, local_median * 4.0 + 2.0)
        if value < threshold or value - local_median < 6.0:
            continue
        candidates.append(
            {
                "frame": index,
                "seconds": index / fps,
                "mad_8bit": round(value, 4),
                "local_median_8bit": round(local_median, 4),
                "ratio": round(value / max(0.01, local_median), 3),
                "classification": "review_candidate_not_automatic_failure",
            }
        )
    return sorted(candidates, key=lambda item: item["ratio"], reverse=True)


def small_frame(frame: bytes) -> bytes:
    x_step = ANALYSIS_WIDTH / SCALE_WIDTH
    y_step = ANALYSIS_HEIGHT / SCALE_HEIGHT
    return bytes(
        frame[min(ANALYSIS_HEIGHT - 1, int(y * y_step)) * ANALYSIS_WIDTH + min(ANALYSIS_WIDTH - 1, int(x * x_step))]
        for y in range(SCALE_HEIGHT)
        for x in range(SCALE_WIDTH)
    )


def scale_maps() -> tuple[list[int], dict[tuple[float, int, int], list[int]]]:
    margin = 6
    output_indices = [
        y * SCALE_WIDTH + x
        for y in range(margin, SCALE_HEIGHT - margin)
        for x in range(margin, SCALE_WIDTH - margin)
    ]
    center_x = (SCALE_WIDTH - 1) / 2
    center_y = (SCALE_HEIGHT - 1) / 2
    mappings: dict[tuple[float, int, int], list[int]] = {}
    for scale in SCALE_CANDIDATES:
        for shift_y in (-1, 0, 1):
            for shift_x in (-1, 0, 1):
                mapped: list[int] = []
                for output_index in output_indices:
                    y, x = divmod(output_index, SCALE_WIDTH)
                    source_x = round((x - center_x) / scale + center_x + shift_x)
                    source_y = round((y - center_y) / scale + center_y + shift_y)
                    source_x = max(0, min(SCALE_WIDTH - 1, source_x))
                    source_y = max(0, min(SCALE_HEIGHT - 1, source_y))
                    mapped.append(source_y * SCALE_WIDTH + source_x)
                mappings[(scale, shift_x, shift_y)] = mapped
    return output_indices, mappings


def normalized_mapping_score(
    previous: bytes,
    current: bytes,
    output_indices: list[int],
    mapped_indices: list[int],
) -> float:
    previous_values = [previous[index] for index in mapped_indices]
    current_values = [current[index] for index in output_indices]
    previous_mean = sum(previous_values) / len(previous_values)
    current_mean = sum(current_values) / len(current_values)
    variance = (
        sum((value - current_mean) ** 2 for value in current_values)
        + sum((value - previous_mean) ** 2 for value in previous_values)
    ) / (2 * len(current_values))
    normalization = max(8.0, math.sqrt(variance))
    return (
        sum(
            abs((left - previous_mean) - (right - current_mean))
            for left, right in zip(previous_values, current_values)
        )
        / len(current_values)
        / normalization
    )


def estimate_scale_steps(
    frames: list[bytes], differences: list[float], allowed: set[int], fps: float
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    output_indices, mappings = scale_maps()
    reduced = [small_frame(frame) for frame in frames]
    estimates: list[dict[str, Any]] = []
    for frame_index in range(1, len(reduced)):
        if near_allowed(frame_index, allowed, radius=1):
            continue
        motion = differences[frame_index - 1]
        if motion < 0.5 or motion > 30.0:
            continue
        scores: dict[float, float] = {}
        for scale in SCALE_CANDIDATES:
            scores[scale] = min(
                normalized_mapping_score(
                    reduced[frame_index - 1],
                    reduced[frame_index],
                    output_indices,
                    mappings[(scale, shift_x, shift_y)],
                )
                for shift_y in (-1, 0, 1)
                for shift_x in (-1, 0, 1)
            )
        best_scale = min(scores, key=scores.get)
        unity_score = scores[1.0]
        best_score = scores[best_scale]
        improvement = (unity_score - best_score) / max(0.0001, unity_score)
        if abs(best_scale - 1.0) < 0.019 or improvement < 0.12:
            continue
        estimates.append(
            {
                "frame": frame_index,
                "seconds": frame_index / fps,
                "estimated_scale_step": best_scale,
                "improvement_over_unity": round(improvement, 4),
                "unity_score": round(unity_score, 4),
                "best_score": round(best_score, 4),
                "classification": "review_candidate_not_proof_of_digital_zoom",
            }
        )
    by_frame = {int(item["frame"]): item for item in estimates}
    resets: list[dict[str, Any]] = []
    for frame, current in by_frame.items():
        following = by_frame.get(frame + 1)
        if not following:
            continue
        current_delta = float(current["estimated_scale_step"]) - 1.0
        following_delta = float(following["estimated_scale_step"]) - 1.0
        if current_delta * following_delta >= 0:
            continue
        resets.append(
            {
                "frame": frame,
                "seconds": frame / fps,
                "first_scale_step": current["estimated_scale_step"],
                "next_scale_step": following["estimated_scale_step"],
                "classification": "high_priority_scale_reset_review_candidate",
            }
        )
    return estimates, resets


def annotate_runs(runs: list[dict[str, int]], fps: float) -> list[dict[str, Any]]:
    return [
        {
            **item,
            "start_seconds": item["start_frame"] / fps,
            "end_seconds": item["end_frame_inclusive"] / fps,
            "duration_seconds": item["identical_frame_count"] / fps,
        }
        for item in runs
    ]


def candidate_frames_for_strips(report: dict[str, Any]) -> list[tuple[int, str]]:
    candidates: list[tuple[int, str]] = []
    for item in report["duplicate_analysis"]["runs"]:
        candidates.append((int(item["start_frame"]), "duplicate"))
    for item in report["near_static_analysis"]["runs"]:
        candidates.append((int(item["start_frame"]), "near-static"))
    for item in report["motion_analysis"]["spike_candidates"][:8]:
        candidates.append((int(item["frame"]), "motion-spike"))
    for item in report["scale_analysis"]["reset_candidates"][:4]:
        candidates.append((int(item["frame"]), "scale-reset"))
    for item in report["scale_analysis"]["jump_candidates"][:8]:
        candidates.append((int(item["frame"]), "scale-jump"))
    result: list[tuple[int, str]] = []
    for frame, kind in candidates:
        if any(abs(frame - existing_frame) <= 2 for existing_frame, _ in result):
            continue
        result.append((frame, kind))
        if len(result) >= 12:
            break
    return result


def render_candidate_strips(
    ffmpeg: Path,
    video: Path,
    evidence_dir: Path,
    candidates: Iterable[tuple[int, str]],
    total_frames: int,
) -> list[dict[str, Any]]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    strips: list[dict[str, Any]] = []
    for index, (frame, kind) in enumerate(candidates, start=1):
        start = max(0, frame - 4)
        end = min(total_frames - 1, frame + 4)
        count = end - start + 1
        target = evidence_dir / f"{index:02d}-{kind}-frame-{frame}.jpg"
        run(
            [
                str(ffmpeg),
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-threads",
                "2",
                "-i",
                str(video),
                "-an",
                "-vf",
                (
                    f"select='between(n\\,{start}\\,{end})',"
                    "scale=220:-2:flags=lanczos,"
                    "drawbox=x=0:y=0:w=iw:h=ih:color=white:t=3,"
                    "drawtext=text='frame %{n}':x=7:y=7:fontsize=15:"
                    "fontcolor=white:borderw=2:bordercolor=black,"
                    f"tile={count}x1:padding=3:margin=3:color=0x303030"
                ),
                "-frames:v",
                "1",
                "-y",
                str(target),
            ]
        )
        strips.append(
            {
                "frame": frame,
                "kind": kind,
                "range_frames_inclusive": [start, end],
                "path": str(target),
            }
        )
    return strips


def analyze_temporal_continuity(
    *,
    ffmpeg: Path,
    ffprobe: Path,
    video: Path,
    render_report: Path | None = None,
    review_manifest: Path | None = None,
    variant: str | None = None,
    evidence_dir: Path | None = None,
    render_strips: bool = True,
) -> dict[str, Any]:
    video = video.resolve()
    probe = probe_video(ffprobe, video)
    hashes = decoded_frame_hashes(ffmpeg, video)
    frames = read_gray_frames(ffmpeg, video)
    if len(hashes) != len(frames):
        raise ValueError(
            f"decoded frame count mismatch: framemd5={len(hashes)} raw={len(frames)}"
        )
    allowed, allowed_evidence, resolved_variant, declared_black_breaths = allowed_event_frames(
        render_report.resolve() if render_report else None,
        review_manifest.resolve() if review_manifest else None,
        variant,
        video,
    )
    differences = [
        mean_absolute_difference(frames[index - 1], frames[index])
        for index in range(1, len(frames))
    ]
    runs = annotate_runs(duplicate_runs(hashes), probe["fps"])
    static_runs = annotate_runs(near_static_runs(differences), probe["fps"])
    terminal_run = runs[-1] if runs and runs[-1]["end_frame_inclusive"] == len(frames) - 1 else None
    terminal_static_run = (
        static_runs[-1]
        if static_runs
        and static_runs[-1]["end_frame_inclusive"] == len(frames) - 1
        else None
    )
    spikes = motion_spikes(differences, allowed, probe["fps"])
    scale_jumps, scale_resets = estimate_scale_steps(
        frames, differences, allowed, probe["fps"]
    )
    declared_duplicate_runs = [
        item
        for item in runs
        if run_within_declared_black_breath(item, declared_black_breaths)
    ]
    unexcused_duplicate_runs = [
        item
        for item in runs
        if not run_within_declared_black_breath(item, declared_black_breaths)
    ]
    long_duplicate_runs = [
        item for item in unexcused_duplicate_runs if int(item["repeated_transitions"]) >= 2
    ]
    automatic_failures: list[str] = []
    if (
        terminal_run
        and not run_within_declared_black_breath(terminal_run, declared_black_breaths)
        and int(terminal_run["repeated_transitions"]) >= 1
    ):
        automatic_failures.append("terminal_identical_frame_padding")
    if (
        terminal_static_run
        and int(terminal_static_run["repeated_transitions"])
        >= NEAR_STATIC_FAILURE_TRANSITIONS
    ):
        automatic_failures.append("terminal_near_static_padding")
    if long_duplicate_runs:
        automatic_failures.append("consecutive_identical_frame_run")
    review_reasons: list[str] = []
    if unexcused_duplicate_runs:
        review_reasons.append("isolated_or_short_identical_frame_pairs")
    if declared_duplicate_runs:
        review_reasons.append("declared_intentional_black_breath_requires_visual_review")
    if spikes:
        review_reasons.append("motion_spike_candidates")
    if scale_resets:
        review_reasons.append("scale_reset_candidates")
    elif scale_jumps:
        review_reasons.append("scale_jump_candidates")
    verdict = (
        "fail"
        if automatic_failures
        else "review_required"
        if review_reasons
        else "pass"
    )
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "video": str(video),
        "video_sha256": sha256(video),
        "variant": resolved_variant or "unresolved",
        "probe": probe,
        "analysis_resolution": [ANALYSIS_WIDTH, ANALYSIS_HEIGHT],
        "allowed_edit_events": {
            "frames": sorted(allowed),
            "evidence": allowed_evidence,
            "exclusion_radius_frames": 1,
            "declared_intentional_black_breaths": declared_black_breaths,
        },
        "duplicate_analysis": {
            "decoded_full_frame_hash": "framemd5",
            "runs": runs,
            "declared_intentional_black_breath_runs": declared_duplicate_runs,
            "unexcused_runs": unexcused_duplicate_runs,
            "long_runs": long_duplicate_runs,
            "terminal_padding_candidate": terminal_run,
        },
        "near_static_analysis": {
            "metric": "mean_absolute_difference_on_160x90_gray_frames",
            "threshold_8bit": NEAR_STATIC_MAD_THRESHOLD,
            "minimum_terminal_failure_transitions": NEAR_STATIC_FAILURE_TRANSITIONS,
            "runs": static_runs,
            "terminal_padding_candidate": terminal_static_run,
            "limitation": (
                "Only terminal runs of at least three transitions fail automatically; "
                "short or internal stillness remains direct-review evidence."
            ),
        },
        "motion_analysis": {
            "metric": "mean_absolute_difference_on_160x90_gray_frames",
            "median_8bit": round(percentile(differences, 0.5), 4),
            "p95_8bit": round(percentile(differences, 0.95), 4),
            "maximum_8bit": round(max(differences, default=0.0), 4),
            "spike_candidates": spikes,
        },
        "scale_analysis": {
            "method": "brightness_normalized_center_scale_search_with_small_translation",
            "tested_scale_steps": list(SCALE_CANDIDATES),
            "jump_candidates": scale_jumps,
            "reset_candidates": scale_resets,
            "limitation": (
                "A candidate may come from physical camera or subject motion. "
                "It is not proof of digital zoom until the strip and recipe are reviewed."
            ),
        },
        "automated_verdict": {
            "status": verdict,
            "automatic_failures": automatic_failures,
            "review_reasons": review_reasons,
            "promotion_increment": 0,
            "user_verdict": "pending",
        },
        "evidence_strips": [],
        "main_agent_review_required": True,
        "full_playback_reviewed": False,
        "guardrail": (
            "This report detects technical continuity candidates only. It does not "
            "prove directing quality, Haku identity, aesthetic success, user acceptance, "
            "or full-speed playback review."
        ),
    }
    if render_strips and evidence_dir is not None:
        report["evidence_strips"] = render_candidate_strips(
            ffmpeg,
            video,
            evidence_dir.resolve(),
            candidate_frames_for_strips(report),
            len(frames),
        )
    return report


def attach_temporal_continuity_qc(
    *,
    ffmpeg: Path,
    ffprobe: Path,
    render_report: Path,
    review_manifest: Path | None = None,
    evidence_root: Path | None = None,
    render_strips: bool = True,
) -> dict[str, dict[str, Any]]:
    """Attach plain/proof continuity reports without changing human verdicts."""
    render_report = render_report.resolve()
    payload = json.loads(render_report.read_text(encoding="utf-8"))
    root = (evidence_root or render_report.parent / "temporal-qc").resolve()
    attached: dict[str, dict[str, Any]] = {}
    for variant in ("plain", "proof"):
        variant_payload = payload.get(variant)
        if not isinstance(variant_payload, dict):
            raise ValueError(f"render report is missing {variant}")
        raw_video = variant_payload.get("path")
        video = Path(raw_video) if raw_video else render_report.parent / f"{variant}.mp4"
        if not video.is_absolute():
            video = (render_report.parent / video).resolve()
        report = analyze_temporal_continuity(
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
            video=video,
            render_report=render_report,
            review_manifest=review_manifest,
            variant=variant,
            evidence_dir=root / variant,
            render_strips=render_strips,
        )
        variant_payload["temporal_continuity_qc"] = report
        attached[variant] = report
        root.mkdir(parents=True, exist_ok=True)
        (root / f"{variant}.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    payload["temporal_continuity_gate"] = {
        "status": (
            "fail"
            if any(
                report["automated_verdict"]["status"] == "fail"
                for report in attached.values()
            )
            else "review_required"
            if any(
                report["automated_verdict"]["status"] == "review_required"
                for report in attached.values()
            )
            else "pass"
        ),
        "checked_variants": ["plain", "proof"],
        "fail_closed": True,
        "note": (
            "Automatic failure blocks review readiness. Candidate-only findings still "
            "require direct strip review and never imply aesthetic success."
        ),
    }
    render_report.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return attached


def main() -> int:
    args = parse_args()
    ffmpeg = resolve_binary(args.ffmpeg, "ffmpeg")
    ffprobe = resolve_binary(args.ffprobe, "ffprobe")
    report_path = args.render_report.resolve() if args.render_report else None
    manifest_path = args.review_manifest.resolve() if args.review_manifest else None
    if manifest_path is None and report_path is not None:
        candidate = report_path.parent / "review-auto" / "review-manifest.json"
        if candidate.is_file():
            manifest_path = candidate
    evidence_dir = args.evidence_dir
    if evidence_dir is None:
        evidence_dir = args.output.resolve().parent / f"{args.video.stem}-temporal-evidence"
    report = analyze_temporal_continuity(
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
        video=args.video,
        render_report=report_path,
        review_manifest=manifest_path,
        variant=args.variant,
        evidence_dir=evidence_dir,
        render_strips=not args.no_strips,
    )
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "success": True,
                "output": str(args.output.resolve()),
                "status": report["automated_verdict"]["status"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
