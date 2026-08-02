from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "skill-package"
    / "haku-tool"
    / "scripts"
    / "render_composite_proof_recipe.py"
)
RECIPE = ROOT / "proofs" / "picnic-sensory-scale-v001" / "recipe.json"
SPEC = importlib.util.spec_from_file_location("render_composite_proof_recipe", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


canonical = json.loads(RECIPE.read_text(encoding="utf-8"))
for variant in ("plain", "proof"):
    segment = canonical["variants"][variant]["segments"][0]
    segment["type"] = "fit-single"
    segment["canvas_color"] = "0x080808"
MODULE.validate(RECIPE, canonical)

invalid = copy.deepcopy(canonical)
invalid["variants"]["proof"]["segments"][0]["canvas_color"] = "black"
try:
    MODULE.validate(RECIPE, invalid)
except ValueError as error:
    assert "0xRRGGBB" in str(error)
else:
    raise AssertionError("fit-single accepted an unbounded canvas color")

print("fit-single guardrails: pass")
