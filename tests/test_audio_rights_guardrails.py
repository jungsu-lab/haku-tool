from __future__ import annotations

import copy
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill-package" / "haku-tool" / "scripts" / "validate_audio_rights.py"
SPEC = importlib.util.spec_from_file_location("validate_audio_rights", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def canonical() -> dict:
    return {
        "schema_version": "1.0",
        "provider": "Mixkit",
        "track_title": "Example Track",
        "creator": "Example Artist",
        "track_page_url": "https://example.com/track",
        "license_name": "Mixkit Stock Music Free License",
        "license_url": "https://mixkit.co/license/",
        "license_verified": True,
        "license_evidence_captured_at": "2026-08-01T09:00:00Z",
        "downloaded_at": "2026-08-01T09:00:00Z",
        "source_file": "C:/media/example.mp3",
        "sha256": "A" * 64,
        "generated_by_agent": False,
        "intended_use": "online_advertising",
        "permitted_uses": ["video_sync", "social_media"],
        "prohibited_uses": ["standalone_distribution"],
        "standalone_distribution_forbidden": True,
        "attribution_required": False,
        "attribution_text": "",
        "content_id_status": "unknown",
        "license_certificate_path": "",
        "platform_fit": ["local_review", "social_media"],
        "notes": ""
    }


assert MODULE.validate(canonical()) == []
mutations = []
bad = canonical(); bad["generated_by_agent"] = True; mutations.append(bad)
bad = canonical(); bad["permitted_uses"] = ["listening"]; mutations.append(bad)
bad = canonical(); bad["license_name"] = "CC BY-ND 4.0"; mutations.append(bad)
bad = canonical(); bad["license_name"] = "CC BY-NC 4.0"; mutations.append(bad)
bad = canonical(); bad["attribution_required"] = True; bad["attribution_text"] = ""; mutations.append(bad)
bad = canonical(); bad["sha256"] = "short"; mutations.append(bad)
for mutation in mutations:
    assert MODULE.validate(copy.deepcopy(mutation)), mutation
print("audio rights guardrails: canonical accepted; six unsafe mutations rejected")
