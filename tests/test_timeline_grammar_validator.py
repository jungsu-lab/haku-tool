from __future__ import annotations

import copy
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill-package" / "haku-tool" / "scripts" / "validate_timeline_grammar.py"
SPEC = importlib.util.spec_from_file_location("validate_timeline_grammar", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def canonical() -> dict:
    return {
        "schema_version": "1.0", "reel_id": "fixture", "account": "@haku_.photo",
        "source_duration_seconds": 3.0, "audio_policy": "deferred_by_user",
        "events": [{
            "event_id": "event-001", "start_seconds": 2.1, "end_seconds": 2.6,
            "timecode_display": "00:02.1~00:02.6", "observation": "제품이 중앙에 등장한다.", "inference": "제품 공개를 강조한다.",
            "narrative": {"stage": "climax", "function": "product reveal"},
            "shot": {"shot_type": "hero", "subject": "product", "framing": "CU", "camera_angle": "eye-level", "camera_motion": "source locked", "shot_duration_seconds": 0.5},
            "cut": {"cut_type": "hard", "cut_reason": "reveal", "incoming_motion": "none", "outgoing_motion": "none", "continuity": "center anchor"},
            "timing": {"pace": "fast", "rhythm": "accent", "beat_position": "not_reviewed", "pause_seconds": 0.0, "speed_change": "none"},
            "transition": {"transition_type": "none", "duration_seconds": 0.0, "direction": "none", "visual_anchor": "product center", "sound_anchor": "not_reviewed"},
            "text": {"content": "", "font_style": "none", "position": "none", "emphasis": "none", "animation": "none", "duration_seconds": 0.0},
            "color": {"exposure": "stable", "contrast": "medium", "saturation": "medium", "temperature": "neutral", "palette": ["brown"], "mood": "confident"},
            "audio": {"status": "deferred_by_user", "dialogue": "not_reviewed", "music": "not_reviewed", "sfx": "not_reviewed", "ambience": "not_reviewed", "beat": "not_reviewed", "volume_curve": "not_reviewed"},
            "motion": {"zoom": "105% to 125%", "pan": "none", "shake": "none", "tracking": "none", "easing": "ease-out", "motion_blur": "unknown"},
            "purpose": {"primary": "product_emphasis", "effect_name": "fast_push_in", "when_used": "제품 등장", "applied_scene": "hero shot", "why_used": "등장 강조", "viewer_feeling": ["강렬함", "확신"]},
            "operator_links": ["experience-before-product"], "confidence": "high"
        }]
    }


def canonical_v11() -> dict:
    payload = canonical()
    payload["schema_version"] = "1.1"
    payload["artifact_type"] = "proof_edit"
    payload["timeline_duration_seconds"] = 3.0
    payload["timeline_fps"] = 20
    payload["events"][0]["source_mapping"] = {
        "source_clip_id": "clip-001",
        "source_path": "source/clip-001.mp4",
        "source_sha256": "A" * 64,
        "source_fps": 20,
        "source_in_seconds": 2.1,
        "source_out_seconds": 2.6,
        "source_frame_in": 42,
        "source_frame_out_exclusive": 52,
        "output_in_seconds": 2.1,
        "output_out_seconds": 2.6,
        "output_frame_in": 42,
        "output_frame_out_exclusive": 52,
        "retime": "none",
    }
    payload["toolchain"] = {
        "primary_editor": "ffmpeg deterministic proof renderer",
        "secondary_tools": ["dense frame sheets"],
        "why_this_toolchain": "Keep frame counts and plain/proof comparison deterministic."
    }
    payload["narrative_arc"] = {
        "hook": {"status": "not_applicable", "event_ids": [], "reason": "Fixture contains only the reveal event."},
        "setup": {"status": "not_applicable", "event_ids": [], "reason": "Fixture contains only the reveal event."},
        "buildup": {"status": "not_applicable", "event_ids": [], "reason": "Fixture contains only the reveal event."},
        "climax": {"status": "present", "event_ids": ["event-001"], "reason": "The product reveal is the climax."},
        "resolution": {"status": "not_applicable", "event_ids": [], "reason": "Fixture ends at the reveal."},
        "cta": {"status": "not_applicable", "event_ids": [], "reason": "No advertising CTA is present in this fixture."}
    }
    return payload


assert MODULE.validate(canonical()) == []
assert MODULE.validate(canonical_v11()) == []
mutations = []
bad = canonical(); bad["events"][0]["end_seconds"] = 3.5; mutations.append(bad)
bad = canonical(); bad["events"][0]["purpose"]["why_used"] = ""; mutations.append(bad)
bad = canonical(); bad["events"][0]["audio"]["beat"] = "bass hit"; mutations.append(bad)
bad = canonical(); del bad["events"][0]["motion"]["easing"]; mutations.append(bad)
bad = canonical(); bad["events"][0]["narrative"]["stage"] = "intro"; mutations.append(bad)
for mutation in mutations:
    assert MODULE.validate(copy.deepcopy(mutation)), mutation
strict_mutations = []
bad = canonical_v11(); del bad["narrative_arc"]; strict_mutations.append(bad)
bad = canonical_v11(); bad["events"][0]["shot"]["framing"] = ""; strict_mutations.append(bad)
bad = canonical_v11(); bad["audio_policy"] = "licensed_library_track"; strict_mutations.append(bad)
bad = canonical_v11(); bad["events"][0]["shot"]["shot_duration_seconds"] = 0.4; strict_mutations.append(bad)
bad = canonical_v11(); bad["events"][0]["source_mapping"]["output_frame_out_exclusive"] = 53; strict_mutations.append(bad)
for mutation in strict_mutations:
    assert MODULE.validate(copy.deepcopy(mutation)), mutation
print("timeline grammar validator: v1.0 and strict v1.1 accepted; ten mutations rejected")
