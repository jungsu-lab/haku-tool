from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_audio_rights import validate as validate_audio_rights
from validate_music_event_map import validate as validate_music_event_map
from validate_source_manifest import validate as validate_source_manifest
from validate_timeline_grammar import validate as validate_timeline_grammar


RESEARCH_VERDICTS = {
    "pending",
    "pass",
    "partial_pass",
    "fail",
    "supporting_pass",
    "not_independently_tested",
}
CYCLING_VERDICTS = {"pending", "pass", "partial_pass", "fail"}
USER_VERDICTS = {"pending", "accepted", "partial", "rejected"}


def validate_timeline_source_mappings(
    timeline_payload: dict,
    timeline_file: Path,
    source_manifest_payload: dict,
    source_manifest_file: Path,
) -> list[str]:
    """Cross-check every timeline mapping against one exact manifest record."""
    errors: list[str] = []
    manifest_sources: dict[str, tuple[dict, Path]] = {}
    for source in source_manifest_payload.get("sources", []):
        if not isinstance(source, dict):
            continue
        source_clip_id = str(source.get("source_clip_id", "")).strip()
        if not source_clip_id:
            continue
        source_path = Path(str(source.get("file", "")))
        if not source_path.is_absolute():
            source_path = (source_manifest_file.parent / source_path).resolve()
        manifest_sources[source_clip_id] = (source, source_path)

    tolerance = 1e-6
    for event in timeline_payload.get("events", []):
        if not isinstance(event, dict):
            continue
        event_id = event.get("event_id", "unknown")
        mapping = event.get("source_mapping", {})
        if not isinstance(mapping, dict):
            errors.append(f"timeline source_mapping must be an object: {event_id}")
            continue
        source_clip_id = str(mapping.get("source_clip_id", "")).strip()
        manifest_entry = manifest_sources.get(source_clip_id)
        if manifest_entry is None:
            errors.append(
                f"timeline source_clip_id is not backed by source_manifest: "
                f"{event_id} ({source_clip_id or 'missing'})"
            )
            continue
        source, manifest_path = manifest_entry
        mapped_path = Path(str(mapping.get("source_path", "")))
        if not mapped_path.is_absolute():
            mapped_path = (timeline_file.parent / mapped_path).resolve()
        if str(mapped_path).casefold() != str(manifest_path).casefold():
            errors.append(f"timeline source_path does not match source_manifest: {event_id}")
        if str(mapping.get("source_sha256", "")).lower() != str(source.get("sha256", "")).lower():
            errors.append(f"timeline source_sha256 does not match source_manifest: {event_id}")
        try:
            mapped_fps = float(mapping.get("source_fps"))
            manifest_fps = float(source.get("fps"))
            if abs(mapped_fps - manifest_fps) > tolerance:
                errors.append(f"timeline source_fps does not match source_manifest: {event_id}")
        except (TypeError, ValueError):
            errors.append(f"timeline source_fps is not numeric: {event_id}")
        try:
            source_in = float(mapping.get("source_in_seconds"))
            source_out = float(mapping.get("source_out_seconds"))
            duration = float(source.get("duration_seconds"))
            if source_in < -tolerance:
                errors.append(f"timeline source_in_seconds is before source start: {event_id}")
            if source_out <= source_in + tolerance:
                errors.append(f"timeline source range is empty or reversed: {event_id}")
            if source_out > duration + tolerance:
                errors.append(f"timeline source_out_seconds exceeds source duration: {event_id}")
        except (TypeError, ValueError):
            errors.append(f"timeline source range is not numeric: {event_id}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--operator-registry", type=Path, required=True)
    parser.add_argument("--legacy-registry", type=Path)
    args = parser.parse_args()

    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    registry = json.loads(args.operator_registry.read_text(encoding="utf-8"))
    registry_ids = {item["id"] for item in registry["operators"]}
    legacy_ids: set[str] = set()
    if args.legacy_registry:
        legacy = json.loads(args.legacy_registry.read_text(encoding="utf-8"))
        legacy_ids = {
            item["operator_id"] for item in legacy.get("core_operators", [])
        }
        legacy_ids.update(
            item["device_id"] for item in legacy.get("conditional_devices", [])
        )
    known_operator_ids = registry_ids | legacy_ids
    errors: list[str] = []
    seen_cycle_ids: set[str] = set()
    accepted_situations: set[str] = set()
    accepted_situations_by_operator: dict[str, set[str]] = {}
    decision_contract = ledger.get("decision_contract", {})
    enforced_from = decision_contract.get("enforced_from_cycle_id")
    strict_started = False
    strict_cycle_count = 0
    check_artifact_paths = args.ledger.parent.name == "state"

    for cycle in ledger["cycles"]:
        cycle_id = cycle["cycle_id"]
        if cycle_id == enforced_from:
            strict_started = True
        if cycle_id in seen_cycle_ids:
            errors.append(f"duplicate cycle_id: {cycle_id}")
        seen_cycle_ids.add(cycle_id)
        situation_id = cycle.get("promotion_situation_id")
        if not situation_id:
            errors.append(f"{cycle_id}: missing promotion_situation_id")

        tested = cycle["tested_operator_id"]
        supporting = set(cycle.get("supporting_operator_ids", []))
        if tested in supporting:
            errors.append(
                f"{cycle_id}: tested_operator_id cannot also be a supporting operator"
            )
        attributed = {tested, *supporting}
        unknown = attributed - known_operator_ids
        if unknown:
            errors.append(f"{cycle_id}: unknown operator IDs {sorted(unknown)}")
        verdicts = cycle.get("operator_verdicts", {})
        if set(verdicts) != attributed:
            errors.append(
                f"{cycle_id}: operator_verdicts keys must equal tested + supporting IDs"
            )
        for operator_id, verdict in verdicts.items():
            if verdict not in RESEARCH_VERDICTS:
                errors.append(
                    f"{cycle_id}: invalid verdict {verdict} for {operator_id}"
                )
        cycle_verdict = cycle.get("research_verdict")
        if cycle_verdict not in CYCLING_VERDICTS:
            errors.append(
                f"{cycle_id}: invalid cycle research_verdict {cycle_verdict}"
            )
        tested_verdict = verdicts.get(tested)
        if (
            cycle_verdict in CYCLING_VERDICTS
            and tested_verdict in RESEARCH_VERDICTS
            and cycle_verdict != tested_verdict
        ):
            errors.append(
                f"{cycle_id}: cycle research_verdict must equal the tested "
                "operator verdict"
            )

        user_verdict = cycle.get("user_verdict")
        if user_verdict not in USER_VERDICTS:
            errors.append(f"{cycle_id}: invalid user_verdict {user_verdict}")
        increment = int(cycle.get("promotion_increment", 0))
        if user_verdict == "accepted":
            if increment not in (0, 1):
                errors.append(f"{cycle_id}: accepted increment must be 0 or 1")
            if increment == 1 and situation_id:
                accepted_situations.add(situation_id)
                accepted_situations_by_operator.setdefault(tested, set()).add(situation_id)
        elif increment != 0:
            errors.append(f"{cycle_id}: non-accepted cycle cannot increment promotion")
        if strict_started:
            strict_cycle_count += 1
            source_manifest_file: Path | None = None
            source_manifest_payload: dict | None = None
            if cycle.get("decision_contract_version") != "1.1":
                errors.append(f"{cycle_id}: decision_contract_version must be 1.1")
            if cycle.get("timeline_grammar_axis_count") != 10:
                errors.append(f"{cycle_id}: timeline_grammar_axis_count must be 10")
            source_manifest_path = cycle.get("source_manifest")
            if not isinstance(source_manifest_path, str) or not source_manifest_path.strip():
                errors.append(f"{cycle_id}: source_manifest is required")
            elif check_artifact_paths:
                source_manifest_file = (args.ledger.parent / source_manifest_path).resolve()
                if not source_manifest_file.is_file():
                    errors.append(f"{cycle_id}: source_manifest file does not exist")
                else:
                    source_manifest_payload = json.loads(source_manifest_file.read_text(encoding="utf-8"))
                    source_manifest_errors = validate_source_manifest(
                        source_manifest_payload,
                        manifest_path=source_manifest_file,
                        check_files=True,
                    )
                    errors.extend(
                        f"{cycle_id}: source_manifest: {error}"
                        for error in source_manifest_errors
                    )
            timeline_path = cycle.get("timeline_grammar")
            timeline_file: Path | None = None
            timeline_payload: dict | None = None
            if not isinstance(timeline_path, str) or not timeline_path.strip():
                errors.append(f"{cycle_id}: timeline_grammar is required")
            elif check_artifact_paths:
                timeline_file = (args.ledger.parent / timeline_path).resolve()
                if not timeline_file.is_file():
                    errors.append(f"{cycle_id}: timeline_grammar file does not exist")
                else:
                    timeline_payload = json.loads(timeline_file.read_text(encoding="utf-8"))
                    timeline_errors = validate_timeline_grammar(timeline_payload)
                    errors.extend(f"{cycle_id}: timeline_grammar: {error}" for error in timeline_errors)
                    if timeline_payload.get("artifact_type") != "proof_edit":
                        errors.append(f"{cycle_id}: timeline_grammar artifact_type must be proof_edit")
                    if source_manifest_payload is not None and source_manifest_file is not None:
                        mapping_errors = validate_timeline_source_mappings(
                            timeline_payload,
                            timeline_file,
                            source_manifest_payload,
                            source_manifest_file,
                        )
                        errors.extend(
                            f"{cycle_id}: {error}" for error in mapping_errors
                        )
            audio_decision = cycle.get("audio_decision")
            if not isinstance(audio_decision, dict):
                errors.append(f"{cycle_id}: audio_decision must be an object")
            else:
                if audio_decision.get("policy") not in {
                    "deferred_by_user", "deferred_by_rights", "licensed_library_track"
                }:
                    errors.append(f"{cycle_id}: audio_decision.policy is invalid")
                if not isinstance(audio_decision.get("reason"), str) or not audio_decision["reason"].strip():
                    errors.append(f"{cycle_id}: audio_decision.reason must be non-empty")
                policy = audio_decision.get("policy")
                if timeline_payload is not None:
                    timeline_policy = timeline_payload.get("audio_policy")
                    if policy == "licensed_library_track" and timeline_policy != policy:
                        errors.append(f"{cycle_id}: timeline audio_policy must be licensed_library_track")
                    if policy in {"deferred_by_user", "deferred_by_rights"} and timeline_policy != policy:
                        errors.append(f"{cycle_id}: deferred proof timeline audio_policy must match audio_decision.policy")
                if policy == "licensed_library_track" and timeline_file is not None and timeline_payload is not None:
                    rights_ref = timeline_payload.get("audio_rights_manifest")
                    map_ref = timeline_payload.get("music_event_map")
                    rights_payload: dict | None = None
                    if isinstance(rights_ref, str) and rights_ref.strip():
                        rights_file = (timeline_file.parent / rights_ref).resolve()
                        if not rights_file.is_file():
                            errors.append(f"{cycle_id}: audio_rights_manifest file does not exist")
                        else:
                            rights_payload = json.loads(rights_file.read_text(encoding="utf-8"))
                            source_ref = rights_payload.get("source_file")
                            if isinstance(source_ref, str) and source_ref.strip():
                                source_path = Path(source_ref)
                                if not source_path.is_absolute():
                                    rights_payload["source_file"] = str((rights_file.parent / source_path).resolve())
                            rights_errors = validate_audio_rights(rights_payload, check_file=True)
                            errors.extend(f"{cycle_id}: audio_rights_manifest: {error}" for error in rights_errors)
                    if isinstance(map_ref, str) and map_ref.strip():
                        map_file = (timeline_file.parent / map_ref).resolve()
                        if not map_file.is_file():
                            errors.append(f"{cycle_id}: music_event_map file does not exist")
                        else:
                            map_payload = json.loads(map_file.read_text(encoding="utf-8"))
                            visual_event_ids = {
                                event.get("event_id")
                                for event in timeline_payload.get("events", [])
                                if isinstance(event, dict)
                            }
                            map_errors = validate_music_event_map(map_payload, visual_event_ids)
                            errors.extend(f"{cycle_id}: music_event_map: {error}" for error in map_errors)
                            if isinstance(rights_ref, str) and rights_ref.strip():
                                linked_rights = (map_file.parent / str(map_payload.get("audio_rights_manifest", ""))).resolve()
                                if linked_rights != (timeline_file.parent / rights_ref).resolve():
                                    errors.append(f"{cycle_id}: music_event_map must link the same audio_rights_manifest")
                            if rights_payload is not None and map_payload.get("audio_file_sha256", "").lower() != rights_payload.get("sha256", "").lower():
                                errors.append(f"{cycle_id}: music_event_map audio hash must match audio_rights_manifest")

    progress = ledger["user_promotion_progress"]
    if int(progress["accepted"]) != len(accepted_situations):
        errors.append(
            "user_promotion_progress.accepted must equal unique accepted "
            "promotion_situation_id count"
        )
    if int(progress["required"]) != 3:
        errors.append("required promotion situations must remain 3")
    operator_progress = ledger.get("operator_promotion_progress")
    if not isinstance(operator_progress, dict):
        errors.append("operator_promotion_progress must be an object")
    else:
        expected_operator_ids = set(accepted_situations_by_operator)
        if set(operator_progress) != expected_operator_ids:
            errors.append(
                "operator_promotion_progress keys must equal Operators with accepted increments"
            )
        for operator_id, situation_ids in accepted_situations_by_operator.items():
            entry = operator_progress.get(operator_id)
            if not isinstance(entry, dict):
                continue
            reported_ids = entry.get("accepted_situation_ids")
            if not isinstance(reported_ids, list) or set(reported_ids) != situation_ids:
                errors.append(
                    f"operator_promotion_progress.{operator_id}.accepted_situation_ids mismatch"
                )
            if int(entry.get("accepted", -1)) != len(situation_ids):
                errors.append(
                    f"operator_promotion_progress.{operator_id}.accepted mismatch"
                )
            if int(entry.get("required", -1)) != 3:
                errors.append(
                    f"operator_promotion_progress.{operator_id}.required must be 3"
                )
    if decision_contract.get("version") != "1.1":
        errors.append("decision_contract.version must be 1.1")
    if decision_contract.get("required_axis_count") != 10:
        errors.append("decision_contract.required_axis_count must be 10")
    if not strict_started:
        errors.append("decision_contract.enforced_from_cycle_id was not found")

    print(
        json.dumps(
            {
                "valid": not errors,
                "cycle_count": len(ledger["cycles"]),
                "operator_count": len(registry_ids),
                "legacy_fallback_operator_count": len(legacy_ids),
                "unique_accepted_situations": len(accepted_situations),
                "accepted_situations_by_operator": {
                    operator_id: len(situations)
                    for operator_id, situations in sorted(accepted_situations_by_operator.items())
                },
                "strict_decision_contract_cycles": strict_cycle_count,
                "errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
