"""Whole-plan path checks without walking photo directories.

These are preflight checks, not a claim of race-proof Windows I/O. The runtime
adapter must retain its existing bound-handle/reparse protections and call
recheck() immediately before each reservation/write. Do not use on untrusted
shared parents; native Windows handle-race tests remain a separate hard gate.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .common import EngineeringError, require


@dataclass(frozen=True)
class CheckedPath:
    path: Path
    existed: bool
    ancestors: tuple[tuple[Path, int, int], ...]


def _linked(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def checked_path(value: Path, *, must_exist: bool) -> CheckedPath:
    """Reject links before resolving, including all extant parents and junctions."""
    path = Path(value)
    require(path.is_absolute(), "NPI_PATH_NOT_ABSOLUTE")
    require(".." not in path.parts, "NPI_PATH_TRAVERSAL")
    text = str(path)
    require(not text.startswith(("\\\\", "//")), "NPI_NETWORK_PATH_DENIED")
    for part in path.parts[1:]:
        require(":" not in part, "NPI_ALTERNATE_STREAM_DENIED")
    entries: list[tuple[Path, int, int]] = []
    exists = False
    for component in reversed((path, *path.parents)):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise EngineeringError("NPI_PATH_UNAVAILABLE") from exc
        require(not _linked(info), "NPI_REPARSE_PATH_DENIED")
        require(stat.S_ISDIR(info.st_mode), "NPI_NOT_DIRECTORY")
        entries.append((component, info.st_dev, info.st_ino))
        if component == path:
            exists = True
    require(not must_exist or exists, "NPI_REQUIRED_ROOT_MISSING")
    require(bool(entries), "NPI_NO_EXISTING_PARENT")
    return CheckedPath(path=path, existed=exists, ancestors=tuple(entries))


def overlaps(left: Path, right: Path) -> bool:
    try:
        common = os.path.commonpath((os.path.normcase(str(left)), os.path.normcase(str(right))))
    except ValueError:
        return False
    return common in (os.path.normcase(str(left)), os.path.normcase(str(right)))


def validate_plan(
    *, inputs: Mapping[str, Path], outputs: Mapping[str, Path], protected: Mapping[str, Path]
) -> dict[str, CheckedPath]:
    """Every output must be fresh, disjoint, and outside ALL protected/input roots."""
    require(bool(inputs) and bool(outputs) and bool(protected), "NPI_PATH_PLAN_INCOMPLETE")
    labels = list(inputs) + list(outputs) + list(protected)
    require(len(labels) == len(set(labels)), "NPI_PATH_LABEL_COLLISION")
    result = {name: checked_path(path, must_exist=True) for name, path in inputs.items()}
    result.update({name: checked_path(path, must_exist=True) for name, path in protected.items()})
    blockers = list(result.values())
    out_values: list[CheckedPath] = []
    for name, path in outputs.items():
        item = checked_path(path, must_exist=False)
        require(not item.existed, "NPI_OUTPUT_ALREADY_EXISTS")
        require(
            all(not overlaps(item.path, other.path) for other in blockers + out_values),
            "NPI_OUTPUT_ROOT_OVERLAP",
        )
        out_values.append(item)
        result[name] = item
    return result


def recheck(plan: Mapping[str, CheckedPath]) -> None:
    """Revalidate identities of pre-existing ancestors, without reading their contents."""
    for item in plan.values():
        for path, device, inode in item.ancestors:
            try:
                info = path.lstat()
            except OSError as exc:
                raise EngineeringError("NPI_BOUND_ROOT_CHANGED") from exc
            require(
                not _linked(info)
                and stat.S_ISDIR(info.st_mode)
                and (info.st_dev, info.st_ino) == (device, inode),
                "NPI_BOUND_ROOT_CHANGED",
            )
        fresh = checked_path(item.path, must_exist=item.existed)
        require(item.existed or not fresh.existed, "NPI_OUTPUT_ALREADY_EXISTS")
