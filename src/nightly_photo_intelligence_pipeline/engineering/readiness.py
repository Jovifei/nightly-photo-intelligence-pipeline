"""Read-only readiness; no model imports, pip, installs, service starts or inference."""

from __future__ import annotations

import http.client
import importlib.metadata
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .common import EngineeringError, require, strict_json

SUPPORTED = ">=3.11,<3.13"
MAX_RESPONSE = 1024 * 1024


def python_check(version: tuple[int, int, int]) -> dict[str, Any]:
    supported = version[0] == 3 and 11 <= version[1] < 13
    return {
        "name": "python_support",
        "status": "PASS" if supported else "FAIL",
        "observed_version": ".".join(map(str, version)),
        "requires_python": SUPPORTED,
        "code": "NPI_PYTHON_SUPPORTED" if supported else "NPI_UNSUPPORTED_PYTHON",
    }


def dependency_checks(
    project_file: Path, lookup: Callable[[str], str] = importlib.metadata.version
) -> list[dict[str, Any]]:
    project = tomllib.loads(project_file.read_text(encoding="utf-8"))["project"]
    require(project.get("requires-python") == SUPPORTED, "NPI_PYTHON_CONTRACT_CHANGED")
    requirements = list(project["dependencies"]) + list(project["optional-dependencies"]["dev"])
    results = []
    for spec in requirements:
        require(isinstance(spec, str) and spec.count("==") == 1, "NPI_UNSUPPORTED_REQUIREMENT")
        name, expected = spec.split("==")
        require(bool(name) and bool(expected), "NPI_UNSUPPORTED_REQUIREMENT")
        try:
            installed = lookup(name)
        except importlib.metadata.PackageNotFoundError:
            results.append(
                {
                    "name": name,
                    "expected": expected,
                    "status": "NOT_AVAILABLE",
                    "code": "NPI_DEPENDENCY_MISSING",
                }
            )
            continue
        results.append(
            {
                "name": name,
                "expected": expected,
                "observed": installed,
                "status": "PASS" if installed == expected else "FAIL",
                "code": "NPI_DEPENDENCY_MATCH" if installed == expected else "NPI_DEPENDENCY_DRIFT",
            }
        )
    return results


def ollama_version_probe(
    factory: Callable[..., Any] = http.client.HTTPConnection,
) -> dict[str, Any]:
    """Only GET /api/version on the exact loopback. No redirects or environment proxy."""
    connection = factory("127.0.0.1", 11434, timeout=3)
    try:
        connection.request("GET", "/api/version", headers={"Accept": "application/json"})
        response = connection.getresponse()
        require(response.status == 200, "NPI_OLLAMA_HTTP_NOT_OK")
        raw = response.read(MAX_RESPONSE + 1)
        require(len(raw) <= MAX_RESPONSE, "NPI_OLLAMA_RESPONSE_TOO_LARGE")
        payload = strict_json(raw)
        version = payload.get("version") if isinstance(payload, dict) else None
        require(isinstance(version, str) and bool(version.strip()), "NPI_OLLAMA_RESPONSE_INVALID")
        return {
            "name": "ollama_service",
            "status": "PASS",
            "version": version,
            "code": "NPI_OLLAMA_METADATA_REACHABLE",
            "identity_verified": False,
            "model_loaded": False,
        }
    except (TimeoutError, ConnectionError, OSError, http.client.HTTPException):
        return {
            "name": "ollama_service",
            "status": "NOT_AVAILABLE",
            "code": "NPI_OLLAMA_UNREACHABLE",
            "identity_verified": False,
            "model_loaded": False,
        }
    except EngineeringError as exc:
        return {
            "name": "ollama_service",
            "status": "FAIL",
            "code": str(exc),
            "identity_verified": False,
            "model_loaded": False,
        }
    finally:
        connection.close()


def readiness(project_file: Path, *, probe_ollama: bool = False) -> dict[str, Any]:
    checks = [
        python_check((sys.version_info.major, sys.version_info.minor, sys.version_info.micro))
    ]
    checks.extend(dependency_checks(project_file))
    if probe_ollama:
        checks.append(ollama_version_probe())
    return {
        "schema_version": "npi-engineering-readiness-v1",
        "checks": checks,
        "result": "READY_FOR_CODE_CHECKS"
        if all(row["status"] == "PASS" for row in checks)
        else "BLOCKED_ENVIRONMENT",
        "execution_authorized": False,
        "scope": "PYTHON_AND_METADATA_ONLY_NOT_GPU_CAPABILITY_VALIDATION",
    }
