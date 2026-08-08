"""Local Ollama loopback client for the N2B2 photography-reasoning VLM.

Hard gates (CODEX §4, §9, §10):

* Only ``http://127.0.0.1:11434`` is ever contacted. Any other host/port,
  or an explicit non-loopback URL, raises a security-boundary error.
* The model is identified before use: name ``qwen3.5:9b``, ``vision``
  capability present, quantization ``Q4_K_M``.
* Images are sent as in-memory Base64; no absolute path is ever placed in a
  request or response.
* Generation uses ``stream=false``, ``think=false``, a strict JSON Schema
  ``format``, and ``keep_alive=0``; ``thinking`` is never persisted.
* After generation the client polls ``/api/ps`` to confirm the model unloaded.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse

from ..domain.errors import NPI_SECURITY_BOUNDARY
from .config import LOOPBACK_HOST, LOOPBACK_PORT, OLLAMA_BASE_URL, QWEN_MODEL, QWEN_QUANTIZATION


@dataclass(frozen=True)
class ModelIdentity:
    model_name: str
    full_local_digest: str
    size_bytes: int
    format: str
    family: str
    parameter_size: str
    quantization_level: str
    capabilities: list[str]
    license: str
    modified_at: str
    ollama_version: str


def assert_loopback(base_url: str) -> None:
    """Raise if *base_url* is not the exact Ollama loopback endpoint."""

    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname != LOOPBACK_HOST or parsed.port != LOOPBACK_PORT:
        raise PermissionError(
            f"{NPI_SECURITY_BOUNDARY}: Ollama must be reached only via loopback "
            f"{OLLAMA_BASE_URL}; refused {base_url!r}"
        )


class OllamaClient:
    """Thin, testable wrapper around the local Ollama HTTP API."""

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        opener: Callable[[urllib.request.Request], Any] | None = None,
    ) -> None:
        assert_loopback(base_url)
        self.base_url = base_url.rstrip("/")
        self._opener = opener or (lambda req: urllib.request.urlopen(req, timeout=200))

    # -- low-level HTTP ---------------------------------------------------
    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        try:
            with self._opener(req) as resp:
                raw = resp.read().decode("utf-8")
        except URLError as exc:  # pragma: no cover - network dependent
            raise ConnectionError(f"Ollama loopback unreachable at {url}: {exc}") from exc
        if not raw:
            return {}
        return json.loads(raw)

    # -- identity ---------------------------------------------------------
    def verify_identity(self) -> ModelIdentity:
        tags = self._request("GET", "/api/tags")
        models = tags.get("models", [])
        entry = next((m for m in models if m.get("name") == QWEN_MODEL), None)
        if entry is None:
            raise ValueError(f"{QWEN_MODEL} not found in Ollama; N2B2_LOCAL_QWEN_IDENTITY_MISMATCH")
        details = entry.get("details", {})
        capabilities = details.get("capabilities", [])
        if "vision" not in capabilities:
            raise ValueError(
                "qwen3.5:9b lacks vision capability; N2B2_LOCAL_QWEN_VISION_CAPABILITY_MISSING"
            )
        quantization = details.get("quantization_level", "")
        if quantization != QWEN_QUANTIZATION:
            raise ValueError(
                f"quantization {quantization!r} != {QWEN_QUANTIZATION}; "
                "N2B2_LOCAL_QWEN_IDENTITY_MISMATCH"
            )
        version = self._request("GET", "/api/version").get("version", "unknown")
        return ModelIdentity(
            model_name=QWEN_MODEL,
            full_local_digest=entry.get("digest", ""),
            size_bytes=int(entry.get("size", 0)),
            format=details.get("format", ""),
            family=details.get("family", ""),
            parameter_size=details.get("parameter_size", ""),
            quantization_level=quantization,
            capabilities=list(capabilities),
            license=details.get("license", "unknown"),
            modified_at=entry.get("modified_at", ""),
            ollama_version=str(version),
        )

    # -- generation -------------------------------------------------------
    def reason(
        self,
        *,
        image_b64: str,
        case_id: str,
        fact_digest: str,
        fact_ids: list[str],
        uncertainties: list[dict[str, Any]],
        response_schema: dict[str, Any],
        num_ctx: int = 8192,
        num_predict: int = 1200,
        temperature: float = 0.0,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """Run one VLM reasoning pass and return the parsed JSON object.

        ``image_b64`` is the in-memory Base64 of the synthetic image; no path
        is transmitted. ``keep_alive=0`` requests immediate unload.
        """

        prompt = self._build_prompt(
            fact_digest=fact_digest, fact_ids=fact_ids, uncertainties=uncertainties
        )
        payload: dict[str, Any] = {
            "model": QWEN_MODEL,
            "prompt": prompt,
            "images": [image_b64],  # in-memory only; never an absolute path
            "stream": False,
            "think": False,
            "format": response_schema,
            "options": {
                "num_ctx": num_ctx,
                "num_predict": num_predict,
                "temperature": temperature,
                **({"seed": seed} if seed is not None else {}),
            },
            "keep_alive": 0,
        }
        out = self._request("POST", "/api/generate", payload)
        text = out.get("response", "")
        parsed = (
            json.loads(text)
            if isinstance(text, str) and text.strip()
            else (text if isinstance(text, dict) else {})
        )
        # Defensive: never persist a thinking trace even if the server returns one.
        parsed.pop("thinking", None)
        parsed.pop("done", None)
        parsed.pop("done_reason", None)
        return parsed

    @staticmethod
    def _build_prompt(
        *, fact_digest: str, fact_ids: list[str], uncertainties: list[dict[str, Any]]
    ) -> str:
        return (
            "You are a photography interpreter. Use ONLY the provided deterministic "
            f"vision facts (fact_digest={fact_digest}). Referenced fact_ids: {fact_ids}. "
            f"Known uncertainties: {uncertainties}. "
            "Produce photographic_interpretation, story_candidates (safe/narrative/dynamic), "
            "director_prompts (standard/dramatic/plan_b/technical), and uncertainties. "
            "Do NOT output any forbidden field (person_count, bbox, keypoints, mask, "
            "pose_confidence, segmentation_confidence, EXIF, exact_focal_length, "
            "exact_camera_distance, copyright_status, real_mental_state)."
        )

    # -- unload -----------------------------------------------------------
    def verify_unloaded(self) -> bool:
        ps = self._request("GET", "/api/ps")
        models = ps.get("models", [])
        return not any(m.get("name") == QWEN_MODEL for m in models)
