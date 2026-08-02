from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Record a main-agent direct visual review. This command cannot record "
            "or infer a user verdict."
        )
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--research-verdict",
        required=True,
        choices=["pass", "partial_pass", "fail"],
    )
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--limitation", action="append", default=[])
    parser.add_argument("--originals-reviewed", action="store_true")
    parser.add_argument("--plain-reviewed", action="store_true")
    parser.add_argument("--proof-reviewed", action="store_true")
    parser.add_argument("--all-boundaries-reviewed", action="store_true")
    parser.add_argument("--full-playback-reviewed", action="store_true")
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload.setdefault("recipe", str(Path("..") / ".." / "recipe.json"))
    payload.setdefault("render_report", str(Path("..") / "render-report.json"))
    payload["manifest_path"] = manifest_path.name
    for name in ("plain", "proof"):
        evidence = payload.get("dense_full_sequence_evidence", {}).get(name)
        if evidence:
            evidence["path"] = f"{name}-8fps.jpg"
    for item in payload.get("boundary_and_internal_event_evidence", []):
        item["strip"] = str(
            Path("boundaries") / Path(item["strip"]).name
        )
    required = {
        "originals_reviewed": args.originals_reviewed,
        "plain_reviewed": args.plain_reviewed,
        "proof_reviewed": args.proof_reviewed,
        "all_boundary_strips_reviewed": args.all_boundaries_reviewed,
        "full_playback_reviewed": args.full_playback_reviewed,
    }
    if not all(
        required[key]
        for key in (
            "originals_reviewed",
            "plain_reviewed",
            "proof_reviewed",
            "all_boundary_strips_reviewed",
        )
    ):
        parser.error(
            "A research verdict requires direct review of originals, plain, proof, "
            "and every boundary strip."
        )
    if not args.evidence:
        parser.error("At least one timestamped or frame-specific --evidence is required")

    payload["direct_visual_review"] = {
        "status": "reviewed_by_main_agent",
        **required,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "evidence": args.evidence,
        "limitations": args.limitation,
    }
    payload["research_verdict"]["status"] = args.research_verdict
    existing_user_verdict = payload.get("user_verdict", {"status": "pending"})
    existing_promotion_increment = payload.get("promotion_increment", 0)
    payload["user_verdict"] = existing_user_verdict
    payload["promotion_increment"] = existing_promotion_increment
    for item in payload.get("boundary_and_internal_event_evidence", []):
        item["review_status"] = "reviewed_by_main_agent"
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    render_report_path = Path(payload["render_report"])
    if not render_report_path.is_absolute():
        render_report_path = (manifest_path.parent / render_report_path).resolve()
    if render_report_path.is_file():
        report = json.loads(render_report_path.read_text(encoding="utf-8"))
        report["visual_review"] = {
            "status": "reviewed_by_main_agent",
            **required,
            "evidence": args.evidence,
            "limitations": args.limitation,
            "review_manifest": str(manifest_path),
        }
        if "user_verdict" not in report:
            report["user_verdict"] = existing_user_verdict
        render_report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(
        json.dumps(
            {
                "updated": str(manifest_path),
                "research_verdict": args.research_verdict,
                "user_verdict": existing_user_verdict.get("status", "pending"),
                "promotion_increment": existing_promotion_increment,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
