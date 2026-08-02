from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


RIGHTS = {"owned", "licensed", "permissioned-analysis", "public-reference-only"}
DETAILS = {"efficient", "balanced", "token-burner"}
TRANSCRIPTS = {"none", "native-captions", "external-whisper"}


def _resolve(base: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else (base / path).resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def validate(payload: dict, evidence_path: Path | None = None, check_files: bool = False) -> list[str]:
    errors: list[str] = []
    base = evidence_path.parent if evidence_path else Path.cwd()
    if payload.get("schema_version") != "1.0":
        errors.append("schema_version must be 1.0")

    source = payload.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
        source = {}
    kind = source.get("kind")
    if kind not in {"url", "local_file"}:
        errors.append("source.kind must be url or local_file")
    rights = source.get("rights_status")
    if rights not in RIGHTS:
        errors.append("source.rights_status must be an explicit permitted status")
    if not isinstance(source.get("value"), str) or not source.get("value", "").strip():
        errors.append("source.value must be non-empty")
    if kind == "local_file":
        sha = str(source.get("sha256", ""))
        if len(sha) != 64:
            errors.append("local_file source.sha256 must contain 64 hex characters")
        if check_files and isinstance(source.get("value"), str):
            source_file = _resolve(base, source["value"])
            if not source_file.is_file():
                errors.append("local source file does not exist")
            elif _sha256(source_file) != sha.upper():
                errors.append("local source sha256 does not match file")

    invocation = payload.get("invocation")
    if not isinstance(invocation, dict):
        errors.append("invocation must be an object")
        invocation = {}
    wrapper = str(invocation.get("wrapper", "")).replace("\\", "/").lower()
    if not wrapper.endswith("/tools/run-watch.cmd"):
        errors.append("invocation.wrapper must point to tools/run-watch.cmd")
    if invocation.get("detail") not in DETAILS:
        errors.append("invocation.detail is invalid")
    external_allowed = invocation.get("external_transcription_allowed") is True
    consent = invocation.get("explicit_user_consent_for_audio_upload") is True
    no_whisper = invocation.get("no_whisper") is True
    if external_allowed and not consent:
        errors.append("external transcription requires explicit user consent")
    if external_allowed and no_whisper:
        errors.append("external transcription cannot be combined with no_whisper")
    if not external_allowed and not no_whisper:
        errors.append("no_whisper must be true when external transcription is not allowed")
    if check_files:
        for field in ("output_directory", "report_path"):
            value = invocation.get(field)
            path = _resolve(base, value) if isinstance(value, str) else None
            if path is None or (not path.is_dir() if field == "output_directory" else not path.is_file()):
                errors.append(f"invocation.{field} does not exist")

    review = payload.get("review")
    if not isinstance(review, dict):
        errors.append("review must be an object")
        review = {}
    if review.get("reviewer") != "main-agent":
        errors.append("review.reviewer must be main-agent")
    if review.get("every_listed_frame_reviewed") is not True:
        errors.append("every listed frame must be directly reviewed")
    transcript_source = review.get("transcript_source")
    if transcript_source not in TRANSCRIPTS:
        errors.append("review.transcript_source is invalid")
    if transcript_source == "external-whisper" and not external_allowed:
        errors.append("external-whisper transcript is not permitted by invocation")
    frame_evidence = review.get("frame_evidence")
    if not isinstance(frame_evidence, list) or not frame_evidence:
        errors.append("review.frame_evidence must be a non-empty list")
        frame_evidence = []
    previous_time = -1.0
    for index, item in enumerate(frame_evidence):
        prefix = f"review.frame_evidence[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        try:
            timestamp = float(item.get("timestamp_seconds"))
            if timestamp < 0 or timestamp < previous_time:
                errors.append(f"{prefix}.timestamp_seconds must be non-negative and sorted")
            previous_time = timestamp
        except (TypeError, ValueError):
            errors.append(f"{prefix}.timestamp_seconds must be numeric")
        for field in ("frame_path", "observation", "inference"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{prefix}.{field} must be non-empty")
        event_ids = item.get("timeline_event_ids")
        if not isinstance(event_ids, list) or not all(isinstance(value, str) and value for value in event_ids):
            errors.append(f"{prefix}.timeline_event_ids must be a string list")
        if check_files and isinstance(item.get("frame_path"), str):
            if not _resolve(base, item["frame_path"]).is_file():
                errors.append(f"{prefix}.frame_path does not exist")

    reuse = payload.get("reuse_gate")
    if not isinstance(reuse, dict):
        errors.append("reuse_gate must be an object")
        reuse = {}
    if rights == "public-reference-only":
        if reuse.get("analysis_only") is not True:
            errors.append("public-reference-only evidence must remain analysis_only")
        if reuse.get("allowed_in_proof") is not False or reuse.get("allowed_in_final") is not False:
            errors.append("public-reference-only evidence cannot enter proof or final")

    conversion = payload.get("conversion")
    if not isinstance(conversion, dict):
        errors.append("conversion must be an object")
        conversion = {}
    status = conversion.get("status")
    if status not in {"pending", "mapped"}:
        errors.append("conversion.status must be pending or mapped")
    if status == "mapped":
        if not isinstance(conversion.get("timeline_grammar_path"), str) or not conversion["timeline_grammar_path"].strip():
            errors.append("mapped conversion requires timeline_grammar_path")
        for index, item in enumerate(frame_evidence):
            if isinstance(item, dict) and not item.get("timeline_event_ids"):
                errors.append(f"mapped conversion requires event IDs at frame {index}")
        if check_files and isinstance(conversion.get("timeline_grammar_path"), str):
            if not _resolve(base, conversion["timeline_grammar_path"]).is_file():
                errors.append("conversion.timeline_grammar_path does not exist")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--check-files", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.evidence.read_text(encoding="utf-8"))
    errors = validate(payload, args.evidence, args.check_files)
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

