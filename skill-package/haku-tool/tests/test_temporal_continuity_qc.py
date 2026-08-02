from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from temporal_continuity_qc import (  # noqa: E402
    ANALYSIS_HEIGHT,
    ANALYSIS_WIDTH,
    duplicate_runs,
    estimate_scale_steps,
    mean_absolute_difference,
    motion_spikes,
    near_static_runs,
)


def patterned_frame() -> bytes:
    return bytes(
        max(
            0,
            min(
                255,
                int(
                    118
                    + 45 * math.sin(x / 18)
                    + 35 * math.cos(y / 12)
                    + 30 * math.sin((x + y) / 22)
                    + (55 if (x - 45) ** 2 + (y - 35) ** 2 < 13**2 else 0)
                    + (-60 if 100 < x < 135 and 50 < y < 72 else 0)
                ),
            ),
        )
        for y in range(ANALYSIS_HEIGHT)
        for x in range(ANALYSIS_WIDTH)
    )


def zoom_frame(source: bytes, scale: float) -> bytes:
    center_x = (ANALYSIS_WIDTH - 1) / 2
    center_y = (ANALYSIS_HEIGHT - 1) / 2
    output = bytearray(ANALYSIS_WIDTH * ANALYSIS_HEIGHT)
    for y in range(ANALYSIS_HEIGHT):
        for x in range(ANALYSIS_WIDTH):
            source_x = round((x - center_x) / scale + center_x)
            source_y = round((y - center_y) / scale + center_y)
            source_x = max(0, min(ANALYSIS_WIDTH - 1, source_x))
            source_y = max(0, min(ANALYSIS_HEIGHT - 1, source_y))
            output[y * ANALYSIS_WIDTH + x] = source[
                source_y * ANALYSIS_WIDTH + source_x
            ]
    return bytes(output)


class TemporalContinuityQcTest(unittest.TestCase):
    def test_duplicate_runs_include_terminal_padding(self) -> None:
        hashes = ["a", "b", "c", "d", "d", "d"]

        runs = duplicate_runs(hashes)

        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["start_frame"], 3)
        self.assertEqual(runs[0]["end_frame_inclusive"], 5)
        self.assertEqual(runs[0]["repeated_transitions"], 2)

    def test_motion_spike_is_suppressed_only_at_recorded_event(self) -> None:
        differences = [2.0] * 14
        differences[6] = 24.0

        visible = motion_spikes(differences, set(), fps=25.0)
        allowed = motion_spikes(differences, {7}, fps=25.0)

        self.assertEqual([item["frame"] for item in visible], [7])
        self.assertEqual(allowed, [])

    def test_near_static_run_survives_codec_chroma_variation(self) -> None:
        self.assertEqual(
            [
                {
                    "start_frame": 2,
                    "end_frame_inclusive": 6,
                    "repeated_transitions": 4,
                    "identical_frame_count": 5,
                }
            ],
            near_static_runs([2.0, 1.0, 0.0, 0.02, 0.0, 0.01]),
        )

    def test_four_percent_zoom_step_is_a_review_candidate(self) -> None:
        source = patterned_frame()
        zoomed = zoom_frame(source, 1.04)
        differences = [mean_absolute_difference(source, zoomed)]

        jumps, resets = estimate_scale_steps(
            [source, zoomed], differences, set(), fps=25.0
        )

        self.assertTrue(jumps)
        self.assertGreaterEqual(abs(jumps[0]["estimated_scale_step"] - 1.0), 0.02)
        self.assertEqual(resets, [])


if __name__ == "__main__":
    unittest.main()
