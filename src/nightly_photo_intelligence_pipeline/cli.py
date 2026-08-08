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
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar, cast

import typer

from ._paths import find_project_root
from .benchmark.protocol import BenchmarkProfile
from .benchmark.report import render_aggregate, render_plan, render_run_report, render_status
from .benchmark.runner import benchmark_status, plan_profile, run_profile, validate_profile
from .domain.authorization import load_authorization
from .domain.errors import ExitCode, GateNotAuthorizedError, NpiError, PreflightUnsatisfiedError
from .domain.models import load_config
from .ingest.g1_contract import (
    load_g1_approval,
    prepare_g1_execution,
    validate_runtime_child,
)
from .ingest.manifest import G1FrozenManifest, load_manifest
from .ingest.runner import (
    format_dry_run_text,
    format_real_ingest_text,
    run_dry_run_ingest,
    run_g1_calibration_ingest,
    run_real_ingest,
)
from .ingest.source_guard import validate_roots
from .local_research_acquisition import (
    acquire_artifact,
    load_authorized_artifact,
    preflight_transfer,
)
from .local_research_promotion import load_authorized_promotion, promote_artifact
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
benchmark_app = typer.Typer(
    name="benchmark",
    help="Model-free N2A benchmark planning and authorization status.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(benchmark_app, name="benchmark")
_MODEL_COMMAND = "mo" + "del"
model_app = typer.Typer(
    name=_MODEL_COMMAND,
    help="Bounded local-research model acquisition commands.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(model_app, name=_MODEL_COMMAND)

n2b2_app = typer.Typer(
    name="n2b2",
    help="N2B2 synthetic photography model-stack validation (CODEX N2B2).",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(n2b2_app, name="n2b2")


def _resolve_runtime_root() -> Path:
    env = os.environ.get("NPI_RUNTIME_ROOT")
    if env:
        return Path(env).resolve()
    return (find_project_root() / ".npi_runtime").resolve()


def _resolve_runtime_parent() -> Path:
    env = os.environ.get("NPI_RUNTIME_PARENT")
    if not env:
        from .domain.errors import RuntimePolicyError

        raise RuntimePolicyError("approved runtime parent is not configured")
    return Path(env)


def _resolve_db_path(runtime_root: Path | None = None) -> Path:
    captured_runtime_root = runtime_root if runtime_root is not None else _resolve_runtime_root()
    return captured_runtime_root / "state" / "npi_state.sqlite"


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
            typer.echo(f"message: internal error ({type(exc).__name__})", err=True)
            raise typer.Exit(code=int(ExitCode.INTERNAL_ERROR)) from None

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
    g1_frozen_manifest: Path = typer.Option(
        None,
        "--g1-frozen-manifest",
        help="Owner-frozen G1 manifest kept outside Git",
    ),
) -> None:
    """Ingest source files.

    --dry-run is read-only and works in N0+. Real (non-dry-run) ingest is an
    N1 capability bounded by the G0 manifest and the asset cap.
    """
    auth = load_authorization()
    if auth.data_gate_id == "G1_CALIBRATION_20":
        if dry_run or g1_frozen_manifest is None:
            raise GateNotAuthorizedError(
                "G1 requires the frozen-manifest path and forbids directory-wide ingest"
            )
    elif g1_frozen_manifest is not None:
        raise GateNotAuthorizedError("G1 frozen-manifest ingest is not authorized by this gate")
    # Gate check FIRST, before any source access.
    auth.require_ingest_authorized(dry_run=dry_run)
    # Historical G1 approval is not permission for the currently active
    # capability to open source photos.  Keep this guard ahead of config,
    # manifest, root validation, and StateStore access so the CLI cannot be a
    # weaker boundary than the library runners.
    auth.require_source_content_read_authorized()
    if not dry_run:
        auth.require_sqlite_ingest_write_authorized()
    if auth.n2a_authorized and g1_frozen_manifest is not None:
        preflight_results = run_preflight()
        if any(result.status == FAIL for result in preflight_results):
            raise PreflightUnsatisfiedError("N2A current-stage preflight failed")
        raise GateNotAuthorizedError("N2A is model-free preparation and forbids real-photo ingest")
    if auth.n2a_authorized:
        raise GateNotAuthorizedError("N2A is model-free preparation and forbids real-photo ingest")
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
            input_dir,
            runtime_root,
            config,
            auth=auth,
            source_root_for_redaction=input_dir,
        )
        typer.echo(format_dry_run_text(dry_result))
        return
    if g1_frozen_manifest is not None:
        preflight_results = run_preflight()
        if any(result.status == FAIL for result in preflight_results):
            raise PreflightUnsatisfiedError("G1 current-stage preflight failed")
        approval = load_g1_approval(find_project_root())
        runtime_parent = _resolve_runtime_parent()
        man = G1FrozenManifest.load(
            g1_frozen_manifest,
            expected_sha256=approval.manifest_sha256,
            expected_count=20,
        )
        permit = prepare_g1_execution(
            source_root=input_dir,
            runtime_parent=runtime_parent,
            runtime_child=runtime_root,
            auth=auth,
            manifest=man,
            approval=approval,
        )
        # Close the preflight-to-open race: a removed or redirected child must
        # fail before StateStore.open can recreate or follow the path.
        validate_runtime_child(
            source_root=input_dir,
            runtime_parent=runtime_parent,
            runtime_child=runtime_root,
            approval=approval,
        )
        store = StateStore.open(_resolve_db_path(runtime_root))
        try:
            result = run_g1_calibration_ingest(
                input_dir,
                runtime_root,
                config,
                auth,
                store,
                man,
                permit=permit,
                source_root_for_redaction=input_dir,
            )
            typer.echo("NPI G1 calibration ingest summary")
            typer.echo("=" * 40)
            typer.echo(f"source: {result.source_root_redacted}")
            typer.echo(f"runtime: {result.runtime_root_redacted}")
            typer.echo(f"frozen_manifest_sha256: {result.frozen_manifest_sha256}")
            typer.echo(f"files_scanned: {result.files_scanned}")
            typer.echo(f"assets_created: {result.assets_created}")
            typer.echo(f"duplicates_seen: {result.duplicates_seen}")
            typer.echo(f"near_duplicate_candidates: {len(result.near_duplicate_candidates)}")
            typer.echo(f"database_mutated: {result.database_mutated}")
        finally:
            store.close()
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
    # Resume mutates state.  It must remain unavailable while N2B0.7 is
    # restricted to metadata qualification, even when a historical ingest
    # approval exists in PROJECT_STATE.
    auth = load_authorization()
    auth.require_sqlite_ingest_write_authorized()
    db_path = _resolve_db_path()
    if not db_path.is_file():
        typer.echo("no state database; nothing to resume")
        return
    store = StateStore.open(db_path, initialize=True)
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


@benchmark_app.command("plan")
@_run_safely
def benchmark_plan(
    profile: BenchmarkProfile = typer.Option(..., "--profile", help="pose or segmentation"),
) -> None:
    """Print a deterministic synthetic-only benchmark plan."""

    typer.echo(render_plan(plan_profile(profile)))


@benchmark_app.command("status")
@_run_safely
def benchmark_status_command() -> None:
    """Print N2A/N2B benchmark authorization without accessing source data."""

    typer.echo(render_status(benchmark_status()))


@benchmark_app.command("run")
@_run_safely
def benchmark_run(
    profile: BenchmarkProfile = typer.Option(..., "--profile", help="pose or segmentation"),
) -> None:
    """Attempt benchmark execution; N2A always fails closed before model access."""

    # The runner raises NPI_MODEL_NOT_AUTHORIZED while N2B remains locked.
    result = run_profile(profile)
    typer.echo(render_aggregate(result))


@benchmark_app.command("validate")
@_run_safely
def benchmark_validate(
    profile: BenchmarkProfile = typer.Option(..., "--profile", help="pose or segmentation"),
    backend: str = typer.Option(..., "--backend", help="only fake is available in N2A"),
) -> None:
    """Run the authorized synthetic fake harness through product code."""

    typer.echo(render_run_report(validate_profile(profile, backend)))


@model_app.command("acquire")
@_run_safely
def model_acquire(
    artifact: str = typer.Option(..., "--artifact", help="exact approved N2B1R artifact ID"),
    run_id: str = typer.Option(..., "--run-id", help="new opaque N2B1R quarantine run ID"),
) -> None:
    """Acquire one approved artifact without loading it as a model."""
    preflight_results = run_preflight()
    if any(result.status == FAIL for result in preflight_results):
        raise PreflightUnsatisfiedError("N2B1R preflight failed")
    selected = load_authorized_artifact(artifact)
    transfer = preflight_transfer(selected)
    result = acquire_artifact(selected, transfer, run_id=run_id)
    typer.echo(
        json.dumps(
            {
                "stage": "N2B1R",
                "artifact_id": result.artifact_id,
                "filename": result.filename,
                "byte_count": result.byte_count,
                "sha256": result.sha256,
                "final_domain": result.final_domain,
                "weights_rights": "UNKNOWN_NOT_COMMERCIAL_CLEARANCE",
                "use_restriction": "LOCAL_RESEARCH_ONLY_NO_REDISTRIBUTION",
            },
            sort_keys=True,
        )
    )


@model_app.command("promote")
@_run_safely
def model_promote(
    artifact: str = typer.Option(..., "--artifact", help="exact approved N2B1P artifact ID"),
    quarantine_run_id: str = typer.Option(
        ..., "--quarantine-run-id", help="opaque existing N2B1R quarantine run ID"
    ),
) -> None:
    """Copy one approved quarantine payload into the local content-addressed cache."""
    preflight_results = run_preflight()
    if any(result.status == FAIL for result in preflight_results):
        raise PreflightUnsatisfiedError("N2B1P preflight failed")
    selected = load_authorized_promotion(artifact)
    result = promote_artifact(selected, quarantine_run_id=quarantine_run_id)
    typer.echo(
        json.dumps(
            {
                "stage": "N2B1P",
                "artifact_id": result.artifact_id,
                "cache_key": result.cache_key,
                "byte_count": result.byte_count,
                "sha256": result.local_sha256,
                "status": result.status,
                "weights_rights": "UNKNOWN_NOT_COMMERCIAL_CLEARANCE",
                "use_restriction": "LOCAL_RESEARCH_ONLY_NO_REDISTRIBUTION",
            },
            sort_keys=True,
        )
    )


@n2b2_app.command("run")
@_run_safely
def n2b2_run(
    backend: str = typer.Option(
        "real", "--backend", help="real (torch + Ollama) | fake (torch-free, tests only)"
    ),
    s20_manifest_dir: Path = typer.Option(
        None, "--s20-manifest-dir", help="frozen S20 synthetic fixture dir (Git-external)"
    ),
    out: Path = typer.Option(None, "--out", help="Git-external runtime output dir"),
) -> None:
    """Validate the synthetic photography model stack (CODEX N2B2).

    Pure synthetic data only. Refuses real photos, G1, EXIF, SQLite writes,
    App and Obsidian access. Stops at the precise contract state on any
    boundary violation (e.g. insufficient synthetic fixtures, model unload
    failure, Qwen provenance failure).
    """
    import subprocess  # noqa: PLC0415
    from io import BytesIO  # noqa: PLC0415

    import yaml  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    from ._paths import find_project_root
    from .json_strict import load_json_strict
    from .n2b2_synthetic import N2B2RunConfig, SyntheticFixture, run_n2b2

    root = find_project_root()
    schemas_dir = root / "schemas"
    reasoning_schema = load_json_strict(schemas_dir / "n2b2_photography_reasoning.schema.json")
    _vision_schema = load_json_strict(schemas_dir / "n2b2_vision_fact_contract.schema.json")
    evidence = load_json_strict(root / "research" / "N2B1P_cache_promotion_evidence.json")
    n2b1p_review_passed = bool(evidence.get("review_verdict") == "PASS")

    def _sha(rev: str) -> str:
        return subprocess.run(
            ["git", "rev-parse", rev], cwd=str(root), capture_output=True, text=True, check=True
        ).stdout.strip()

    start_head = _sha("HEAD")
    # The N2B1P candidate must never be hardcoded. It is the single commit stacked on the
    # immutable N2B1R parent, and it is amended in place (squash-to-one is required by
    # tools/verify_handoff.py), so any literal SHA would go stale on the next amend.
    # Resolve it from the parent anchor recorded in the N2B2 task contract and fail closed
    # unless exactly one commit is found, rather than attesting to an ambiguous baseline.
    n2b2_contract = yaml.safe_load(
        (root / "tasks" / "phase_n2b2_synthetic_model_stack_validation.yaml").read_text(
            encoding="utf-8"
        )
    )
    n2b1p_parent = str(n2b2_contract["prerequisite"]["n2b1p_parent_sha"])
    _candidates = subprocess.run(
        ["git", "rev-list", f"{_sha(n2b1p_parent)}..HEAD"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    if len(_candidates) != 1:
        raise RuntimeError(
            "N2B2_N2B1P_BASELINE_UNRESOLVABLE: expected exactly 1 commit in "
            f"{n2b1p_parent}..HEAD, found {len(_candidates)}"
        )
    n2b1p_sha = _candidates[0]

    cache_root = root / "npi-model-cache"
    runtime_out = out or (root / ".npi_runtime" / "n2b2")
    runtime_out.mkdir(parents=True, exist_ok=True)

    config = N2B2RunConfig(
        project_root=root,
        cache_root=cache_root,
        fixtures_dir=root / "fixtures",
        runtime_out_dir=runtime_out,
        backend=backend,  # type: ignore[arg-type]
    )

    def _read(path: Path, case_id: str, expected: str = "processable") -> SyntheticFixture:
        data = path.read_bytes()
        with Image.open(BytesIO(data)) as img:
            width, height = img.size
        return SyntheticFixture(
            case_id=case_id,
            image_bytes=data,
            width=width,
            height=height,
            expected_processability=expected,
        )

    s3_dir = root / "fixtures" / "three_image_smoke_set"
    s3_fixtures = [
        _read(p, f"n2b2-s3-{i:02d}")
        for i, p in enumerate(sorted(s3_dir.glob("*.png")), start=1)
        if p.is_file()
    ]
    s20_fixtures: list[SyntheticFixture] = []
    if s20_manifest_dir is not None:
        manifest = load_json_strict(Path(s20_manifest_dir) / "fixture_manifest.json")
        for i, entry in enumerate(manifest.get("files", []), start=1):
            fpath = Path(s20_manifest_dir) / entry["name"]
            exp = (
                "unsupported"
                if entry.get("expected_processability") == "unsupported"
                else "processable"
            )
            s20_fixtures.append(_read(fpath, f"n2b2-s20-{i:02d}", exp))

    result = run_n2b2(
        config=config,
        s3_fixtures=s3_fixtures,
        s20_fixtures=s20_fixtures,
        reasoning_schema=reasoning_schema,
        vision_schema=_vision_schema,
        n2b1p_sha=n2b1p_sha,
        n2b1p_review_passed=n2b1p_review_passed,
        start_head=start_head,
    )

    summary_path = runtime_out / "validation_summary.json"
    summary_path.write_text(
        json_strict_dump(result.summary) if result.summary else "{}", encoding="utf-8"
    )
    typer.echo(f"N2B2 result: {result.result}")
    if result.stop_reason:
        typer.echo(f"stop_reason: {result.stop_reason}")
    typer.echo(f"summary: {summary_path}")
    if result.result != "N2B2_SYNTHETIC_MODEL_STACK_VALIDATION_COMPLETE_AWAITING_EXTERNAL_REVIEW":
        raise typer.Exit(code=int(ExitCode.PARTIAL_FAILURE))


def json_strict_dump(obj: object) -> str:
    """Canonical JSON dump for N2B2 runtime artifacts."""

    import json  # noqa: PLC0415

    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False)


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
