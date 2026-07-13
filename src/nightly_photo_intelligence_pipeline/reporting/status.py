"""Status summary builder for ``npi status``.

Never emits absolute paths. Source paths stored in the database (the
``asset_sources.local_path_protected`` column) are intentionally not surfaced
here; only sanitized names and counts are reported.
"""

from __future__ import annotations

from typing import Any

from ..domain.authorization import AuthorizationSnapshot
from ..persistence.sqlite import StateStore


def build_status_summary(
    store: StateStore | None,
    auth: AuthorizationSnapshot,
) -> dict[str, Any]:
    """Build a redacted status summary dict."""
    summary: dict[str, Any] = {
        "phase": {"id": auth.phase_id, "status": auth.phase_status},
        "data_gate": {"id": auth.data_gate_id, "status": auth.data_gate_status},
        "real_photo_access": auth.real_photo_access,
        "large_model_downloads": auth.large_model_downloads,
        "openclaw_activation": auth.openclaw_activation,
        "database": {
            "present": False,
            "schema_version": None,
            "asset_count": 0,
            "counts_by_state": {},
            "interrupted_runs": 0,
            "recent_stage_runs": [],
        },
    }
    if store is None:
        return summary
    try:
        schema = store.schema_version()
        count = store.asset_count()
        counts = store.count_assets_by_state()
        interrupted = store.identify_interrupted_runs()
        recent = store.recent_stage_runs(limit=5)
        summary["database"] = {
            "present": True,
            "schema_version": schema,
            "asset_count": count,
            "counts_by_state": counts,
            "interrupted_runs": len(interrupted),
            "recent_stage_runs": [
                {
                    "stage_run_id": r.stage_run_id,
                    "asset_id": r.asset_id,
                    "stage_name": r.stage_name,
                    "status": r.status,
                    "attempt": r.attempt,
                    "started_at": r.started_at,
                }
                for r in recent
            ],
        }
    except Exception as exc:  # noqa: BLE001 - status must not crash the CLI
        summary["database"] = {"present": True, "error": f"unreadable: {type(exc).__name__}"}
    return summary


def format_status_text(summary: dict[str, Any]) -> str:
    """Render the status summary as human-readable text without absolute paths."""
    lines: list[str] = []
    lines.append("NPI status")
    lines.append("==========")
    lines.append(
        f"Authorization: phase={summary['phase']['id']} ({summary['phase']['status']}), "
        f"data_gate={summary['data_gate']['id']} ({summary['data_gate']['status']})"
    )
    lines.append(
        f"  real_photo_access={summary['real_photo_access']}, "
        f"model_downloads={summary['large_model_downloads']}, "
        f"openclaw={summary['openclaw_activation']}"
    )
    db = summary["database"]
    if not db.get("present"):
        lines.append("Database: not present (empty state is normal for a fresh N0 install)")
    elif "error" in db:
        lines.append(f"Database: present but unreadable: {db['error']}")
    else:
        lines.append(
            f"Database: present, schema_version={db['schema_version']}, "
            f"assets={db['asset_count']}, interrupted_runs={db['interrupted_runs']}"
        )
        counts = db.get("counts_by_state", {})
        if counts:
            lines.append("  assets by state:")
            for state in sorted(counts):
                lines.append(f"    {state}: {counts[state]}")
        recent = db.get("recent_stage_runs", [])
        if recent:
            lines.append("  recent stage runs:")
            for r in recent:
                lines.append(
                    f"    {r['stage_name']} status={r['status']} attempt={r['attempt']} "
                    f"started={r['started_at']}"
                )
    return "\n".join(lines)
