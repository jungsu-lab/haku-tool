from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skill-package" / "haku-tool"
VALIDATOR = SKILL / "scripts" / "validate_proof_cycles.py"
LEDGER = ROOT / "state" / "proof-cycles.json"
REGISTRY = SKILL / "references" / "auto-research-operator-registry.json"
LEGACY_REGISTRY = SKILL / "references" / "operator-registry.json"


def run_validator(payload: dict) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="haku-proof-cycle-test-") as folder:
        ledger = Path(folder) / "proof-cycles.json"
        ledger.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return subprocess.run(
            [
                sys.executable,
                str(VALIDATOR),
                str(ledger),
                "--operator-registry",
                str(REGISTRY),
                "--legacy-registry",
                str(LEGACY_REGISTRY),
            ],
            capture_output=True,
            text=True,
            check=False,
        )


def main() -> int:
    canonical = json.loads(LEDGER.read_text(encoding="utf-8"))

    valid = run_validator(canonical)
    if valid.returncode != 0:
        raise AssertionError(f"canonical ledger failed:\n{valid.stdout}\n{valid.stderr}")

    contradictory = copy.deepcopy(canonical)
    contradictory["cycles"][0]["research_verdict"] = "fail"
    result = run_validator(contradictory)
    if result.returncode == 0 or "must equal" not in result.stdout:
        raise AssertionError(f"contradictory verdict passed:\n{result.stdout}")

    duplicated_role = copy.deepcopy(canonical)
    cycle = duplicated_role["cycles"][0]
    cycle["supporting_operator_ids"].append(cycle["tested_operator_id"])
    result = run_validator(duplicated_role)
    if result.returncode == 0 or "cannot also be" not in result.stdout:
        raise AssertionError(f"duplicated operator role passed:\n{result.stdout}")

    missing_timeline = copy.deepcopy(canonical)
    del missing_timeline["cycles"][-1]["timeline_grammar"]
    result = run_validator(missing_timeline)
    if result.returncode == 0 or "timeline_grammar is required" not in result.stdout:
        raise AssertionError(f"missing timeline grammar passed:\n{result.stdout}")

    wrong_axis_count = copy.deepcopy(canonical)
    wrong_axis_count["cycles"][-1]["timeline_grammar_axis_count"] = 9
    result = run_validator(wrong_axis_count)
    if result.returncode == 0 or "timeline_grammar_axis_count must be 10" not in result.stdout:
        raise AssertionError(f"wrong axis count passed:\n{result.stdout}")

    wrong_operator_progress = copy.deepcopy(canonical)
    wrong_operator_progress["operator_promotion_progress"]["density-wave-release"]["accepted"] = 2
    result = run_validator(wrong_operator_progress)
    if result.returncode == 0 or "accepted mismatch" not in result.stdout:
        raise AssertionError(f"wrong operator progress passed:\n{result.stdout}")

    print("PASS: canonical accepted; verdict, role, timeline, axis-count, and Operator-progress mutations rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
