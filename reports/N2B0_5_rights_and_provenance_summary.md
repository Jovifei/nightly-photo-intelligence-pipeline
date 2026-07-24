# N2B0.5 Rights and Provenance Summary

Owner: Jovi · Date: 2026-07-24 · Status: `N2B0_5_RIGHTS_CLARIFICATION_BLOCKED`

## 2026-07-26 governance remediation evidence

- Independent review found a duplicate JSON member in `PROJECT_STATE.json`.
  The duplicate was removed: the sole `data_scope.N2B0_MODEL_ARTIFACT_QUALIFICATION`
  value is `APPROVED_COMPLETE`.
- Authorization and preflight now follow this fail-closed order: raw bytes →
  strict duplicate-member JSON parse → Draft 2020-12 structural Schema
  validation → semantic authorization validation. Duplicate members return
  `NPI_DUPLICATE_JSON_MEMBER`; a Schema cannot repair parser ambiguity.
- The strict loader protects current project state, task/state catalogs,
  security-critical schemas, fixture manifest reads, and authorization paths.
  YAML remains in its existing YAML parsing boundary; the artifact allowlist is
  YAML and stays `DRAFT_NOT_AUTHORIZED`, never a runtime authority.
- Future N2B1 governance is represented only by no-I/O policy checks. N2B1-Q
  quarantine download, N2B1-P cache promotion, N2B2 execution, and all model
  bytes remain locked. ZIP inspection is metadata-only; `.pth` quarantine
  permits byte hash and metadata only and forbids deserialization.
- Review regression coverage exercises duplicate JSON, rights, official HTTPS
  redirects, exact Content-Length, ETag/Last-Modified non-authority,
  quarantine/cache two-approval sequencing, direct-Python gate refusal, and
  ZIP/PTH policy. No request or model payload is made by these tests.

## 2026-07-26 transport-metadata remediation evidence

- Independent review required two fail-closed corrections: the final response
  URL's artifact basename must exactly match the approved filename, and every
  future transfer must carry a positive Owner maximum-byte ceiling.
- The no-I/O policy now treats the final URL as authoritative for filename
  binding. It ignores query and fragment, percent-decodes once, rejects empty
  or directory basenames, separators, NUL/control characters, and mismatches,
  and compares the normalized filename case-sensitively. Errors expose only a
  stable code and generic reason, never a full URL, query, header, or path.
- A future N2B1-Q approval requires the artifact ID, exact filename, official
  request URL, allowed final domains, expected size, Owner ceiling, redirect
  maximum, quarantine fingerprint, expiry, and Owner decision reference. The
  policy rejects missing, non-integer, zero, negative, or server-exceeded
  ceilings before any quarantine action.
- The four artifact verdicts remain `READY_FOR_QUARANTINE_DOWNLOAD = FAIL`.
  The draft allowlist remains `DRAFT_NOT_AUTHORIZED` and contains no Owner
  ceiling. No model bytes, model execution, or real-photo reads occurred:
  each remains 0.
- Child A and Child B were `NOT_DISPATCHED_PARENT_DIRECT`, not PASS: the
  tightly coupled policy/schema/test remediation cost less to review directly,
  and the prior comparable Child-Claude package had reached three watchdog
  timeouts.
- Clean-commit local evidence: 316 pytest passed; Ruff, formatting, mypy,
  quality 7/7, sensitive scan, preflight 15/15, strict JSON scan, and diff
  check all exited 0. Detailed results are in
  `reports/N2B0_5_transport_gate_test_evidence.md`.

## 2026-07-26 composed quarantine-gate remediation

- Independent review found that a standalone N2B1-Q approval gate and a
  standalone transport validator could each pass while binding different
  artifact metadata. They are no longer public production entry points.
- The only public N2B1-Q validation entry takes strict approval JSON bytes,
  strict qualification-snapshot JSON bytes, strict project-state JSON bytes,
  actual transport metadata, and explicit time. It parses strict JSON before
  Schema and semantic checks, then derives every transport expectation from
  the raw approval. Its frozen output is descriptive metadata only, never a
  credential for a later download, promotion, or execution action.
- The approval binds exact request URL; separate request and final-domain
  allowlists; redirect limit and every redirect hop; final filename; expected
  bytes; Owner cap; quarantine fingerprint; rights snapshot; project-state
  digest; N2B0.5 baseline SHA; Owner decision; and validity interval.
- Approval expiry, not-yet-valid time, revocation, state/snapshot mismatch,
  unqualified rights, URL/user-info/port/trailing-dot/Unicode host ambiguity,
  and all caller metadata mismatches fail closed. The returned immutable object
  proves metadata consistency only and cannot perform a download.
- The current production state remains N2B1-Q locked and all four artifacts
  remain `READY_FOR_QUARANTINE_DOWNLOAD = FAIL`; no valid production approval
  can be created. Download bytes, model execution, and real-photo reads remain
  0.
