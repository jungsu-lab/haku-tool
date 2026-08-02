from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "skill-package"
    / "haku-tool"
    / "scripts"
    / "record_proof_review.py"
)

with tempfile.TemporaryDirectory() as temporary_directory:
    manifest = Path(temporary_directory) / "review-manifest.json"
    custom_recipe = str(Path("..") / ".." / "recipe-v004.json")
    custom_report = str(Path("..") / "render-report-v004.json")
    manifest.write_text(
        json.dumps(
            {
                "recipe": custom_recipe,
                "render_report": custom_report,
                "dense_full_sequence_evidence": {
                    "plain": {"path": "plain-old.jpg"},
                    "proof": {"path": "proof-old.jpg"},
                },
                "boundary_and_internal_event_evidence": [],
                "research_verdict": {"status": "pending"},
                "user_verdict": {"status": "pending"},
                "promotion_increment": 0,
            }
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "py",
            "-3.10",
            str(SCRIPT),
            str(manifest),
            "--research-verdict",
            "partial_pass",
            "--evidence",
            "frame-specific regression fixture",
            "--originals-reviewed",
            "--plain-reviewed",
            "--proof-reviewed",
            "--all-boundaries-reviewed",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    updated = json.loads(manifest.read_text(encoding="utf-8"))
    assert updated["recipe"] == custom_recipe
    assert updated["render_report"] == custom_report

print("review provenance guardrails: pass")
