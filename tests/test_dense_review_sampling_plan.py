from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "skill-package"
    / "haku-tool"
    / "scripts"
    / "build_dense_review_sheet.py"
)
SPEC = importlib.util.spec_from_file_location("build_dense_review_sheet", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def expect_error(*args: object) -> None:
    try:
        MODULE.choose_sampling_plan(*args)
    except ValueError:
        return
    raise AssertionError(f"expected ValueError for {args!r}")


fps, count = MODULE.choose_sampling_plan(600.0, 4.0, 160)
assert count == 160
assert abs(fps - (160 / 600.0)) < 1e-9

fps, count = MODULE.choose_sampling_plan(7.2, 10.0, 80)
assert fps == 10.0
assert count == 72

fps, count = MODULE.choose_sampling_plan(0.0, 4.0, 1)
assert count == 1
assert fps == 4.0

expect_error(-1.0, 4.0, 160)
expect_error(10.0, 0.0, 160)
expect_error(10.0, 4.0, 0)

print("dense review sampling plan guardrails: pass")
