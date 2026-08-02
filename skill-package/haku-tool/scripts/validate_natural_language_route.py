#!/usr/bin/env python3
"""Validate a Haku natural-language route without changing its review state."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from route_natural_language_request import load_json, validate_registry, validate_route


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("route", type=Path)
    parser.add_argument(
        "--registry",
        type=Path,
        default=script_dir.parent / "references" / "natural-language-routing-registry.json",
    )
    args = parser.parse_args()
    try:
        route = load_json(args.route.resolve())
        registry = load_json(args.registry.resolve())
        validate_registry(registry)
        validate_route(route, registry)
        print(json.dumps({"valid": True, "route": str(args.route.resolve())}))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
