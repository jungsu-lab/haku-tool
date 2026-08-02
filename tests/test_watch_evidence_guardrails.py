from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skill-package" / "haku-tool" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from validate_watch_evidence import validate


def canonical(folder: Path) -> tuple[dict, Path]:
    source = folder / "원본 영상.mp4"
    source.write_bytes(b"permitted-fixture")
    frame = folder / "frame-000.jpg"
    frame.write_bytes(b"jpeg-fixture")
    report = folder / "report.md"
    report.write_text("watch report", encoding="utf-8")
    timeline = folder / "timeline-grammar.json"
    timeline.write_text(json.dumps({"schema_version": "1.1"}), encoding="utf-8")
    import hashlib

    payload = {
        "schema_version": "1.0",
        "source": {
            "kind": "local_file",
            "value": str(source),
            "rights_status": "licensed",
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest().upper(),
        },
        "invocation": {
            "wrapper": "C:/Users/HP-5600G/Desktop/AI 제작과정/tools/run-watch.cmd",
            "detail": "balanced",
            "external_transcription_allowed": False,
            "explicit_user_consent_for_audio_upload": False,
            "no_whisper": True,
            "output_directory": str(folder),
            "report_path": str(report),
        },
        "review": {
            "reviewer": "main-agent",
            "every_listed_frame_reviewed": True,
            "transcript_source": "none",
            "frame_evidence": [
                {
                    "timestamp_seconds": 0.0,
                    "frame_path": str(frame),
                    "observation": "A static field is visible.",
                    "inference": "The frame can establish place.",
                    "timeline_event_ids": ["event-001"],
                }
            ],
            "limitations": [],
        },
        "reuse_gate": {
            "analysis_only": False,
            "allowed_in_proof": True,
            "allowed_in_final": True,
        },
        "conversion": {
            "status": "mapped",
            "timeline_grammar_path": str(timeline),
        },
    }
    return payload, folder / "watch-evidence.json"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="haku-watch-evidence-") as raw:
        folder = Path(raw)
        payload, evidence = canonical(folder)
        evidence.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        errors = validate(payload, evidence, check_files=True)
        if errors:
            raise AssertionError(f"canonical evidence failed: {errors}")

        mutations = []
        wrong_rights = copy.deepcopy(payload)
        wrong_rights["source"]["rights_status"] = "unknown"
        mutations.append((wrong_rights, "rights_status"))
        leaked_transcription = copy.deepcopy(payload)
        leaked_transcription["invocation"]["no_whisper"] = False
        mutations.append((leaked_transcription, "no_whisper"))
        unreviewed = copy.deepcopy(payload)
        unreviewed["review"]["every_listed_frame_reviewed"] = False
        mutations.append((unreviewed, "directly reviewed"))
        public_reuse = copy.deepcopy(payload)
        public_reuse["source"]["rights_status"] = "public-reference-only"
        mutations.append((public_reuse, "cannot enter proof"))
        unmapped = copy.deepcopy(payload)
        unmapped["review"]["frame_evidence"][0]["timeline_event_ids"] = []
        mutations.append((unmapped, "event IDs"))

        for mutated, expected in mutations:
            errors = validate(mutated, evidence, check_files=False)
            if not any(expected in error for error in errors):
                raise AssertionError(f"mutation was not rejected ({expected}): {errors}")

    print("watch evidence guardrails: canonical accepted; five unsafe mutations rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

