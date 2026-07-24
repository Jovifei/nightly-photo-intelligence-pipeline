#!/usr/bin/env python3
"""Scan every tracked JSON document with the fail-closed duplicate-member parser.

Fixtures below ``tests/fixtures/invalid_json`` are intentional negative inputs:
they are reported separately and do not make the production scan fail.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nightly_photo_intelligence_pipeline.domain.errors import (  # noqa: E402
    DuplicateJsonMemberError,
)
from nightly_photo_intelligence_pipeline.json_strict import load_json_strict  # noqa: E402

EXPECTED_INVALID_PREFIX = Path("tests") / "fixtures" / "invalid_json"


def _tracked_json_files() -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--", "*.json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [Path(line) for line in result.stdout.splitlines() if line]


def _is_expected_invalid(path: Path) -> bool:
    try:
        path.relative_to(EXPECTED_INVALID_PREFIX)
    except ValueError:
        return False
    return True


def main() -> int:
    tracked = _tracked_json_files()
    expected_invalid = 0
    production_duplicates = 0
    malformed = 0
    for relative in tracked:
        try:
            load_json_strict(ROOT / relative)
        except DuplicateJsonMemberError:
            if _is_expected_invalid(relative):
                expected_invalid += 1
            else:
                production_duplicates += 1
        except (OSError, UnicodeError, ValueError):
            malformed += 1
    print(
        "JSON_STRICT_SCAN "
        f"tracked={len(tracked)} expected_invalid_duplicates={expected_invalid} "
        f"production_duplicates={production_duplicates} malformed={malformed}"
    )
    return 1 if production_duplicates or malformed else 0


if __name__ == "__main__":
    raise SystemExit(main())
