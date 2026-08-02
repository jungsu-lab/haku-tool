#!/usr/bin/env python3
"""Route a reviewed natural-language Haku request to evidence-backed Operators.

This router is intentionally fail-closed. It selects editing grammar; it does not
analyze video, invent missing coverage, approve an Operator, or render media.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


AXES = (
    "narrative",
    "shot",
    "cut",
    "timing",
    "transition",
    "text",
    "color",
    "audio",
    "motion",
    "purpose",
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower()
    return re.sub(r"\s+", " ", value).strip()


def validate_registry(registry: dict[str, Any]) -> None:
    if registry.get("schema_version") != "1.0":
        raise ValueError("routing registry schema_version must be 1.0")
    operators = registry.get("operators")
    if not isinstance(operators, list) or not operators:
        raise ValueError("routing registry must contain operators")
    seen: set[str] = set()
    for operator in operators:
        operator_id = operator.get("id")
        if not isinstance(operator_id, str) or not operator_id:
            raise ValueError("every routing operator needs an id")
        if operator_id in seen:
            raise ValueError(f"duplicate routing operator: {operator_id}")
        seen.add(operator_id)
        axis_intents = operator.get("axis_intents", {})
        if tuple(axis_intents.keys()) != AXES:
            raise ValueError(f"{operator_id} must define the ten axes in canonical order")


def validate_request(request: dict[str, Any]) -> None:
    if request.get("schema_version") != "1.0":
        raise ValueError("request schema_version must be 1.0")
    if not str(request.get("request_id", "")).strip():
        raise ValueError("request_id is required")
    if not str(request.get("natural_language", "")).strip():
        raise ValueError("natural_language is required")
    if not str(request.get("purpose", "")).strip():
        raise ValueError("purpose is required")
    observations = request.get("material_observations")
    if not isinstance(observations, dict):
        raise ValueError("material_observations must be an object")
    tags = observations.get("tags", [])
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise ValueError("material_observations.tags must be a string array")


def material_fit(operator: dict[str, Any], tags: set[str]) -> dict[str, Any]:
    missing_all = [tag for tag in operator.get("required_all", []) if tag not in tags]
    missing_any: list[list[str]] = []
    for group in operator.get("required_any", []):
        if not any(tag in tags for tag in group):
            missing_any.append(list(group))
    missing = missing_all + ["one_of:" + "|".join(group) for group in missing_any]
    return {
        "status": "pass" if not missing else "insufficient_coverage",
        "missing_required": missing,
        "matched_required_count": (
            len(operator.get("required_all", [])) - len(missing_all)
            + len(operator.get("required_any", [])) - len(missing_any)
        ),
    }


def semantic_score(
    operator: dict[str, Any], text: str, purpose: str, explicit_operator_id: str | None
) -> tuple[int, list[str], list[str]]:
    matched_phrases = [phrase for phrase in operator.get("phrases", []) if normalize(phrase) in text]
    matched_keywords = [keyword for keyword in operator.get("keywords", []) if normalize(keyword) in text]
    score = 5 * len(matched_phrases) + len(matched_keywords)
    if purpose in operator.get("purposes", []):
        score += 2
    if explicit_operator_id == operator.get("id"):
        score += 1000
    return score, matched_phrases, matched_keywords


def route_request(request: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    validate_registry(registry)
    validate_request(request)

    text = normalize(str(request["natural_language"]))
    purpose = normalize(str(request["purpose"]))
    observations = request["material_observations"]
    tags = {normalize(tag).replace(" ", "_") for tag in observations.get("tags", [])}
    explicit = request.get("explicit_operator_id")
    operators = registry["operators"]
    operator_ids = {operator["id"] for operator in operators}
    if explicit is not None and explicit not in operator_ids:
        raise ValueError(f"unknown explicit_operator_id: {explicit}")

    ranked: list[dict[str, Any]] = []
    for operator in operators:
        score, phrases, keywords = semantic_score(operator, text, purpose, explicit)
        fit = material_fit(operator, tags)
        ranked.append(
            {
                "operator_id": operator["id"],
                "semantic_score": score,
                "matched_phrases": phrases,
                "matched_keywords": keywords,
                "material_fit": fit,
                "operator_status": operator["status"],
                "axis_intents": operator["axis_intents"],
            }
        )
    ranked.sort(
        key=lambda item: (
            item["semantic_score"],
            item["material_fit"]["matched_required_count"],
            item["operator_id"],
        ),
        reverse=True,
    )

    semantic_candidates = [item for item in ranked if item["semantic_score"] > 0]
    primary = semantic_candidates[0] if semantic_candidates else None
    supporting = [
        item
        for item in semantic_candidates[1:]
        if item["semantic_score"] >= 2 and item["material_fit"]["status"] == "pass"
    ][:3]

    rights_status = request.get("source_rights", {}).get("status", "unverified")
    reviewed = observations.get("reviewed_by_main_agent") is True
    existing_edit = observations.get("existing_edit_detected")
    if rights_status != "verified":
        route_status = "needs_rights_verification"
        next_action = "권리 상태와 source-manifest를 검증한 뒤 다시 라우팅한다."
    elif existing_edit is True:
        route_status = "source_rejected_existing_edit"
        next_action = "기존 컷·자막·속도 변화·합성이 없는 원본을 확보한다."
    elif not reviewed or existing_edit is None or not tags:
        route_status = "needs_source_review"
        next_action = "주 에이전트가 원본 전체를 직접 보고 material tags와 기존 편집 여부를 기록한다."
    elif primary is None:
        route_status = "no_semantic_match"
        next_action = "Haku Operator를 억지로 적용하지 말고 단순 관찰 편집 또는 다른 스타일 팩을 사용한다."
    elif primary["material_fit"]["status"] != "pass":
        route_status = "needs_coverage_or_smaller_operator"
        next_action = "누락 커버리지를 재촬영하거나 더 작은 Operator·단순 관찰 편집을 선택한다."
    else:
        route_status = "ready_for_treatment_choice"
        next_action = "safe·recommended·experimental 세 treatment를 비교한 뒤 recipe와 10축 timeline을 작성한다."

    primary_id = primary["operator_id"] if primary else None
    support_ids = [item["operator_id"] for item in supporting]
    treatments = {
        "safe": {
            "operators": [primary_id] if primary_id else [],
            "rule": "주 Operator 하나만 사용하고 화면 내부 밀도와 효과 수를 최소화한다.",
        },
        "recommended": {
            "operators": ([primary_id] if primary_id else []) + support_ids[:1],
            "rule": "주 Operator의 인과를 유지하면서 검증된 supporting Operator 하나만 결합한다.",
        },
        "experimental": {
            "operators": ([primary_id] if primary_id else []) + support_ids,
            "rule": "추가 밀도는 별도 가설로만 시험하고 plain과 분리 검증한다.",
        },
    }

    return {
        "schema_version": "1.0",
        "request_id": request["request_id"],
        "account": registry["account"],
        "request": {
            "natural_language": request["natural_language"],
            "purpose": request["purpose"],
            "target_duration_seconds": request.get("target_duration_seconds"),
            "audio_policy": request.get("audio_policy", "deferred_by_user"),
            "text_policy": request.get("text_policy", "only_if_semantically_required"),
        },
        "route_status": route_status,
        "selected": {
            "primary_operator_id": primary_id,
            "supporting_operator_ids": support_ids,
            "primary_material_fit": primary["material_fit"] if primary else None,
            "ten_axis_intents": primary["axis_intents"] if primary else None,
        },
        "ranked_candidates": ranked,
        "treatments": treatments,
        "next_action": next_action,
        "evidence_contract": {
            "registry": registry["evidence_registry"],
            "source_reviewed_by_main_agent": reviewed,
            "source_manifest": request.get("source_rights", {}).get("source_manifest"),
        },
        "promotion_gate": {
            "user_verdict": "pending",
            "promotion_increment": 0,
            "rule": "Only an explicit user accepted verdict in a distinct situation may increment the tested Operator.",
        },
    }


def validate_route(route: dict[str, Any], registry: dict[str, Any]) -> None:
    operator_ids = {operator["id"] for operator in registry["operators"]}
    selected = route.get("selected", {})
    primary = selected.get("primary_operator_id")
    if primary is not None and primary not in operator_ids:
        raise ValueError("route selected an operator absent from the routing registry")
    axes = selected.get("ten_axis_intents")
    if axes is not None and tuple(axes.keys()) != AXES:
        raise ValueError("selected route must contain exactly the canonical ten axes")
    gate = route.get("promotion_gate", {})
    if gate.get("user_verdict") != "pending" or gate.get("promotion_increment") != 0:
        raise ValueError("router must never infer user acceptance or promotion")
    if route.get("evidence_contract", {}).get("registry") != registry.get("evidence_registry"):
        raise ValueError("route must preserve the evidence registry link")


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--registry",
        type=Path,
        default=script_dir.parent / "references" / "natural-language-routing-registry.json",
    )
    args = parser.parse_args()
    try:
        request = load_json(args.request.resolve())
        registry = load_json(args.registry.resolve())
        route = route_request(request, registry)
        validate_route(route, registry)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(route, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print(
            json.dumps(
                {
                    "output": str(args.output.resolve()),
                    "route_status": route["route_status"],
                    "primary_operator_id": route["selected"]["primary_operator_id"],
                    "promotion_increment": 0,
                },
                ensure_ascii=False,
            )
        )
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
