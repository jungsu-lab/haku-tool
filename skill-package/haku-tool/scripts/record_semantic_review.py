from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ALLOWED_STATUSES = {"semantic_complete", "needs_second_review"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument(
        "--status",
        choices=sorted(ALLOWED_STATUSES),
        default="semantic_complete",
    )
    args = parser.parse_args()

    state_path = args.state.resolve()
    review_path = args.review.resolve()
    state = load_json(state_path)
    review = load_json(review_path)
    reel_id = review.get("reel_id")
    if not reel_id:
        raise ValueError("review.reel_id is required")
    if review.get("account") != state.get("account"):
        raise ValueError("review account does not match research state")
    if review.get("rights") != "public-reference-only":
        raise ValueError("reference reviews must remain public-reference-only")

    visual = review.get("direct_visual_review", {})
    if not visual.get("storyboard_reviewed"):
        raise ValueError("storyboard_reviewed must be true")
    if not visual.get("dense_timeline_reviewed"):
        raise ValueError("dense_timeline_reviewed must be true")

    evidence = review.get("evidence", [])
    if len(evidence) < 3:
        raise ValueError("at least three evidence ranges are required")
    for number, item in enumerate(evidence, 1):
        start = item.get("start_seconds")
        end = item.get("end_seconds")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            raise ValueError(f"evidence {number} must have numeric boundaries")
        if end <= start:
            raise ValueError(f"evidence {number} end must be greater than start")
        if not item.get("observation") or not item.get("inference"):
            raise ValueError(
                f"evidence {number} must separate observation and inference"
            )

    matches = [item for item in state["reels"] if item["reel_id"] == reel_id]
    if len(matches) != 1:
        raise ValueError(f"expected one state entry for {reel_id}, found {len(matches)}")
    reel = matches[0]
    if reel["rights"]["output_reuse"]:
        raise ValueError("reference item unexpectedly permits output reuse")

    now = datetime.now(timezone.utc).isoformat()
    reel["research_status"] = args.status
    reel["direct_visual_review"] = True
    reel["full_playback_review"] = bool(visual.get("full_playback_reviewed"))
    reel["semantic_review_path"] = str(review_path)
    reel["evidence_range_count"] = len(evidence)
    reel["inference_count"] = sum(
        1 for item in evidence if item.get("inference")
    )
    reel["counterexample_count"] = len(review.get("counterexamples", []))
    reel["last_updated_at"] = now

    statuses = [item["research_status"] for item in state["reels"]]
    state["counts"]["total"] = len(statuses)
    state["counts"]["legacy_golden_reviewed"] = statuses.count(
        "reviewed_legacy_golden"
    )
    state["counts"]["semantic_complete"] = statuses.count("semantic_complete")
    state["counts"]["needs_second_review"] = statuses.count("needs_second_review")
    state["counts"]["pending_visual_review"] = statuses.count(
        "pending_visual_review"
    )
    state["updated_at"] = now
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "reel_id": reel_id,
                "status": args.status,
                "evidence_ranges": len(evidence),
                "state": str(state_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
