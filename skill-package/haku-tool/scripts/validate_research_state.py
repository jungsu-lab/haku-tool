from __future__ import annotations

import argparse
import json
from pathlib import Path


ALLOWED_STATUSES = {
    "pending_visual_review",
    "reviewed_legacy_golden",
    "semantic_complete",
    "needs_second_review",
    "excluded",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("state", type=Path)
    args = parser.parse_args()
    state_path = args.state.resolve()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    ids: set[str] = set()

    if state.get("schema_version") != "1.0":
        errors.append("schema_version must be 1.0")
    if state.get("rights_policy") != "public-reference-only-analysis":
        errors.append("rights_policy mismatch")

    for reel in state.get("reels", []):
        reel_id = str(reel.get("reel_id", ""))
        if not reel_id or reel_id in ids:
            errors.append(f"invalid or duplicate reel_id: {reel_id!r}")
        ids.add(reel_id)
        status = reel.get("research_status")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{reel_id}: invalid research_status {status!r}")
        if reel.get("rights", {}).get("status") != "public-reference-only":
            errors.append(f"{reel_id}: rights status must be public-reference-only")
        if reel.get("rights", {}).get("output_reuse") is not False:
            errors.append(f"{reel_id}: output_reuse must be false")
        for key in ("private_analysis_copy", "storyboard", "quantitative_card"):
            if not Path(reel[key]).is_file():
                errors.append(f"{reel_id}: missing {key}: {reel[key]}")
        if status == "semantic_complete":
            if reel.get("direct_visual_review") is not True:
                errors.append(f"{reel_id}: semantic_complete without visual review")
            if int(reel.get("evidence_range_count", 0)) < 3:
                errors.append(f"{reel_id}: semantic_complete needs 3 evidence ranges")
            review = reel.get("semantic_review_path")
            if not review or not Path(review).is_file():
                errors.append(f"{reel_id}: missing semantic review file")

    expected = len(state.get("reels", []))
    if expected != 40:
        errors.append(f"expected 40 reels, found {expected}")

    print(
        json.dumps(
            {"valid": not errors, "reel_count": expected, "errors": errors},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

