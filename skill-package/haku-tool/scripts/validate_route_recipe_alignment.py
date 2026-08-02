#!/usr/bin/env python3
"""Validate natural-language route → recipe → ten-axis timeline traceability."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from route_natural_language_request import AXES, load_json


def recipe_operator_ids(recipe: dict[str, Any]) -> list[str]:
    operator = recipe.get("operator", {})
    values: list[str] = []
    for key in ("primary", "secondary"):
        value = operator.get(key)
        if isinstance(value, str) and value:
            values.append(value)
    for value in operator.get("supporting", []):
        if isinstance(value, str) and value:
            values.append(value)
    return list(dict.fromkeys(values))


def validate_alignment(
    route: dict[str, Any], recipe: dict[str, Any], timeline: dict[str, Any]
) -> dict[str, Any]:
    errors: list[str] = []
    selected = route.get("selected", {})
    primary = selected.get("primary_operator_id")
    selected_ids = {primary} if isinstance(primary, str) else set()
    selected_ids.update(selected.get("supporting_operator_ids", []))
    recipe_ids = recipe_operator_ids(recipe)
    recipe_primary = recipe.get("operator", {}).get("primary")
    if route.get("route_status") != "ready_for_treatment_choice":
        errors.append("route is not ready_for_treatment_choice")
    if recipe_primary != primary:
        errors.append(f"recipe primary {recipe_primary!r} does not match route primary {primary!r}")
    untraced = [operator_id for operator_id in recipe_ids if operator_id not in selected_ids]
    if untraced:
        errors.append("recipe operators absent from route: " + ", ".join(untraced))

    route_manifest = route.get("evidence_contract", {}).get("source_manifest")
    if recipe.get("source_manifest") != route_manifest:
        errors.append("recipe source_manifest does not match the routed reviewed source")
    if timeline.get("source_manifest") != route_manifest:
        errors.append("timeline source_manifest does not match the routed reviewed source")

    audio_values = {
        route.get("request", {}).get("audio_policy"),
        recipe.get("audio_policy"),
        timeline.get("audio_policy"),
    }
    if len(audio_values) != 1:
        errors.append("route, recipe, and timeline audio policies differ")

    events = timeline.get("events")
    if timeline.get("schema_version") != "1.1" or not isinstance(events, list) or not events:
        errors.append("timeline must be schema 1.1 with at least one event")
        events = []
    for event in events:
        event_id = event.get("event_id", "unknown")
        missing_axes = [axis for axis in AXES if axis not in event]
        if missing_axes:
            errors.append(f"{event_id} missing axes: {', '.join(missing_axes)}")
        missing_links = [link for link in event.get("operator_links", []) if link not in recipe_ids]
        if missing_links:
            errors.append(f"{event_id} links operators absent from recipe: {', '.join(missing_links)}")
        source_mapping = event.get("source_mapping", {})
        for key in (
            "source_path",
            "source_sha256",
            "source_frame_in",
            "source_frame_out_exclusive",
            "output_frame_in",
            "output_frame_out_exclusive",
        ):
            if key not in source_mapping:
                errors.append(f"{event_id} source_mapping missing {key}")

    gate = route.get("promotion_gate", {})
    if gate.get("user_verdict") != "pending" or gate.get("promotion_increment") != 0:
        errors.append("route improperly inferred user acceptance")
    if errors:
        raise ValueError("; ".join(errors))
    return {
        "valid": True,
        "primary_operator_id": primary,
        "recipe_operator_ids": recipe_ids,
        "timeline_event_count": len(events),
        "axis_count_per_event": len(AXES),
        "promotion_increment": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("route", type=Path)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("timeline", type=Path)
    args = parser.parse_args()
    try:
        result = validate_alignment(
            load_json(args.route.resolve()),
            load_json(args.recipe.resolve()),
            load_json(args.timeline.resolve()),
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
