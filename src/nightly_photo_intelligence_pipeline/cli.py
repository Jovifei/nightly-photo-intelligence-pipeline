"""NPI command-line interface (Typer).

N0 commands:
  npi preflight                 read-only environment checks; no remediation
  npi status                    redacted SQLite + authorization summary
  npi ingest --input <DIR> --dry-run   read-only fingerprint / duplicate preview
  npi ingest --input <DIR>             -> exit 8 (NPI_GATE_NOT_AUTHORIZED in N0)

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
from .ingest.runner import format_dry_run_text, run_dry_run_ingest
from .ingest.source_guard import validate_roots
from .persistence.sqlite import StateStore
from .preflight import FAIL, format_preflight_text, run_preflight
from .redaction import redact_text
from .reporting.status import build_status_summary, format_status_text

app = typer.Typer(
    name="npi",
    help="Nightly Photo Intelligence Pipeline - N0 safe scaffold CLI.",
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
    dry_run: bool = typer.Option(
        False, "--dry-run", help="read-only preview (required in N0; real ingest is N1)"
    ),
) -> None:
    """Ingest source files. Only --dry-run is authorized in N0."""
    auth = load_authorization()
    # Gate check FIRST, before any source access.
    auth.require_ingest_authorized(dry_run=dry_run)
    if not dry_run:  # pragma: no cover - require_ingest_authorized already raised
        raise typer.Exit(code=int(ExitCode.GATE_NOT_AUTHORIZED))

    config = load_config()
    runtime_root = _resolve_runtime_root()
    # Security boundary: refuse source/runtime overlap before touching source.
    validate_roots(
        input_dir,
        runtime_root,
        allow_source_symlink=config.paths.allow_source_symlink,
        allow_file_symlink=config.paths.allow_file_symlink,
    )
    result = run_dry_run_ingest(
        input_dir,
        runtime_root,
        config,
        source_root_for_redaction=input_dir,
    )
    typer.echo(format_dry_run_text(result))


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
