#!/usr/bin/env python3
"""Sensitive file scanner for the nightly-photo-intelligence-pipeline repo.

This is a read-only, standard-library-only guard executed as part of the
``make quality`` command before commits. It refuses to modify, delete, or
move any file, and it never touches the network. It flags files that must
never be committed at the N0 stage:

* databases, logs, model weights
* image derivatives (except the 3 authorised synthetic PNG fixtures)
* secrets / keys / tokens / credentials
* personal absolute paths embedded in text files
* private-key PEM blocks embedded in text files
* files larger than 5 MiB (with a small allow-list)

Exit codes:
    0  no violations
    1  one or more violations found
    2  scanner itself failed
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

MAX_FILE_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MiB

# Directories that we always skip when walking the filesystem (fallback mode).
SKIP_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "venv",
        "node_modules",
        ".idea",
        ".vscode",
    }
)

# Private-key PEM markers to search for inside text files.
PRIVATE_KEY_MARKERS: tuple[str, ...] = (
    "-----BEGIN " + "PRIVATE KEY-----",
    "-----BEGIN " + "OPENSSH PRIVATE KEY-----",
    "-----BEGIN " + "RSA PRIVATE KEY-----",
)

# File-extension → violation category (lower-case, includes the leading dot).
DATABASE_EXTS: frozenset[str] = frozenset({".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm"})
LOG_EXTS: frozenset[str] = frozenset({".log"})
MODEL_WEIGHT_EXTS: frozenset[str] = frozenset(
    {
        ".pt",
        ".pth",
        ".ckpt",
        ".safetensors",
        ".onnx",
        ".engine",
        ".npy",
        ".npz",
    }
)
IMAGE_DERIV_EXTS: frozenset[str] = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".heic",
        ".webp",
        ".tif",
        ".tiff",
        ".bmp",
        ".avif",
    }
)
KEY_CRED_EXTS: frozenset[str] = frozenset({".pem", ".key", ".p12", ".pfx"})

# Suspicious substrings in filenames (case-insensitive).
CREDENTIAL_NAME_SUBSTRINGS: tuple[str, ...] = ("token", "secret", "credentials")

# Allow-lists for the special rules.
ALLOWED_PNGS: frozenset[str] = frozenset(
    {
        "fixtures/three_image_smoke_set/fixture_a_corridor_abstract.png",
        "fixtures/three_image_smoke_set/fixture_a_exact_copy.png",
        "fixtures/three_image_smoke_set/fixture_b_tonal_abstract.png",
    }
)

# Files/paths exempt from the > 5 MiB rule.
LARGE_FILE_EXEMPT_FILES: frozenset[str] = frozenset({"MANIFEST.sha256"})
LARGE_FILE_EXEMPT_PREFIXES: tuple[str, ...] = (
    "fixtures/three_image_smoke_set/",
    "examples/",
)

# Content-scan personal-path regexes.
#
# Windows: ``C:\Users\<name>\`` where <name> is neither the literal placeholder
# nor common test tokens. We must not fire on already-redacted docs.
_WIN_USER_RE: re.Pattern[str] = re.compile(
    r"[A-Za-z]:\\Users\\(?!<USER_REDACTED>|<HOST_REDACTED>|owner(?:\\|$))"
    r"[A-Za-z0-9._-]+\\"
)
# Same intent but for text that only escapes a single backslash (JSON, YAML …).
_WIN_USER_ESCAPED_RE: re.Pattern[str] = re.compile(
    r"[A-Za-z]:\\\\Users\\\\(?!<USER_REDACTED>|<HOST_REDACTED>|owner(?:\\\\|$))"
    r"[A-Za-z0-9._-]+\\\\"
)
# POSIX: /home/<name>/ — same allow-list.
_POSIX_HOME_RE: re.Pattern[str] = re.compile(
    r"/home/(?!<USER_REDACTED>|<HOST_REDACTED>|owner(?:/|$))"
    r"[A-Za-z0-9._-]+/"
)


# ---------------------------------------------------------------------------
# File enumeration
# ---------------------------------------------------------------------------


def _git_tracked_files(root: Path) -> list[Path] | None:
    """Return the list of files git tracks or would track, or ``None`` if unavailable.

    Uses ``git ls-files --cached --others --exclude-standard`` (no network,
    read-only). This covers staged files plus untracked files that are not
    gitignored - i.e. everything that could be committed. Returns ``None`` when
    git is missing, when the directory is not a git repo, or when the command
    fails.
    """
    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            capture_output=True,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return None
    if completed.returncode != 0:
        return None
    raw = completed.stdout
    if not raw:
        return []
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError:
        decoded = raw.decode("utf-8", errors="replace")
    entries = [chunk for chunk in decoded.split("\x00") if chunk]
    return [root / rel for rel in entries]


def _walk_fallback(root: Path) -> list[Path]:
    """Fallback file enumeration when git is not available.

    Skips well-known metadata / cache directories in-place so we do not descend
    into them.
    """
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Mutate ``dirnames`` in-place so ``os.walk`` skips these subtrees.
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for name in filenames:
            out.append(Path(dirpath) / name)
    return out


def enumerate_files(root: Path) -> list[Path]:
    """Return the ordered list of files to scan under ``root``."""
    tracked = _git_tracked_files(root)
    files = [p for p in tracked if p.is_file()] if tracked is not None else _walk_fallback(root)
    files.sort()
    return files


# ---------------------------------------------------------------------------
# Rule evaluation
# ---------------------------------------------------------------------------


def _rel_posix(path: Path, root: Path) -> str:
    """Return ``path`` relative to ``root`` in POSIX form."""
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        rel = path
    return Path(rel).as_posix()


def _name_violations(rel: str, name: str, suffix: str) -> list[str]:
    """Return reasons why the file's *name* or *extension* is disallowed."""
    reasons: list[str] = []
    lower_name = name.lower()
    lower_suffix = suffix.lower()

    if lower_suffix in DATABASE_EXTS:
        reasons.append(f"database file extension '{lower_suffix}'")
    if lower_suffix in LOG_EXTS:
        reasons.append(f"log file extension '{lower_suffix}'")
    if lower_suffix in MODEL_WEIGHT_EXTS:
        reasons.append(f"model weight extension '{lower_suffix}'")
    if lower_suffix in IMAGE_DERIV_EXTS:
        reasons.append(f"image derivative extension '{lower_suffix}'")

    # PNG special rule.
    if lower_suffix == ".png" and rel not in ALLOWED_PNGS:
        reasons.append("PNG outside the 3-fixture allow-list")

    # Key / cert extensions.
    if lower_suffix in KEY_CRED_EXTS:
        reasons.append(f"key/credential extension '{lower_suffix}'")

    # Credential-ish filenames.
    for token in CREDENTIAL_NAME_SUBSTRINGS:
        if token in lower_name:
            reasons.append(f"suspicious credential filename token '{token}'")
            break

    # .env / .env.* rule, allowing .env.example.
    if lower_name == ".env":
        reasons.append(".env file")
    elif lower_name.startswith(".env.") and lower_name != ".env.example":
        reasons.append(f"dotenv variant '{lower_name}'")

    return reasons


