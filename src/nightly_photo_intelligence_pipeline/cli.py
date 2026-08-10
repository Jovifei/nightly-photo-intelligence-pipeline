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
    s20_manifest_dir: Path | None = typer.Option(
        None, "--s20-manifest-dir", help="frozen S20 synthetic fixture dir (Git-external)"
    ),
    s3_manifest_dir: Path = typer.Option(
        None, "--s3-manifest-dir", help="frozen S3 synthetic fixture dir (Git-external)"
    ),
    out: Path = typer.Option(None, "--out", help="Git-external runtime output dir"),
    s3_only: bool = typer.Option(False, "--s3-only", help="run the authorized S3 smoke only"),
    device: str | None = typer.Option(
        None, "--device", help="explicit real backend device: cuda or cpu"
    ),
) -> None:
    """Run the bounded, synthetic-only N2B2 S3 smoke."""
    import subprocess  # noqa: PLC0415

    import yaml  # noqa: PLC0415

    from ._paths import find_project_root
    from .json_strict import load_json_strict
    from .n2b1p_integrity import load_n2b1p_runtime_configuration
    from .n2b2_synthetic import N2B2RunConfig, load_s3_manifest, run_n2b2
    from .n2b2_synthetic.n2b1p_gate import validate_n2b1p_review

    root = find_project_root()
    if not s3_only:
        typer.echo("N2B2_S3_ONLY_REQUIRED")
        raise typer.Exit(code=int(ExitCode.CLI_USAGE_ERROR))
    if backend == "real" and device not in {"cuda", "cpu"}:
        typer.echo("N2B2_DEVICE_REQUIRED: real backend requires --device cuda|cpu")
        raise typer.Exit(code=int(ExitCode.CLI_USAGE_ERROR))
    if s20_manifest_dir is not None:
        typer.echo("N2B2_S20_NOT_AUTHORIZED")
        raise typer.Exit(code=int(ExitCode.PARTIAL_FAILURE))
    if s3_manifest_dir is None or out is None:
        typer.echo("N2B2_S3_MANIFEST_AND_EXTERNAL_OUT_REQUIRED")
        raise typer.Exit(code=int(ExitCode.CLI_USAGE_ERROR))

    def _external_path(value: Path, label: str) -> Path:
        resolved = value.resolve()
        try:
            inside = os.path.commonpath((str(root.resolve()), str(resolved))) == str(root.resolve())
        except ValueError:
            # On Windows, a runtime on another drive cannot be inside the Git
            # project; treat the drive boundary as an external-path proof.
            inside = False
        if inside:
            raise RuntimeError(f"{label} must be Git-external")
        return resolved

    schemas_dir = root / "schemas"
    reasoning_schema = load_json_strict(schemas_dir / "n2b2_photography_reasoning.schema.json")
    vision_schema = load_json_strict(schemas_dir / "n2b2_vision_fact_contract.schema.json")
    evidence = load_json_strict(root / "research" / "N2B1P_cache_promotion_evidence.json")
    n2b1p_review_passed, review_detail = validate_n2b1p_review(evidence)
    typer.echo(f"N2B1P review gate: {'PASS' if n2b1p_review_passed else 'FAIL'} ({review_detail})")
    completion_record = root / "approvals" / "phase_completion_N2B1P.yaml"
    if not completion_record.is_file():
        typer.echo("OWNER_PHASE_COMPLETION_RECORD_NOT_PRESENT")
    state = load_json_strict(root / "PROJECT_STATE.json")
    phase_status = state.get("phase_status", {})
    if phase_status.get("N2B2") != "LOCKED":
        typer.echo("N2B2_PROJECT_STATE_BOUNDARY_VIOLATION")
        raise typer.Exit(code=int(ExitCode.PARTIAL_FAILURE))

    def _sha(rev: str) -> str:
        return subprocess.run(
            ["git", "rev-parse", rev], cwd=str(root), capture_output=True, text=True, check=True
        ).stdout.strip()

    start_head = _sha("HEAD")
    # Resolve the reviewed N2B1P commit as the direct child of the immutable N2B1R
    # parent.  A later N2B2 review-candidate commit is intentionally not treated as
    # the N2B1P baseline.
    n2b2_contract = yaml.safe_load(
        (root / "tasks" / "phase_n2b2_synthetic_model_stack_validation.yaml").read_text(
            encoding="utf-8"
        )
    )
    n2b1p_parent = str(n2b2_contract["prerequisite"]["n2b1p_parent_sha"])
    _candidates = subprocess.run(
        ["git", "rev-list", "--parents", f"{_sha(n2b1p_parent)}..HEAD"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    direct_children = [
        line.split()[0]
        for line in _candidates
        if len(line.split()) == 2 and line.split()[1] == _sha(n2b1p_parent)
    ]
    if len(direct_children) != 1:
        raise RuntimeError(
            "N2B2_N2B1P_BASELINE_UNRESOLVABLE: expected one direct N2B1P child, "
            f"found {len(direct_children)}"
        )
    n2b1p_sha = direct_children[0]

    manifest_dir = _external_path(s3_manifest_dir, "S3 manifest")
    runtime_out = _external_path(out, "runtime output")
    s3_fixtures = load_s3_manifest(manifest_dir, project_root=root)
    # Use only the strictly validated, Git-external cache root from the
    # approved N2B1P runtime configuration; never fall back to a repo cache.
    cache_root = load_n2b1p_runtime_configuration(root).cache_root
    runtime_out.mkdir(parents=True, exist_ok=True)

    config = N2B2RunConfig(
        project_root=root,
        cache_root=cache_root,
        fixtures_dir=manifest_dir,
        runtime_out_dir=runtime_out,
        backend=cast(Any, backend),
        device=cast(Any, device or "cpu"),
        s3_only=True,
    )

    result = run_n2b2(
        config=config,
        s3_fixtures=s3_fixtures,
        s20_fixtures=[],
        reasoning_schema=reasoning_schema,
        vision_schema=vision_schema,
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
    if result.result != "N2B2_SYNTHETIC_SMOKE_VALIDATION_COMPLETE_AWAITING_OWNER_REVIEW":
        raise typer.Exit(code=int(ExitCode.PARTIAL_FAILURE))


@n2b2_app.command("gpu-validate")
@_run_safely
def n2b2_gpu_validate(
    s3_manifest_dir: Path = typer.Option(..., "--s3-manifest-dir"),
    out: Path = typer.Option(..., "--out"),
) -> None:
    """Run CPU comparator, explicit CUDA probe, then the CUDA S3 smoke."""

    from .json_strict import load_json_strict
    from .n2b1p_integrity import load_n2b1p_runtime_configuration
    from .n2b2_synthetic import N2B2RunConfig, load_s3_manifest, run_gpu_probe
    from .n2b2_synthetic.metrics import MetricsCollector
    from .n2b2_synthetic.n2b1p_gate import validate_n2b1p_review

    root = find_project_root()
    resolved_manifest = s3_manifest_dir.resolve()
    resolved_out = out.resolve()
    try:
        inside = os.path.commonpath((str(root.resolve()), str(resolved_manifest))) == str(
            root.resolve()
        )
    except ValueError:
        inside = False
    if inside:
        raise RuntimeError("S3 manifest must be Git-external")
    try:
        inside = os.path.commonpath((str(root.resolve()), str(resolved_out))) == str(root.resolve())
    except ValueError:
        inside = False
    if inside:
        raise RuntimeError("GPU runtime output must be Git-external")

    state = load_json_strict(root / "PROJECT_STATE.json")
    if state.get("phase_status", {}).get("N2B2") != "LOCKED":
        typer.echo("N2B2_PROJECT_STATE_BOUNDARY_VIOLATION")
        raise typer.Exit(code=int(ExitCode.PARTIAL_FAILURE))
    evidence = load_json_strict(root / "research" / "N2B1P_cache_promotion_evidence.json")
    review_passed, review_detail = validate_n2b1p_review(evidence)
    typer.echo(f"N2B1P review gate: {'PASS' if review_passed else 'FAIL'} ({review_detail})")
    if not review_passed:
        typer.echo("N2B2_EXECUTION_BLOCKED_N2B1P_NOT_APPROVED")
        raise typer.Exit(code=int(ExitCode.PARTIAL_FAILURE))

    vision_schema = load_json_strict(root / "schemas" / "n2b2_vision_fact_contract.schema.json")
    fixtures = load_s3_manifest(resolved_manifest, project_root=root)
    cache_root = load_n2b1p_runtime_configuration(root).cache_root
    probe_config = N2B2RunConfig(
        project_root=root,
        cache_root=cache_root,
        fixtures_dir=resolved_manifest,
        runtime_out_dir=resolved_out,
        backend="real",
        device="cuda",
        s3_only=True,
    )
    resolved_out.mkdir(parents=True, exist_ok=True)
    baseline_mib = MetricsCollector().sample_baseline()
    if baseline_mib >= probe_config.gpu_limit_mib - 1024:
        blocked = {
            "schema_version": "n2b2-gpu-runtime-metrics-v1",
            "status": "N2B2_GPU_RUNTIME_UNAVAILABLE",
            "stop_reason": "INSUFFICIENT_EXCLUSIVE_HEADROOM",
            "fixture_count": len(fixtures),
            "devices": {},
            "formal_cuda_gate": False,
            "hard_counts": {
                "real_photo_read_count": 0,
                "real_exif_read_count": 0,
                "g1_source_access": 0,
                "sqlite_write_count": 0,
                "app_write_count": 0,
                "obsidian_write_count": 0,
            },
            "runtime": {
                "gpu_baseline_mib": baseline_mib,
                "gpu_limit_mib": probe_config.gpu_limit_mib,
                "required_reserve_mib": 1024,
                "comfyui_listener": "NOT_FOUND; no process stopped",
            },
        }
        (resolved_out / "gpu_runtime_metrics.json").write_text(
            json_strict_dump(blocked), encoding="utf-8"
        )
        typer.echo("N2B2_GPU_RUNTIME_UNAVAILABLE: INSUFFICIENT_EXCLUSIVE_HEADROOM")
        typer.echo(f"GPU probe metrics: {resolved_out / 'gpu_runtime_metrics.json'}")
        raise typer.Exit(code=int(ExitCode.PARTIAL_FAILURE))
    probe = run_gpu_probe(
        cache_root=probe_config.cache_root,
        cache_subdirs=probe_config.cache_subdirs,
        fixtures=fixtures,
        vision_schema=vision_schema,
    )
    (resolved_out / "gpu_runtime_metrics.json").write_text(
        json_strict_dump(probe), encoding="utf-8"
    )
    typer.echo(f"GPU probe metrics: {resolved_out / 'gpu_runtime_metrics.json'}")
    if not probe.get("formal_cuda_gate", False):
        typer.echo("N2B2_GPU_RUNTIME_UNAVAILABLE")
        raise typer.Exit(code=int(ExitCode.PARTIAL_FAILURE))

    n2b2_run(
        backend="real",
        s20_manifest_dir=None,
        s3_manifest_dir=resolved_manifest,
        out=resolved_out,
        s3_only=True,
        device="cuda",
    )


@n2b2_app.command("case17-remediate")
@_run_safely
def n2b2_case17_remediate(
    baseline_manifest_dir: Path = typer.Option(..., "--baseline-manifest-dir"),
    candidate_dir: Path = typer.Option(..., "--candidate-dir"),
    out: Path = typer.Option(..., "--out"),
) -> None:
    """Select one bounded Case 17 candidate and build an external v2 set."""

    from .json_strict import load_json_strict
    from .n2b1p_integrity import load_n2b1p_runtime_configuration
    from .n2b2_synthetic import N2B2RunConfig
    from .n2b2_synthetic.case17_remediation import build_case17_v2_manifest

    root = find_project_root()

    def external_path(value: Path, label: str) -> Path:
        resolved = value.resolve()
        try:
            inside = os.path.commonpath((str(root.resolve()), str(resolved))) == str(root.resolve())
        except ValueError:
            inside = False
        if inside:
            raise RuntimeError(f"{label} must be Git-external")
        return resolved

    state = load_json_strict(root / "PROJECT_STATE.json")
    if state.get("phase_status", {}).get("N2B2") != "LOCKED":
        typer.echo("N2B2_PROJECT_STATE_BOUNDARY_VIOLATION")
        raise typer.Exit(code=int(ExitCode.PARTIAL_FAILURE))
    import yaml

    remediation_receipt = root / "approvals" / "owner_n2b2_s20_case17_remediation_receipt.yaml"
    receipt = yaml.safe_load(remediation_receipt.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict) or receipt.get("status") != "AUTHORIZED_FOR_BOUNDED_RETRY":
        typer.echo("N2B2_S20_NOT_AUTHORIZED")
        raise typer.Exit(code=int(ExitCode.PARTIAL_FAILURE))
    baseline = external_path(baseline_manifest_dir, "baseline manifest")
    candidates = external_path(candidate_dir, "candidate directory")
    output = external_path(out, "v2 manifest output")
    runtime = load_n2b1p_runtime_configuration(root)
    config = N2B2RunConfig(
        project_root=root,
        cache_root=runtime.cache_root,
        fixtures_dir=baseline,
        runtime_out_dir=output,
        backend="real",
        device="cuda",
        s3_only=False,
    )
    try:
        summary = build_case17_v2_manifest(
            baseline_manifest_dir=baseline,
            candidate_dir=candidates,
            out_dir=output,
            cache_root=runtime.cache_root,
            cache_subdirs=config.cache_subdirs,
        )
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=int(ExitCode.PARTIAL_FAILURE)) from None
    typer.echo(f"Case 17 v2 manifest: {output / 'fixture_manifest.json'}")
    typer.echo(json_strict_dump(summary))


@n2b2_app.command("s20-validate")
@_run_safely
def n2b2_s20_validate(
    device: str = typer.Option("cuda", "--device"),
    review_record: Path = typer.Option(..., "--review-record"),
    s20_manifest_dir: Path = typer.Option(..., "--s20-manifest-dir"),
    baseline_manifest_dir: Path | None = typer.Option(None, "--baseline-manifest-dir"),
    out: Path = typer.Option(..., "--out"),
    resume: bool = typer.Option(False, "--resume"),
) -> None:
    """Run the separately authorized CUDA-only S20 synthetic validation."""

    from .json_strict import load_json_strict
    from .n2b1p_integrity import load_n2b1p_runtime_configuration
    from .n2b2_synthetic import N2B2RunConfig, load_s20_manifest
    from .n2b2_synthetic.s20_orchestrator import S20_COMPLETE, run_s20

    root = find_project_root()
    if device != "cuda":
        typer.echo("N2B2_S20_NOT_AUTHORIZED")
        raise typer.Exit(code=int(ExitCode.PARTIAL_FAILURE))

    def external_path(value: Path, label: str) -> Path:
        resolved = value.resolve()
        try:
            inside = os.path.commonpath((str(root.resolve()), str(resolved))) == str(root.resolve())
        except ValueError:
            inside = False
        if inside:
            raise RuntimeError(f"{label} must be Git-external")
        return resolved

    resolved_review = external_path(review_record, "review record")
    resolved_manifest = external_path(s20_manifest_dir, "S20 manifest")
    resolved_baseline = (
        external_path(baseline_manifest_dir, "baseline manifest")
        if baseline_manifest_dir is not None
        else None
    )
    resolved_out = external_path(out, "S20 runtime output")
    state = load_json_strict(root / "PROJECT_STATE.json")
    if state.get("phase_status", {}).get("N2B2") != "LOCKED":
        typer.echo("N2B2_PROJECT_STATE_BOUNDARY_VIOLATION")
        raise typer.Exit(code=int(ExitCode.PARTIAL_FAILURE))
    review_payload = json.loads(resolved_review.read_text(encoding="utf-8"))
    reviewed_commit = review_payload.get("reviewed_commit")
    if not isinstance(reviewed_commit, str):
        typer.echo("N2B2_S20_NOT_AUTHORIZED")
        raise typer.Exit(code=int(ExitCode.PARTIAL_FAILURE))
    owner_receipt = root / "approvals" / "owner_n2b2_s20_synthetic_validation_receipt.yaml"
    qwen_receipt = root / "approvals" / "owner_n2b2_qwen_fact_binding_remediation_receipt.yaml"
    artifact_integrity_receipt = (
        root / "approvals" / "owner_n2b2_s20_artifact_integrity_remediation_receipt.yaml"
    )
    if (
        not owner_receipt.is_file()
        or not qwen_receipt.is_file()
        or not artifact_integrity_receipt.is_file()
    ):
        typer.echo("N2B2_S20_NOT_AUTHORIZED")
        raise typer.Exit(code=int(ExitCode.PARTIAL_FAILURE))
    fixtures = load_s20_manifest(
        resolved_manifest, project_root=root, baseline_manifest_dir=resolved_baseline
    )
    schemas_dir = root / "schemas"
    reasoning_schema = load_json_strict(schemas_dir / "n2b2_photography_reasoning.schema.json")
    vision_schema = load_json_strict(schemas_dir / "n2b2_vision_fact_contract.schema.json")
    cache_root = load_n2b1p_runtime_configuration(root).cache_root
    config = N2B2RunConfig(
        project_root=root,
        cache_root=cache_root,
        fixtures_dir=resolved_manifest,
        runtime_out_dir=resolved_out,
        backend="real",
        device="cuda",
        s3_only=False,
    )
    try:
        summary = run_s20(
            config=config,
            fixtures=fixtures,
            reasoning_schema=reasoning_schema,
            vision_schema=vision_schema,
            reviewed_commit=reviewed_commit,
            review_record=resolved_review,
            owner_receipt=owner_receipt,
            qwen_receipt=qwen_receipt,
            artifact_integrity_receipt=artifact_integrity_receipt,
            resume=resume,
        )
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=int(ExitCode.PARTIAL_FAILURE)) from None
    typer.echo(f"N2B2 result: {summary.get('result', S20_COMPLETE)}")
    typer.echo(f"summary: {resolved_out / 'validation_summary.json'}")
    if summary.get("result") != S20_COMPLETE:
        raise typer.Exit(code=int(ExitCode.PARTIAL_FAILURE))


@n2b2_app.command("qwen-contract-probe")
@_run_safely
def n2b2_qwen_contract_probe(
    device: str = typer.Option("cuda", "--device"),
    case_id: str = typer.Option("n2b2-s20-03", "--case-id"),
    review_record: Path = typer.Option(..., "--review-record"),
    fixture_manifest_dir: Path = typer.Option(..., "--fixture-manifest-dir"),
    baseline_manifest_dir: Path = typer.Option(..., "--baseline-manifest-dir"),
    vision_evidence_dir: Path = typer.Option(..., "--vision-evidence-dir"),
    out: Path = typer.Option(..., "--out"),
) -> None:
    """Run the frozen Case 03 Qwen fact-binding probe before S20."""

    from .json_strict import load_json_strict
    from .n2b2_synthetic import load_s20_manifest
    from .n2b2_synthetic.qwen_probe import _load_case_facts, run_qwen_contract_probe
    from .n2b2_synthetic.s20_orchestrator import _review_gate

    root = find_project_root()
    if device != "cuda" or case_id != "n2b2-s20-03":
        typer.echo("N2B2_QWEN_BINDING_NOT_AUTHORIZED")
        raise typer.Exit(code=int(ExitCode.PARTIAL_FAILURE))

    def external_path(value: Path, label: str) -> Path:
        resolved = value.resolve()
        try:
            inside = os.path.commonpath((str(root.resolve()), str(resolved))) == str(root.resolve())
        except ValueError:
            inside = False
        if inside:
            raise RuntimeError(f"{label} must be Git-external")
        return resolved

    resolved_review = external_path(review_record, "review record")
    resolved_manifest = external_path(fixture_manifest_dir, "fixture manifest")
    resolved_baseline = external_path(baseline_manifest_dir, "baseline manifest")
    resolved_vision = external_path(vision_evidence_dir, "vision evidence")
    resolved_out = external_path(out, "probe output")
    state = load_json_strict(root / "PROJECT_STATE.json")
    if state.get("phase_status", {}).get("N2B2") != "LOCKED":
        typer.echo("N2B2_PROJECT_STATE_BOUNDARY_VIOLATION")
        raise typer.Exit(code=int(ExitCode.PARTIAL_FAILURE))
    review_payload = json.loads(resolved_review.read_text(encoding="utf-8"))
    reviewed_commit = review_payload.get("reviewed_commit")
    if not isinstance(reviewed_commit, str):
        typer.echo("N2B2_QWEN_BINDING_NOT_AUTHORIZED")
        raise typer.Exit(code=int(ExitCode.PARTIAL_FAILURE))
    owner_receipt = root / "approvals" / "owner_n2b2_s20_synthetic_validation_receipt.yaml"
    qwen_receipt = root / "approvals" / "owner_n2b2_qwen_fact_binding_remediation_receipt.yaml"
    try:
        _review_gate(resolved_review, owner_receipt, qwen_receipt, reviewed_commit)
        fixtures = load_s20_manifest(
            resolved_manifest, project_root=root, baseline_manifest_dir=resolved_baseline
        )
        fixture = next(item for item in fixtures if item.case_id == case_id)
        facts = _load_case_facts(resolved_vision, case_id)
        if facts.get("image_sha256") != fixture.image_sha256:
            raise ValueError("N2B2_QWEN_BINDING_FAILURE_EVIDENCE_DRIFT")
        reasoning_schema = load_json_strict(
            root / "schemas" / "n2b2_photography_reasoning.schema.json"
        )
        summary = run_qwen_contract_probe(
            project_root=root,
            fixture=fixture,
            facts=facts,
            reasoning_schema=reasoning_schema,
            out=resolved_out,
        )
    except (ValueError, StopIteration) as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=int(ExitCode.PARTIAL_FAILURE)) from None
    typer.echo(f"Qwen probe: {summary.get('result')}")
    typer.echo(f"summary: {resolved_out / 'probe_summary.json'}")
    if summary.get("result") != "N2B2_QWEN_FACT_BINDING_CONTRACT_PROBE_PASS":
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
