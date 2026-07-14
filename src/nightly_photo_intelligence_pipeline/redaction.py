"""Path and PII redaction helpers.

All logs, error messages, and human-facing CLI output must pass through these
helpers so that absolute source paths, usernames, hostnames, and tokens never
leave the process. Redaction tokens match config/error_taxonomy.yaml.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from .domain.errors import REDACT_HOSTNAME, REDACT_PATH, REDACT_TOKEN, REDACT_USERNAME

# Matches a Windows drive-letter home prefix, single or double backslashes,
# forward slashes, any case. Captures the prefix up to and including the
# separator after "Users", so only the username segment is replaced.
_WINDOWS_HOME_RE: Final = re.compile(
    r"([A-Za-z]:[\\/]+Users[\\/]+)(?!<|owner(?:[\\/]|$))[A-Za-z0-9._-]+"
)
# Matches /home/<name>/ on POSIX.
_UNIX_HOME_RE: Final = re.compile(r"(/home/)(?!<)[A-Za-z0-9._-]+")
# Common token patterns.
_TOKEN_RE: Final = re.compile(r"(?i)(api[_-]?key|token|secret|password|bearer)\s*[:=]\s*\S+")
_WINDOWS_ABSOLUTE_RE: Final = re.compile(r"(?i)(?:\\\\\?\\)?[a-z]:[\\/][^\r\n\"'<>|]+")
_UNC_RE: Final = re.compile(r"(?i)(?:\\\\|//)[^\r\n\"'<>|]+")
_WSL_MOUNT_RE: Final = re.compile(r"(?i)/mnt/[a-z]/[^\r\n\"'<>|]+")
_IMAGE_FILENAME_RE: Final = re.compile(
    r"(?i)(?<![A-Za-z0-9_.-])[^\\/\r\n\"'<>|]*?"
    r"\.(?:jpe?g|png|heic|webp|tiff?|bmp|avif)\b"
)
REDACT_SOURCE_FILE: Final = "<SOURCE_FILE>"


def redact_text(text: str, source_root: Path | None = None) -> str:
    """Redact usernames, home paths, source roots, and token-like pairs in *text*."""
    if not text:
        return text
    out = text
    if source_root is not None:
        root_str = str(source_root)
        out = out.replace(root_str, REDACT_PATH.rsplit("/", 1)[0])
        # Also cover forward-slash form of the same root.
        out = out.replace(root_str.replace("\\", "/"), REDACT_PATH.rsplit("/", 1)[0])
    out = _WINDOWS_HOME_RE.sub(lambda m: m.group(1) + REDACT_USERNAME, out)
    out = _UNIX_HOME_RE.sub(lambda m: m.group(1) + REDACT_USERNAME, out)
    out = _TOKEN_RE.sub(lambda m: m.group(1) + "=<" + REDACT_TOKEN + ">", out)
    out = _WINDOWS_ABSOLUTE_RE.sub(REDACT_PATH, out)
    out = _UNC_RE.sub(REDACT_PATH, out)
    out = _WSL_MOUNT_RE.sub(REDACT_PATH, out)
    out = _IMAGE_FILENAME_RE.sub(REDACT_SOURCE_FILE, out)
    return out


def redact_path(path: Path | str, source_root: Path | None = None) -> str:
    """Return a redacted, display-safe representation of *path*.

    If *path* is under *source_root*, the real relative tail is discarded.
    Otherwise the raw path is passed through :func:`redact_text` to scrub
    absolute paths, image filenames, home directories, and usernames.
    """
    p = Path(path)
    if source_root is not None:
        try:
            rel = p.resolve().relative_to(Path(source_root).resolve())
            if rel == Path("."):
                return REDACT_PATH.rsplit("/", 1)[0]
            return f"{REDACT_PATH.rsplit('/', 1)[0]}/{REDACT_SOURCE_FILE}"
        except ValueError:
            pass
    if p.is_absolute():
        return REDACT_PATH
    return redact_text(str(p), source_root=source_root)


REDACT_RUNTIME_ROOT = "<RUNTIME_ROOT>"


def redact_hostname(name: str | None) -> str:
    """Redact a hostname string; None becomes an empty string."""
    if not name:
        return ""
    return REDACT_HOSTNAME
