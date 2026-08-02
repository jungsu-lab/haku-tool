from __future__ import annotations

import copy
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill-package" / "haku-tool" / "scripts" / "validate_source_manifest.py"
SPEC = importlib.util.spec_from_file_location("validate_source_manifest", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def canonical() -> dict:
    return {
        "schema_version": "1.0", "session_id": "fixture-session",
        "rights_basis": {"provider": "Pexels", "creator": "Fixture", "license_url": "https://www.pexels.com/license/", "allowed_use": "proof_edit"},
        "capture_world": {"world_id": "world-001", "subject_identity": "same person", "location": "flower field", "time_of_day": "daylight", "weather": "clear", "lens_character": "consistent medium-wide stock coverage", "color_temperature": "warm daylight", "palette": ["yellow", "green"], "same_world_claim": "Same subject, field, daylight and palette."},
        "sources": [{
            "source_clip_id": "clip-001", "file": "clip.mp4", "sha256": "A" * 64,
            "page_url": "https://example.com/clip", "license_url": "https://www.pexels.com/license/",
            "creator": "Fixture", "duration_seconds": 10.0, "width": 1920, "height": 1080,
            "fps": 25, "audio_stream_present": False, "single_take": True,
            "existing_edit_detected": False,
            "hidden_retake_review": {"method": "dense_storyboard_and_boundary_review", "status": "no_detected_splice", "limitations": "Full-speed playback remains a separate review gate."},
            "semantic_role": "environment premise"
        }]
    }


assert MODULE.validate(canonical()) == []
mutations = []
bad = canonical(); bad["sources"][0]["sha256"] = "short"; mutations.append(bad)
bad = canonical(); bad["sources"][0]["single_take"] = False; mutations.append(bad)
bad = canonical(); bad["sources"][0]["hidden_retake_review"]["status"] = "uncertain"; mutations.append(bad)
bad = canonical(); bad["capture_world"]["same_world_claim"] = ""; mutations.append(bad)
for mutation in mutations:
    assert MODULE.validate(copy.deepcopy(mutation)), mutation
print("source manifest guardrails: canonical accepted; four provenance gaps rejected")
