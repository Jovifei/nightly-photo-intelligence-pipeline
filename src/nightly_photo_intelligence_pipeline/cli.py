"""NPI command-line interface (Typer).

N1 commands:
  npi preflight                 read-only environment checks; no remediation
  npi status                    redacted SQLite + authorization summary
  npi ingest --input <DIR> --dry-run   read-only fingerprint / duplicate preview
  npi ingest --input <DIR>             real ingest (N1/G0; manifest-gated, mutating)
  npi resume                    reclaim interrupted stage runs
  npi report --latest           redacted latest-run summary

All errors emit a stable ``error_code`` and exit code (see domain/errors.py).
No absolute source paths, tokens, or hostnames are printed.
"""

from __future__ import annotations

import functools
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar, cast

import typer

from ._paths import find_project_root
from .domain.authorization import load_authorization
from .domain.errors import ExitCode, NpiError
from .domain.models import load_config
from .ingest.manifest import load_manifest
from .ingest.runner import (
    format_dry_run_text,
    format_real_ingest_text,
    run_dry_run_ingest,
    run_real_ingest,
)
from .ingest.source_guard import validate_roots
from .persistence.sqlite import StateStore
from .preflight import FAIL, format_preflight_text, run_preflight
from .redaction import redact_text
from .reporting.status import build_status_summary, format_status_text

app = typer.Typer(
    name="npi",
    help="Nightly Photo Intelligence Pipeline CLI (N1).",
    no_args_is_help=True,
    add_completion=False,
)


def _resolve_runtime_root() -> Path:
    env = os.environ.get("NPI_RUNTIME_ROOT")
    if env:
        return Path(env).resolve()
    return (find_project_root() / ".npi_runtime").resolve()


def _resolve_db_path() -> Path:
    return _resolve_runtime_root() / "state" / "npi_state.sqlite"


def _default_manifest() -> Path:
    return find_project_root() / "fixtures" / "fixture_manifest.json"


def _emit_error(exc: NpiError) -> None:
    typer.echo(f"error_code: {exc.error_code}", err=True)
    typer.echo(f"exit_code: {int(exc.exit_code)}", err=True)
    typer.echo(f"message: {redact_text(str(exc))}", err=True)


F = TypeVar("F", bound=Callable[..., Any])


def _run_safely(func: F) -> F:
    """Decorator: map NpiError to a redacted stderr message + stable exit code."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except NpiError as exc:
            _emit_error(exc)
            raise typer.Exit(code=int(exc.exit_code)) from None
        except typer.Exit:
            raise
        except Exception as exc:  # noqa: BLE001 - last-resort guard
            typer.echo("error_code: NPI_INTERNAL_ERROR", err=True)
            typer.echo(f"exit_code: {int(ExitCode.INTERNAL_ERROR)}", err=True)
            typer.echo(f"message: {redact_text(type(exc).__name__ + ': ' + str(exc))}", err=True)
            raise typer.Exit(code=int(ExitCode.INTERNAL_ERROR)) from exc

    return cast(F, wrapper)


@app.command()
@_run_safely
def preflight() -> None:
    """Read-only environment checks. Never installs, updates, or pulls."""
    results = run_preflight()
    typer.echo(format_preflight_text(results))
    if any(r.status == FAIL for r in results):
        raise typer.Exit(code=int(ExitCode.PREFLIGHT_UNSATISFIED))


@app.command()
@_run_safely
def status() -> None:
    """Print a redacted SQLite + authorization summary."""
    auth = load_authorization()
    db_path = _resolve_db_path()
    store: StateStore | None = None
    if db_path.is_file():
        store = StateStore.open(db_path, initialize=False)
    try:
        summary = build_status_summary(store, auth)
        typer.echo(format_status_text(summary))
    finally:
        if store is not None:
            store.close()


@app.command()
@_run_safely
def ingest(
    input_dir: Path = typer.Option(..., "--input", help="read-only source directory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="read-only preview (no DB mutation)"),
    manifest: Path = typer.Option(
        None, "--manifest", help="G0 data manifest (default: fixtures/fixture_manifest.json)"
    ),
) -> None:
    """Ingest source files.

    --dry-run is read-only and works in N0+. Real (non-dry-run) ingest is an
    N1 capability bounded by the G0 manifest and the asset cap.
    """
    auth = load_authorization()
    # Gate check FIRST, before any source access.
    auth.require_ingest_authorized(dry_run=dry_run)
    config = load_config()
    runtime_root = _resolve_runtime_root()
    # Security boundary: refuse source/runtime overlap before touching source.
    validate_roots(
        input_dir,
        runtime_root,
        allow_source_symlink=config.paths.allow_source_symlink,
        allow_file_symlink=config.paths.allow_file_symlink,
    )
    if dry_run:
        dry_result = run_dry_run_ingest(
            input_dir, runtime_root, config, source_root_for_redaction=input_dir
        )
        typer.echo(format_dry_run_text(dry_result))
        return
    # Real ingest (N1/G0): manifest-gated, idempotent, mutating.
    manifest_path = manifest or _default_manifest()
    man = load_manifest(manifest_path)
    store = StateStore.open(_resolve_db_path())
    try:
        real_result = run_real_ingest(
            input_dir,
            runtime_root,
            config,
            auth,
            store,
            man,
            source_root_for_redaction=input_dir,
        )
        typer.echo(format_real_ingest_text(real_result))
    finally:
        store.close()


@app.command()
@_run_safely
def resume() -> None:
    """Reclaim interrupted stage runs (expired leases) as INTERRUPTED.

    Does not invent outputs or advance asset state; it only flags runs so a
    later stage can reclaim them. Reports the count reclaimed.
    """
    db_path = _resolve_db_path()
    if not db_path.is_file():
        typer.echo("no state database; nothing to resume")
        return
    store = StateStore.open(db_path, initialize=False)
    try:
        n = store.recover_interrupted_runs()
        typer.echo(f"reclaimed {n} interrupted stage run(s)")
    finally:
        store.close()


@app.command()
@_run_safely
def report(
    latest: bool = typer.Option(False, "--latest", help="summarize the latest run"),
) -> None:
    """Print a redacted run report."""
    if not latest:
        typer.echo("use --latest", err=True)
        raise typer.Exit(code=int(ExitCode.CLI_USAGE_ERROR))
    auth = load_authorization()
    db_path = _resolve_db_path()
    store: StateStore | None = None
    if db_path.is_file():
        store = StateStore.open(db_path, initialize=False)
    try:
        summary = build_status_summary(store, auth)
        typer.echo("NPI latest run report")
        typer.echo("=" * 40)
        typer.echo(format_status_text(summary))
        if store is not None:
            typer.echo("")
            typer.echo(f"schema_version: {summary['database'].get('schema_version')}")
            typer.echo(f"interrupted_runs: {summary['database'].get('interrupted_runs')}")
            # Retry/error audit (redacted).
            rows = store.connection.execute(
                "SELECT asset_id, retry_count, last_error_code FROM assets "
                "WHERE retry_count > 0 OR last_error_code IS NOT NULL "
                "ORDER BY updated_at DESC LIMIT 20"
            ).fetchall()
            if rows:
                typer.echo("retry/error audit (redacted):")
                for r in rows:
                    typer.echo(
                        f"  asset={str(r['asset_id'])[:16]}  retries={int(r['retry_count'])}  "
                        f"last_error={r['last_error_code']}"
                    )
            else:
                typer.echo("retry/error audit: none")
    finally:
        if store is not None:
            store.close()


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
