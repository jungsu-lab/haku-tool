from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate(payload: dict, manifest_path: Path | None = None, check_files: bool = False) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != "1.0":
        errors.append("schema_version must be 1.0")
    if not text(payload.get("session_id")):
        errors.append("session_id must be non-empty")
    rights = payload.get("rights_basis")
    if not isinstance(rights, dict):
        errors.append("rights_basis must be an object")
    else:
        for field in ("provider", "creator", "license_url", "allowed_use"):
            if not text(rights.get(field)):
                errors.append(f"rights_basis.{field} must be non-empty")
        if text(rights.get("license_url")) and not str(rights["license_url"]).startswith(("https://", "http://")):
            errors.append("rights_basis.license_url must be HTTP(S)")
    capture = payload.get("capture_world")
    if not isinstance(capture, dict):
        errors.append("capture_world must be an object")
    else:
        for field in (
            "world_id", "subject_identity", "location", "time_of_day", "weather",
            "lens_character", "color_temperature", "same_world_claim",
        ):
            if not text(capture.get(field)):
                errors.append(f"capture_world.{field} must be non-empty")
        if not isinstance(capture.get("palette"), list) or not capture.get("palette"):
            errors.append("capture_world.palette must be a non-empty list")
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        return errors + ["sources must be a non-empty list"]
    seen: set[str] = set()
    base = manifest_path.parent if manifest_path is not None else Path.cwd()
    for index, source in enumerate(sources):
        prefix = f"sources[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{prefix} must be an object")
            continue
        clip_id = source.get("source_clip_id")
        if not text(clip_id):
            errors.append(f"{prefix}.source_clip_id must be non-empty")
        elif clip_id in seen:
            errors.append(f"{prefix}.source_clip_id must be unique")
        else:
            seen.add(str(clip_id))
        for field in ("file", "sha256", "page_url", "license_url", "creator", "semantic_role"):
            if not text(source.get(field)):
                errors.append(f"{prefix}.{field} must be non-empty")
        for field in ("page_url", "license_url"):
            if text(source.get(field)) and not str(source[field]).startswith(("https://", "http://")):
                errors.append(f"{prefix}.{field} must be HTTP(S)")
        digest = str(source.get("sha256", ""))
        if not re.fullmatch(r"[0-9A-Fa-f]{64}", digest):
            errors.append(f"{prefix}.sha256 must contain 64 hexadecimal characters")
        for field in ("duration_seconds", "width", "height", "fps"):
            if not isinstance(source.get(field), (int, float)) or source[field] <= 0:
                errors.append(f"{prefix}.{field} must be greater than zero")
        if not isinstance(source.get("audio_stream_present"), bool):
            errors.append(f"{prefix}.audio_stream_present must be boolean")
        if source.get("single_take") is not True:
            errors.append(f"{prefix}.single_take must be true for proof material")
        if source.get("existing_edit_detected") is not False:
            errors.append(f"{prefix}.existing_edit_detected must be false for proof material")
        retake = source.get("hidden_retake_review")
        if not isinstance(retake, dict):
            errors.append(f"{prefix}.hidden_retake_review must be an object")
        else:
            if retake.get("method") not in {"full_playback", "dense_storyboard_and_boundary_review"}:
                errors.append(f"{prefix}.hidden_retake_review.method is invalid")
            if retake.get("status") != "no_detected_splice":
                errors.append(f"{prefix}.hidden_retake_review.status must be no_detected_splice")
            if not text(retake.get("limitations")):
                errors.append(f"{prefix}.hidden_retake_review.limitations must be non-empty")
        if check_files and text(source.get("file")):
            file_path = Path(str(source["file"]))
            if not file_path.is_absolute():
                file_path = (base / file_path).resolve()
            if not file_path.is_file():
                errors.append(f"{prefix}.file does not exist")
            elif re.fullmatch(r"[0-9A-Fa-f]{64}", digest) and sha256(file_path).lower() != digest.lower():
                errors.append(f"{prefix}.file hash does not match sha256")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--check-files", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    errors = validate(payload, manifest_path=args.manifest.resolve(), check_files=args.check_files)
    print(json.dumps({"valid": not errors, "source_count": len(payload.get("sources", [])), "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
