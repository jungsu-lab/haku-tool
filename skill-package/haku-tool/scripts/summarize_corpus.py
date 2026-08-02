#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np


def stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "p25": None, "median": None, "p75": None}
    array = np.asarray(values, dtype=np.float64)
    return {
        "mean": round(float(np.mean(array)), 6),
        "p25": round(float(np.percentile(array, 25)), 6),
        "median": round(float(np.median(array)), 6),
        "p75": round(float(np.percentile(array, 75)), 6),
    }


def archetype(row: dict[str, Any]) -> str:
    median = float(row["shot_length"]["median"])
    fast_fraction = float(row["under_0_5_fraction"])
    duration = float(row["duration"])
    cuts = int(row["cut_count"])
    if median <= 0.5 or fast_fraction >= 0.5:
        return "flash_micro_montage"
    if duration >= 30.0 and cuts >= 20:
        return "longform_rhythmic_essay"
    if median >= 1.8 and fast_fraction <= 0.15:
        return "lyrical_long_take"
    return "mixed_rhythm_narrative"


def group_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid_sync = [
        float(row["cut_audio_sync_100ms"])
        for row in rows
        if row.get("cut_audio_sync_100ms") is not None
    ]
    return {
        "reel_count": len(rows),
        "duration_seconds": stats([float(row["duration"]) for row in rows]),
        "cuts_per_reel": stats([float(row["cut_count"]) for row in rows]),
        "cuts_per_second": stats(
            [
                float(row["cut_count"]) / max(float(row["duration"]), 1e-6)
                for row in rows
            ]
        ),
        "median_shot_seconds": stats(
            [float(row["shot_length"]["median"]) for row in rows]
        ),
        "under_0_5_fraction": stats(
            [float(row["under_0_5_fraction"]) for row in rows]
        ),
        "freeze_fraction_estimate": stats(
            [float(row["freeze_fraction"]) for row in rows]
        ),
        "black_ranges_per_reel": stats(
            [float(row["black_range_count"]) for row in rows]
        ),
        "cut_audio_sync_100ms": stats(valid_sync),
        "brightness": stats(
            [float(row["visual_metrics"]["brightness"]) for row in rows]
        ),
        "saturation": stats(
            [float(row["visual_metrics"]["saturation"]) for row in rows]
        ),
        "warmth": stats(
            [float(row["visual_metrics"]["warmth"]) for row in rows]
        ),
        "motion_direction": dict(
            Counter(row["motion_direction"]["dominant"] for row in rows)
        ),
        "archetypes": dict(Counter(archetype(row) for row in rows)),
        "device_counts": {
            "rapid_grid_reels": sum(
                1
                for row in rows
                if float(row["shot_length"]["median"]) <= 0.5
                or float(row["under_0_5_fraction"]) >= 0.5
            ),
            "mixed_micro_and_long_reels": sum(
                1
                for row in rows
                if float(row["under_0_5_fraction"]) >= 0.2
                and float(row["shot_length"]["p75"]) >= 1.0
            ),
            "black_interruption_reels": sum(
                1 for row in rows if int(row["black_range_count"]) > 0
            ),
            "strong_cut_audio_sync_reels": sum(
                1
                for row in rows
                if row.get("cut_audio_sync_100ms") is not None
                and float(row["cut_audio_sync_100ms"]) >= 0.5
            ),
        },
    }


def comparison_markdown(summary: dict[str, Any]) -> str:
    hypothesis = summary["hypothesis_set"]
    validation = summary["validation_set"]
    overall = summary["overall"]
    lines = [
        "# haku_tool 40-Reel quantitative summary",
        "",
        "## Corpus",
        "",
        f"- Hypothesis set: {hypothesis['reel_count']} Reels",
        f"- Validation set: {validation['reel_count']} Reels",
        f"- Total: {overall['reel_count']} Reels",
        "",
        "## Hypothesis vs validation",
        "",
        "| Metric | Existing 10 | New 30 | All 40 |",
        "|---|---:|---:|---:|",
    ]
    metrics = [
        ("Median shot length", "median_shot_seconds", "median"),
        ("Cuts per Reel", "cuts_per_reel", "median"),
        ("Cuts per second", "cuts_per_second", "median"),
        ("Shots under 0.5 s", "under_0_5_fraction", "median"),
        ("Freeze estimate", "freeze_fraction_estimate", "median"),
        ("Black ranges per Reel", "black_ranges_per_reel", "median"),
        ("Cut-audio sync within 100 ms", "cut_audio_sync_100ms", "median"),
    ]
    for label, key, field in metrics:
        values = [
            hypothesis[key][field],
            validation[key][field],
            overall[key][field],
        ]
        lines.append(
            f"| {label} | {values[0]} | {values[1]} | {values[2]} |"
        )
    lines.extend(
        [
            "",
            "## Device coverage",
            "",
            "| Device | Existing 10 | New 30 | All 40 |",
            "|---|---:|---:|---:|",
        ]
    )
    device_labels = {
        "rapid_grid_reels": "Rapid microcut grid",
        "mixed_micro_and_long_reels": "Micro/long duration contrast",
        "black_interruption_reels": "Black-frame interruption",
        "strong_cut_audio_sync_reels": "Strong cut-audio sync",
    }
    for key, label in device_labels.items():
        lines.append(
            f"| {label} | {hypothesis['device_counts'][key]} | "
            f"{validation['device_counts'][key]} | "
            f"{overall['device_counts'][key]} |"
        )
    lines.extend(
        [
            "",
            "Freeze detection includes naturally static frames and must be confirmed visually.",
            "Automated archetypes are review candidates, not final semantic labels.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare the original 10-Reel hypotheses against 30 new Reels."
    )
    parser.add_argument("--corpus-metrics", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    corpus_path = Path(args.corpus_metrics).expanduser().resolve()
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    rows = list(corpus["reels"])
    hypothesis = [row for row in rows if int(row["index"]) <= 10]
    validation = [row for row in rows if int(row["index"]) > 10]
    summary = {
        "schema_version": "1.0",
        "hypothesis_set": group_summary(hypothesis),
        "validation_set": group_summary(validation),
        "overall": group_summary(rows),
        "limitations": [
            "Freeze estimates include naturally static source frames.",
            "Cut detection is consistent across the corpus but still threshold-based.",
            "Narrative, blocking, shot scale, and transition meaning require visual review.",
        ],
    }
    output_json = Path(args.output_json).expanduser().resolve()
    output_md = Path(args.output_md).expanduser().resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    output_md.write_text(comparison_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
