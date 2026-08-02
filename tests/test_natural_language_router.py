#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill-package" / "haku-tool" / "scripts" / "route_natural_language_request.py"
REGISTRY = ROOT / "skill-package" / "haku-tool" / "references" / "natural-language-routing-registry.json"
CASES = Path(__file__).with_name("natural-language-routing-cases.json")


def load_module():
    spec = importlib.util.spec_from_file_location("haku_natural_language_router", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = load_module()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    fixture = json.loads(CASES.read_text(encoding="utf-8"))
    module.validate_registry(registry)
    for case in fixture["cases"]:
        route = module.route_request(case["request"], registry)
        module.validate_route(route, registry)
        assert route["selected"]["primary_operator_id"] == case["expected_primary"], case["name"]
        assert route["route_status"] == case["expected_status"], case["name"]
        assert list(route["selected"]["ten_axis_intents"].keys()) == list(module.AXES), case["name"]
        assert route["promotion_gate"]["user_verdict"] == "pending", case["name"]
        assert route["promotion_gate"]["promotion_increment"] == 0, case["name"]
        assert set(route["treatments"]) == {"safe", "recommended", "experimental"}, case["name"]

    unsafe = json.loads(json.dumps(fixture["cases"][0]["request"]))
    unsafe["request_id"] = "route-existing-edit-rejection"
    unsafe["material_observations"]["existing_edit_detected"] = True
    rejected = module.route_request(unsafe, registry)
    assert rejected["route_status"] == "source_rejected_existing_edit"

    unverified = json.loads(json.dumps(fixture["cases"][0]["request"]))
    unverified["request_id"] = "route-rights-gate"
    unverified["source_rights"]["status"] = "unverified"
    gated = module.route_request(unverified, registry)
    assert gated["route_status"] == "needs_rights_verification"

    print("natural language router: four creative routes and two fail-closed gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
