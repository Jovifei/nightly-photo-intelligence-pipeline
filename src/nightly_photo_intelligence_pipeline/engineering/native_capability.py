"""Classify one observed native test gap; never grant or change OS privileges."""

from __future__ import annotations


def symlink_privilege_gap(error: OSError, *, platform: str) -> str | None:
    """Only Windows ERROR_PRIVILEGE_NOT_HELD is an accepted privilege skip.

    An arbitrary OSError does not prove a privilege problem. A missing path,
    access-denied ACL, sharing violation, invalid argument, or non-Windows
    failure must be reported as its original failure, not silently skipped.
    The returned diagnostic never embeds exception text or a private path.
    """
    winerror = getattr(error, "winerror", None)
    if platform != "win32" or type(winerror) is not int or winerror != 1314:
        return None
    errno = error.errno if type(error.errno) is int else "unknown"
    return f"native symlink privilege unavailable: platform=win32 winerror=1314 errno={errno}"
