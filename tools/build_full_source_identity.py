#!/usr/bin/env python3
"""Print full clean-HEAD identity. Redirect stdout OUTSIDE every Git worktree."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    from nightly_photo_intelligence_pipeline.engineering.common import EngineeringError
    from nightly_photo_intelligence_pipeline.engineering.source_identity import full_source_identity

    try:
        result = full_source_identity(ROOT)
    except (EngineeringError, OSError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "result": "SOURCE_BINDING_FAILED",
                    "execution_authorized": False,
                    "code": str(exc)
                    if isinstance(exc, EngineeringError)
                    else "NPI_GIT_UNAVAILABLE",
                }
            )
        )
        return 3
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
