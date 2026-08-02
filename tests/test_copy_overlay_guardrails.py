from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDERER = (
    ROOT
    / "skill-package"
    / "haku-tool"
    / "scripts"
    / "render_composite_proof_recipe.py"
)
RECIPE = ROOT / "proofs" / "beach-meaningful-copy-v002" / "recipe.json"


def load_renderer():
    spec = importlib.util.spec_from_file_location("haku_composite_renderer", RENDERER)
    if spec is None or spec.loader is None:
        raise RuntimeError("renderer import failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def must_reject(renderer, recipe: dict, label: str) -> None:
    try:
        renderer.validate(RECIPE, recipe)
    except ValueError:
        return
    raise AssertionError(f"validator accepted invalid copy-overlay mutation: {label}")


def main() -> int:
    renderer = load_renderer()
    canonical = json.loads(RECIPE.read_text(encoding="utf-8"))
    renderer.validate(RECIPE, canonical)

    invalid_font = copy.deepcopy(canonical)
    invalid_font["variants"]["proof"]["segments"][0]["copies"][0]["font"] = "remote"
    must_reject(renderer, invalid_font, "unapproved font")

    multiline = copy.deepcopy(canonical)
    multiline["variants"]["proof"]["segments"][0]["copies"][0]["text"] = "A\nB"
    must_reject(renderer, multiline, "multiline copy")

    out_of_range = copy.deepcopy(canonical)
    out_of_range["variants"]["proof"]["segments"][0]["copies"][0][
        "active_frames"
    ] = [0, 25]
    must_reject(renderer, out_of_range, "active range beyond segment")

    empty = copy.deepcopy(canonical)
    empty["variants"]["proof"]["segments"][0]["copies"][0]["text"] = " "
    must_reject(renderer, empty, "empty copy")

    bad_weight = copy.deepcopy(canonical)
    bad_weight["variants"]["proof"]["segments"][0]["copies"][0][
        "font_weight"
    ] = "semibold"
    must_reject(renderer, bad_weight, "unapproved font weight")

    bad_shadow = copy.deepcopy(canonical)
    bad_shadow["variants"]["proof"]["segments"][0]["copies"][0][
        "shadow_opacity"
    ] = 1.0
    must_reject(renderer, bad_shadow, "unsafe shadow opacity")

    print("PASS: canonical accepted; six copy-overlay mutations rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
