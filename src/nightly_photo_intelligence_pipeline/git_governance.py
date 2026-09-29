"""Read-only Git topology checks shared by preflight and review tools."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_SHA1 = re.compile(r"^[0-9a-f]{40}$")


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def linear_history_findings(root: Path, baseline_sha: str, tip: str = "HEAD") -> list[str]:
    """Return baseline, merge, and parent-graph violations for a candidate range."""

    if not _SHA1.fullmatch(baseline_sha):
        return ["baseline is not a full Git SHA"]
    if tip != "HEAD" and not _SHA1.fullmatch(tip):
        return ["candidate tip is not a full Git SHA"]
    ancestry = _run_git(root, "merge-base", "--is-ancestor", baseline_sha, tip)
    if ancestry is None:
        return ["cannot inspect baseline ancestry"]
    if ancestry.returncode != 0:
        return ["immutable baseline is not an ancestor of HEAD"]

    results: dict[str, subprocess.CompletedProcess[str]] = {}
    for label, args in (
        ("merge commits", ["rev-list", "--merges", f"{baseline_sha}..{tip}"]),
        ("parent graph", ["rev-list", "--parents", f"{baseline_sha}..{tip}"]),
    ):
        result = _run_git(root, *args)
        if result is None or result.returncode != 0:
            return [f"cannot inspect {label}"]
        results[label] = result

    findings: list[str] = []
    if results["merge commits"].stdout.strip():
        findings.append("candidate range contains a merge commit")
    graph = results["parent graph"].stdout.splitlines()
    if any(len(row.split()) != 2 for row in graph):
        findings.append("candidate range is not one-parent linear history")
    return findings
