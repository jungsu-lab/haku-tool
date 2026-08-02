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
RECIPE = ROOT / "proofs" / "rainbow-luminous-relay-v002" / "recipe.json"


def load_renderer():
    spec = importlib.util.spec_from_file_location("haku_range_renderer", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("renderer import failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    renderer = load_renderer()
    canonical = json.loads(RECIPE.read_text(encoding="utf-8"))
    generous = {material_id: 1000.0 for material_id in canonical["materials"]}
    renderer.validate_source_range_durations(canonical, generous)

    overflow = copy.deepcopy(canonical)
    overflow["materials"]["open_palm_release"]["source_in"] = 999.5
    try:
        renderer.validate_source_range_durations(overflow, generous)
    except ValueError as error:
        if "exceeds source duration" not in str(error):
            raise
    else:
        raise AssertionError("source duration overflow was accepted")

    print("source range guardrails: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
