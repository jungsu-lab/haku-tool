from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skill-package" / "haku-tool" / "scripts"
sys.path.insert(0, str(SCRIPTS))
SCRIPT = SCRIPTS / "licensed_audio.py"
SPEC = importlib.util.spec_from_file_location("licensed_audio", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


with tempfile.TemporaryDirectory(prefix="haku-licensed-audio-test-") as folder:
    root = Path(folder)
    audio = root / "track.mp3"
    audio.write_bytes(b"existing-public-track-fixture")
    digest = hashlib.sha256(audio.read_bytes()).hexdigest()
    rights = {
        "schema_version": "1.0", "provider": "Mixkit", "track_title": "Fixture",
        "creator": "Fixture Creator", "track_page_url": "https://example.com/track",
        "license_name": "Mixkit Stock Music Free License", "license_url": "https://mixkit.co/license/",
        "license_verified": True, "license_evidence_captured_at": "2026-08-01T09:00:00Z",
        "downloaded_at": "2026-08-01T09:00:00Z", "source_file": "track.mp3",
        "sha256": digest, "generated_by_agent": False, "intended_use": "social_media",
        "permitted_uses": ["video_sync"], "prohibited_uses": ["standalone_distribution"],
        "standalone_distribution_forbidden": True, "attribution_required": False,
        "attribution_text": "", "content_id_status": "unknown",
        "platform_fit": ["social_media"], "notes": "fixture"
    }
    (root / "audio-rights.json").write_text(json.dumps(rights), encoding="utf-8")
    timeline = {
        "audio_policy": "licensed_library_track",
        "events": [{"event_id": "visual-001"}]
    }
    (root / "timeline-grammar.json").write_text(json.dumps(timeline), encoding="utf-8")
    event_map = {
        "schema_version": "1.0", "audio_rights_manifest": "audio-rights.json",
        "audio_file_sha256": digest, "track_source_in_seconds": 2.0,
        "track_source_out_seconds": 12.0,
        "analysis_method": ["waveform", "direct_listening"],
        "events": [{
            "event_id": "music-001", "track_seconds": 2.0,
            "timeline_seconds": 0.0, "type": "phrase_start",
            "observation": "A clean phrase begins.", "visual_response": "cut",
            "target_visual_event_id": "visual-001", "intentional_offset_ms": 0,
            "confidence": "high"
        }]
    }
    (root / "music-event-map.json").write_text(json.dumps(event_map), encoding="utf-8")
    recipe = {
        "audio_policy": "licensed_library_track",
        "licensed_audio": {
            "file": "track.mp3", "audio_rights_manifest": "audio-rights.json",
            "music_event_map": "music-event-map.json", "timeline_grammar": "timeline-grammar.json",
            "source_in_seconds": 2.0, "source_out_seconds": 12.0,
            "gain_db": -12.0, "fade_in_seconds": 0.1, "fade_out_seconds": 0.5,
            "same_for_plain_and_proof": True
        }
    }
    recipe_path = root / "recipe.json"
    recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
    assert MODULE.prepare_licensed_audio(recipe_path, recipe, 8.0)
    deferred = copy.deepcopy(recipe); deferred["audio_policy"] = "deferred_by_rights"
    assert MODULE.prepare_licensed_audio(recipe_path, deferred, 8.0) is None
    mutations = []
    bad = copy.deepcopy(recipe); bad["licensed_audio"]["same_for_plain_and_proof"] = False; mutations.append(bad)
    bad = copy.deepcopy(recipe); bad["licensed_audio"]["source_out_seconds"] = 7.0; mutations.append(bad)
    bad = copy.deepcopy(recipe); bad["licensed_audio"]["gain_db"] = 12.0; mutations.append(bad)
    for mutation in mutations:
        try:
            MODULE.prepare_licensed_audio(recipe_path, mutation, 8.0)
        except (ValueError, FileNotFoundError):
            pass
        else:
            raise AssertionError(mutation)
print("licensed audio recipe guardrails: canonical and rights-deferred accepted; three unsafe mixes rejected")
