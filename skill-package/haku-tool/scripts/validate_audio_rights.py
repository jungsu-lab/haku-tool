from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


INTENDED_USES = {"noncommercial_video", "commercial_video", "social_media", "online_advertising"}
CONTENT_ID = {"not_registered", "registered", "unknown"}
COMMERCIAL_USES = {"commercial_video", "online_advertising"}


def text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate(
    payload: dict, check_file: bool = False, base_dir: Path | None = None
) -> list[str]:
    errors: list[str] = []
    for field in (
        "provider", "track_title", "creator", "track_page_url", "license_name",
        "license_url", "license_evidence_captured_at", "downloaded_at", "source_file", "sha256"
    ):
        if not text(payload.get(field)):
            errors.append(f"{field} must be non-empty")
    for field in ("track_page_url", "license_url"):
        if text(payload.get(field)) and not str(payload[field]).startswith(("https://", "http://")):
            errors.append(f"{field} must be an HTTP(S) URL")
    if payload.get("license_verified") is not True:
        errors.append("license_verified must be true")
    if payload.get("generated_by_agent") is not False:
        errors.append("generated_by_agent must be false")
    intended_use = payload.get("intended_use")
    if intended_use not in INTENDED_USES:
        errors.append("intended_use is invalid")
    permitted = payload.get("permitted_uses")
    if not isinstance(permitted, list) or "video_sync" not in permitted:
        errors.append("permitted_uses must include video_sync")
    prohibited = payload.get("prohibited_uses")
    if not isinstance(prohibited, list) or "standalone_distribution" not in prohibited:
        errors.append("prohibited_uses must include standalone_distribution")
    if payload.get("standalone_distribution_forbidden") is not True:
        errors.append("standalone_distribution_forbidden must be true")
    if payload.get("attribution_required") is not False and payload.get("attribution_required") is not True:
        errors.append("attribution_required must be boolean")
    if payload.get("attribution_required") is True and not text(payload.get("attribution_text")):
        errors.append("attribution_text is required when attribution is required")
    if payload.get("content_id_status") not in CONTENT_ID:
        errors.append("content_id_status is invalid")
    if not isinstance(payload.get("platform_fit"), list) or not payload.get("platform_fit"):
        errors.append("platform_fit must be a non-empty list")
    license_name = str(payload.get("license_name", "")).upper().replace("-", " ")
    if re.search(r"\bND\b|NO DERIVATIVES", license_name):
        errors.append("NoDerivatives licenses cannot be synchronized to video")
    if intended_use in COMMERCIAL_USES and re.search(r"\bNC\b|NONCOMMERCIAL", license_name):
        errors.append("NonCommercial licenses cannot be used for commercial video or advertising")
    sha256 = str(payload.get("sha256", ""))
    if not re.fullmatch(r"[0-9A-Fa-f]{64}", sha256):
        errors.append("sha256 must contain 64 hexadecimal characters")
    if check_file and text(payload.get("source_file")):
        source = Path(payload["source_file"])
        if not source.is_absolute() and base_dir is not None:
            source = (base_dir / source).resolve()
        if not source.is_file():
            errors.append("source_file does not exist")
        elif re.fullmatch(r"[0-9A-Fa-f]{64}", sha256):
            actual = hashlib.sha256(source.read_bytes()).hexdigest()
            if actual.lower() != sha256.lower():
                errors.append("source_file hash does not match sha256")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--check-file", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    errors = validate(
        payload,
        check_file=args.check_file,
        base_dir=args.manifest.resolve().parent,
    )
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