- Final local evidence for this remediation: 81 focused governance/composition
  tests and 322 repository tests passed; every required quality command exited
  0. The composed test file has 48 negative test entries plus two additional
  denial branches. This is local validation evidence only, not Reviewer PASS
  or Owner approval.

## 2026-07-26 schema and trust-boundary remediation

- Reviewer blockers addressed: `_VALIDATION_TOKEN` and all token/factory
  constructor logic were removed. Frozen DTOs remain ordinary result data and
  are deliberately not an authorization capability; direct construction,
  `object.__new__`, mutation attempts, and `isinstance` cannot substitute for
  raw-document validation at an action boundary.
- The composed no-I/O entry now processes all documents in observable order:
  strict duplicate-member parse plus fixed approval Schema, then fixed closed
  qualification-snapshot Schema, then fixed project-state Schema, followed by
  document digest/baseline, owner/time/status, qualification-rights, state
  cap/stage, and finally actual transport semantics.
- `model_artifact_qualification_snapshot_v1` is closed and versioned. It
  requires identity, filename, qualification/right statuses, official request
  and domains, expected size, evidence/source digests, N2B0.5 Git baseline,
  and generation time. `READY=PASS` is still subject to semantic rights checks.
- Project-state schemas are selected only through the fixed local catalog:
  current locked v1.2 and future capability-gated v1.3 are accepted; absent or
  unknown claimed versions and unavailable/invalid catalog Schemas fail closed.
  No caller supplies a schema path or schema bytes.
- This is still a code-only remediation. The four real qualification records
  remain fail-closed and `READY_FOR_QUARANTINE_DOWNLOAD = FAIL`; model-download
  bytes, model execution, real-photo reads, cache/quarantine writes, archive
  extraction, and payload deserialization remain 0.
- Child A/B are `NOT_DISPATCHED_PARENT_DIRECT`, not PASS. Comparable bounded
  read-only Child-Claude work had already exhausted three watchdog timeouts;
  the parent completed and verified this tightly coupled code/schema/test task.
- Final local evidence: 103 focused N2B0.5 tests and 344 repository tests
  passed. Ruff, formatting, strict mypy, unified quality (7 PASS), sensitive
  scan, current-stage preflight (15 PASS), strict JSON scan (52 tracked, two
  isolated expected-invalid fixtures, zero production duplicates/malformed),
  and `git diff --check` each exited 0. This is not a new Reviewer verdict.

## Authorization and boundary

- N2B0 approved baseline: `f331621c84905aef921c612908d01d3a8a2f577a`;
  local tag `n2b0-approved-2026-07-24`.
- N2B0.5 is authorized only for official-source rights/provenance closure.
- N2B1 download, N2B2 benchmark execution, G2/G3, real-photo reads, model
  payloads, dependency installation, Docker pulls, and system changes remain
  locked.
- No model payload bytes, model dependencies, model outputs, or real photos were
  read or created. Model download bytes: 0; model execution: 0; real photo reads: 0.

## Four-artifact matrix

| candidate | exact filename | official source/domain | revision | HEAD size | code license | weight license | commercial | official SHA | ready |
|---|---|---|---|---:|---|---|---|---|---|
| Pose preferred RTMPose-m | `rtmpose-m_simcc-coco-wholebody_pt-aic-coco_270e-256x192-cd5e845c_20230123.pth` | MMPose model index / `download.openmmlab.com` | v1.3.0 model-index; artifact revision UNKNOWN | 72010049 | PASS Apache-2.0 | UNKNOWN | REQUIRES_OWNER_DECISION (evidence UNKNOWN) | UNKNOWN | FAIL |
| Pose fallback RTMW-m | `rtmw-dw-l-m_simcc-cocktail14_270e-256x192-20231122.pth` | MMPose model index / `download.openmmlab.com` | v1.3.0 model-index; artifact revision UNKNOWN | 129787113 | PASS Apache-2.0 | UNKNOWN | REQUIRES_OWNER_DECISION (evidence UNKNOWN) | UNKNOWN | FAIL |
| Seg preferred PP-HumanSegV2-Lite | `human_pp_humansegv2_lite_192x192_inference_model.zip` | PaddleSeg `release/2.10` / `paddleseg.bj.bcebos.com` | release/2.10 model page; artifact revision UNKNOWN | 11349952 | PASS Apache-2.0 | UNKNOWN | REQUIRES_OWNER_DECISION (evidence UNKNOWN) | UNKNOWN | FAIL |
| Seg fallback MediaPipe general | `selfie_segmentation.tflite` | MediaPipe model index / `storage.googleapis.com` | legacy model index; object revision UNKNOWN | 249505 | PASS Apache-2.0 | UNKNOWN | REQUIRES_OWNER_DECISION (evidence UNKNOWN) | UNKNOWN | FAIL |

For all four: artifact identity, official domain, size, and zero-redirect HEAD
were observed; immutable artifact revision, weight/model license, commercial
evidence, and official SHA-256 remain `UNKNOWN`. Every commercial disposition
therefore remains `REQUIRES_OWNER_DECISION`. ETag and Last-Modified are retained
only as non-authorizing HEAD evidence in the detailed research files.

