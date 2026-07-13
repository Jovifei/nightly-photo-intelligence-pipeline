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
    return out


def redact_path(path: Path | str, source_root: Path | None = None) -> str:
    """Return a redacted, display-safe representation of *path*.

    If *path* is under *source_root*, only the relative tail is shown prefixed
    with the redaction token. Otherwise the raw path is passed through
    :func:`redact_text` to scrub home/username segments.
    """
    p = Path(path)
    if source_root is not None:
        try:
            rel = p.resolve().relative_to(Path(source_root).resolve())
            if rel == Path("."):
                return REDACT_PATH.rsplit("/", 1)[0]
            return f"{REDACT_PATH.rsplit('/', 1)[0]}/{rel.as_posix()}"
        except ValueError:
            pass
    return redact_text(str(p), source_root=source_root)


REDACT_RUNTIME_ROOT = "<RUNTIME_ROOT>"


def redact_hostname(name: str | None) -> str:
    """Redact a hostname string; None becomes an empty string."""
    if not name:
        return ""
    return REDACT_HOSTNAME
