#!/usr/bin/env python3
"""Model-free readiness. Usage: python tools/engineering_precheck.py [--ollama-metadata]."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    from nightly_photo_intelligence_pipeline.engineering.common import EngineeringError
    from nightly_photo_intelligence_pipeline.engineering.readiness import readiness

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ollama-metadata", action="store_true")
    args = parser.parse_args()
    try:
        result = readiness(ROOT / "pyproject.toml", probe_ollama=args.ollama_metadata)
    except (EngineeringError, OSError, KeyError, ValueError) as exc:
        code = str(exc) if isinstance(exc, EngineeringError) else "NPI_PRECHECK_INPUT_UNAVAILABLE"
        result = {"result": "BLOCKED_ENVIRONMENT", "code": code, "execution_authorized": False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["result"] == "READY_FOR_CODE_CHECKS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