## Recommendations

- Pose preferred: RTMPose-m wholebody. Pose fallback: RTMW-m.
- Segmentation preferred: PP-HumanSegV2-Lite 192x192. Segmentation fallback:
  MediaPipe Selfie Segmentation general. MediaPipe landscape is documented but
  not selected as a fifth artifact.
- No candidate is ready for quarantine download. SAM2 remains escalation-only.
- The artifact allowlist status is `DRAFT_NOT_AUTHORIZED`.

## Child-Claude evidence

Child A was dispatched as a read-only MMPose package with a 30-second watchdog
and 90-second timeout. Attempts 1, 2, and 3 all returned
`Success=false`, `TimedOut=true`, zero stdout/stderr bytes, and no structured
result. No child result was treated as PASS. Parent official-source research
and independent HEAD checks supplied the evidence above. Children B/C/D were
not dispatched after the same child-service timeout pattern; they are recorded
as `NOT_ATTEMPTED_PARENT_FALLBACK`, not PASS.

## Blocking and non-blocking findings

- Blocking: weight/model terms, commercial use, immutable artifact revision, and
  official SHA-256 are unresolved for all four artifacts.
- Non-blocking: code licenses, exact official URLs/filenames, HEAD sizes,
  content types, zero redirects, and draft domain mapping are recorded.
- Unverified: runtime compatibility, VRAM, latency, OOM, model quality, and
  training-data commercial terms; all remain `NOT_MEASURED` or `UNKNOWN`.

Detailed evidence: `research/N2B0_5_mmpose_weights_rights.md`,
`research/N2B0_5_paddleseg_weights_rights.md`,
`research/N2B0_5_mediapipe_artifact_identity.md`, and
`research/N2B0_5_artifact_provenance.md`.

## 2026-07-26 revision/hash/time contract remediation

- The external Reviewer identified two contract blockers in the prior N2B0.5
  candidate: status-only immutable-revision/official-hash fields did not carry
  the actual evidence, and future N2B1-Q `not_before` was optional. This
  amendment addresses only those blockers; it is local validation evidence,
  not a new Reviewer PASS or Owner approval.
- A closed qualification snapshot now requires `artifact_revision` with exact
  `kind`, non-floating `value`, and official HTTPS `source_url` whenever
  `immutable_revision_status=PASS`. Accepted kinds are `GIT_COMMIT`,
  `GIT_TAG`, `RELEASE_ASSET_VERSION`, `OBJECT_VERSION`, and
  `CHECKPOINT_REVISION`. `LATEST`, `MAIN`, `MASTER`, floating URLs, HTTP
  metadata labels, blank values, and date-only strings are rejected.
- `official_hash_status=PASS` now requires an actual lower-case, 64-hex
  `official_artifact_sha256` and an official HTTPS hash-source URL. ETag,
  Last-Modified, Content-Length, MD5, SHA-1, a local quarantine hash, or a
  future computed download hash are not official-hash evidence. A non-PASS
  status requires the corresponding evidence fields to be `null`.
- A future approval must contain the same closed `artifact_revision` object
  and `expected_sha256`; both are exact-equality bound to the snapshot before
  transport. Any change also changes the canonical snapshot digest, so a stale
  approval fails closed. `READY=PASS` requires both evidence statuses and
  values to be valid.
- `not_before` is required, RFC-3339 timezone-aware, and caller-supplied time
  remains explicit. The pure validator enforces
  `issued_at <= not_before < expires_at`, treats `now == not_before` as active
  and `now == expires_at` as expired, and compares normalized UTC instants.
- The four real draft candidates do not instantiate a `PASS` qualification
  snapshot. Their only valid future-snapshot representation remains
  `artifact_revision=null`, `official_artifact_sha256=null`,
  `immutable_revision_status=UNKNOWN`, `official_hash_status=UNKNOWN`, and
  `READY_FOR_QUARANTINE_DOWNLOAD=FAIL`. The existing YAML draft's descriptive
  research text is not an approval or a qualification snapshot.
- Child A/B remain `NOT_DISPATCHED_PARENT_DIRECT`, not PASS: three comparable
  Child-Claude attempts had already exhausted their timeout cap. All new tests
  use future synthetic metadata only. Model-download bytes, model execution,
  real-photo reads, cache/quarantine writes, archive extraction, payload
  deserialization, push, merge, and release remain 0.
- Final clean-worktree evidence for this amendment: 147 focused N2B0.5 tests
  and 384 repository tests passed. Ruff, formatting, strict mypy, unified
  quality (7 PASS, 0 FAIL, 0 NOT_AVAILABLE, 0 SKIPPED), sensitive scan,
  preflight (15 PASS, 0 FAIL, 0 NOT_AVAILABLE, 0 SKIPPED), strict JSON scan,
  and `git diff --check` each exited 0. This remains local evidence, not a
  Reviewer verdict.