def _size_violation(rel: str, size: int) -> str | None:
    """Return a reason if the file is over-size and not exempt, else ``None``."""
    if size <= MAX_FILE_SIZE_BYTES:
        return None
    if rel in LARGE_FILE_EXEMPT_FILES:
        return None
    for prefix in LARGE_FILE_EXEMPT_PREFIXES:
        if rel.startswith(prefix):
            return None
    return f"file size {size} bytes exceeds 5 MiB threshold"


def _content_violations(path: Path) -> list[str]:
    """Return reasons discovered by scanning the file's text content.

    Binary files (files that cannot be decoded as UTF-8) are skipped and
    return an empty list; the caller has already applied the filename and
    size checks.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    reasons: list[str] = []
    for marker in PRIVATE_KEY_MARKERS:
        if marker in text:
            reasons.append(f"private key marker '{marker}'")

    if _WIN_USER_RE.search(text) or _WIN_USER_ESCAPED_RE.search(text):
        reasons.append("personal Windows user path (C:\\Users\\<name>\\)")
    if _POSIX_HOME_RE.search(text):
        reasons.append("personal POSIX home path (/home/<name>/)")

    return reasons


def scan_file(path: Path, root: Path) -> list[tuple[str, str]]:
    """Scan a single file and return the list of ``(rel_path, reason)`` tuples."""
    rel = _rel_posix(path, root)
    try:
        size = path.stat().st_size
    except OSError as exc:
        return [(rel, f"cannot stat file: {exc}")]

    findings: list[tuple[str, str]] = []
    for reason in _name_violations(rel, path.name, path.suffix):
        findings.append((rel, reason))

    size_reason = _size_violation(rel, size)
    if size_reason is not None:
        findings.append((rel, size_reason))

    for reason in _content_violations(path):
        findings.append((rel, reason))

    return findings


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def scan(root: Path) -> list[tuple[str, str]]:
    """Scan the tree at ``root`` and return every violation found."""
    files = enumerate_files(root)
    findings: list[tuple[str, str]] = []
    for path in files:
        try:
            findings.extend(scan_file(path, root))
        except OSError as exc:
            rel = _rel_posix(path, root)
            findings.append((rel, f"cannot read file: {exc}"))
    findings.sort(key=lambda item: (item[0], item[1]))
    return findings


def report(findings: Sequence[tuple[str, str]], stream: os.PathLike[str] | None = None) -> None:
    """Print ``findings`` in the required ``VIOLATION:`` line format."""
    del stream  # unused; kept for a stable signature
    for rel, reason in findings:
        print(f"VIOLATION: {rel} - {reason}")
    print(f"Summary: {len(findings)} violation(s)")


def main(argv: Iterable[str] | None = None) -> int:
    """Entry point. Ignores CLI arguments; kept for a stable signature."""
    del argv
    try:
        findings = scan(ROOT)
    except Exception as exc:  # pragma: no cover - defensive: signal a scanner bug
        print(f"sensitive_file_scan: internal error: {exc}", file=sys.stderr)
        return 2
    report(findings)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
