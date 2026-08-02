from __future__ import annotations

import copy
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill-package" / "haku-tool" / "scripts" / "validate_music_event_map.py"
SPEC = importlib.util.spec_from_file_location("validate_music_event_map", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def canonical() -> dict:
    return {
        "schema_version": "1.0",
        "audio_rights_manifest": "audio-rights.json",
        "audio_file_sha256": "A" * 64,
        "track_source_in_seconds": 4.0,
        "track_source_out_seconds": 16.0,
        "analysis_method": ["waveform", "direct_listening"],
        "events": [
            {
                "event_id": "music-001",
                "track_seconds": 4.0,
                "timeline_seconds": 0.0,
                "type": "phrase_start",
                "observation": "A new instrumental phrase opens cleanly.",
                "visual_response": "in_frame_event",
                "target_visual_event_id": "visual-001",
                "intentional_offset_ms": 0,
                "confidence": "high",
            }
        ],
    }


assert MODULE.validate(canonical(), {"visual-001"}) == []
mutations = []
bad = canonical(); bad["analysis_method"] = ["waveform"]; mutations.append(bad)
bad = canonical(); bad["audio_file_sha256"] = "short"; mutations.append(bad)
bad = canonical(); bad["events"][0]["target_visual_event_id"] = "missing"; mutations.append(bad)
bad = canonical(); bad["events"][0]["visual_response"] = "none"; mutations.append(bad)
bad = canonical(); bad["events"][0]["observation"] = ""; mutations.append(bad)
bad = canonical(); bad["track_source_out_seconds"] = 3.0; mutations.append(bad)
for mutation in mutations:
    assert MODULE.validate(copy.deepcopy(mutation), {"visual-001"}), mutation
print("music event map guardrails: canonical accepted; six empty or invalid interaction maps rejected")
