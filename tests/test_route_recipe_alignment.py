#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skill-package" / "haku-tool" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load_module():
    path = SCRIPTS / "validate_route_recipe_alignment.py"
    spec = importlib.util.spec_from_file_location("haku_route_recipe_alignment", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = load_module()
    proof = ROOT / "proofs" / "park-density-wave-v001"
    route = json.loads((proof / "natural-language-route-v005.json").read_text(encoding="utf-8"))
    recipe = json.loads((proof / "recipe-v005.json").read_text(encoding="utf-8"))
    timeline = json.loads((proof / "timeline-grammar-v005.json").read_text(encoding="utf-8"))
    result = module.validate_alignment(route, recipe, timeline)
    assert result["primary_operator_id"] == "density-wave-release"
    assert result["timeline_event_count"] == 3
    assert result["axis_count_per_event"] == 10
    assert result["promotion_increment"] == 0

    picnic = ROOT / "proofs" / "picnic-density-wave-v001"
    picnic_result = module.validate_alignment(
        json.loads((picnic / "natural-language-route.json").read_text(encoding="utf-8")),
        json.loads((picnic / "recipe.json").read_text(encoding="utf-8")),
        json.loads((picnic / "timeline-grammar.json").read_text(encoding="utf-8")),
    )
    assert picnic_result["primary_operator_id"] == "density-wave-release"
    assert picnic_result["recipe_operator_ids"] == [
        "density-wave-release",
        "sensory-scale-relay",
        "functional-memory-panels",
    ]
    assert picnic_result["timeline_event_count"] == 3

    tampered = json.loads(json.dumps(recipe))
    tampered["operator"]["primary"] = "experience-before-product"
    try:
        module.validate_alignment(route, tampered, timeline)
    except ValueError:
        pass
    else:
        raise AssertionError("tampered recipe primary was accepted")
    print("route-recipe alignment: park and picnic canonical routes passed; tampered primary rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
