# N2B2 authorized synthetic validation — 2026-08-23

## Status

```text
N2B2_SYNTHETIC_MODEL_STACK_VALIDATION_COMPLETE_AWAITING_EXTERNAL_REVIEW
N2B2_STATE=LOCKED
REAL20=NOT_PERFORMED
PRODUCTION_BUNDLE_RELEASE=NOT_CREATED
```

This is a bounded synthetic review candidate. It is not production phase
completion, a real-photo authorization, a G1 renewal, or an App release.

## Authorization and Git

- N2B1P candidate: `0fef0a8f6a2f2b2f75ce2fba3e3eef1e764037b8`.
- N2B2 synthetic candidate parent: `c1008132654d32e7ac6a2032eb5d3a2c7e07cdb6`.
- Authorization candidate commit: the final commit SHA is reported from `HEAD`
  after this report is included; the report does not self-bind to its own SHA.
- `PROJECT_STATE.json` was not modified; production `N2B2` remains locked.
- The main branch was not moved, pushed, merged, or released.

## Fresh S3 evidence

External alias: `EXTERNAL_RUNTIME_WORK/n2b2-s3-authorized-20260823-v1/`.

- A: `person_count=1`, keypoint groups `1`, LRASPP person ratio `0.005125`.
- B: `person_count=2`, keypoint groups `2`, LRASPP person ratio `0.198330`.
- C: `person_count=0`, keypoint groups `0`, LRASPP and comparator ratios `0`.
- Canonical facts: byte-identical repeat and digest-stable.
- Qwen: schema PASS, digest echo PASS, fact IDs valid, forbidden fields `0`.
- GPU: peak `11392 MiB`; Torch `2.11.0+cu128`, TorchVision `0.26.0+cu128`,
  `cuda:0`, float32, no fallback.
- S3 summary SHA-256: `d25c9597463b036159b8aa4ee48f09452b87cd534fa64465131443170e8949bd`.

## Fresh S20 evidence

External alias: `EXTERNAL_RUNTIME_WORK/n2b2-s20-authorized-20260823-v1/`.

- 20 bundles; strict/observation/negative/unsupported: `10/8/1/1`.
- Two-round facts: bytes and digests identical.
- Qwen: schema PASS, digest echo PASS, unknown fact IDs `0`, forbidden fields `0`.
- GPU: baseline `4869 MiB`, peak `11461 MiB`, after unload `5066 MiB`.
- Checkpoint completed; Ollama was explicitly unloaded.
- No-op resume: exit `0`, 149 files before/after, changed `0`, removed `0`.
- Runtime artifact hashes:
  - `validation_summary.json`: `c9ee55df1123758ac92fd8916fee676137a6ffdc537a035b82f1badeeda2133b`
  - `checkpoint.json`: `97749f3b3e94abc641827fce8652af1d611db27df70c13e116be3390b5bcf256`
  - `runtime_metrics.json`: `cc3282fcb2ff272bdeff7c131d66aad4a0288ef53ab9e29516fc9f54a8e90fb3`
  - `synthetic_bundle_index.json`: `91ad5bd860434bb62daf2fee09194a2307599c387217e064ae4dcd906b9898cc`
  - `CHECKSUMS.sha256`: `98263f32a1cabd121a49f4a01a9a918e00d50debf69c102ede8fb22139d9a615`

## Counters and quality

```text
REAL_PHOTO_READ_COUNT=0
REAL_EXIF_READ_COUNT=0
G1_SOURCE_ACCESS=0
SQLITE_WRITE_COUNT=0
APP_WRITE_COUNT=0
OBSIDIAN_WRITE_COUNT=0
S20_RUNTIME_OBSIDIAN_WRITE_COUNT=0
MODEL_DOWNLOAD_BYTES=0
```

- pytest: `540 passed`.
- preflight: `16 pass / 0 fail`.
- handoff: `7 pass / 0 fail`.
- sensitive scan: `0 violations`.
- `git diff --check`: PASS.
- Ruff and mypy: `NOT_AVAILABLE` in the current environment; no dependency was
  installed, so the unified quality command truthfully reports `4 PASS / 3 FAIL`.

The candidate therefore remains awaiting independent external review and does
not claim all quality gates are green.

## 2026-08-23 final-source v2 continuation

After Ruff/mypy were explicitly installed and the authorization gate was
formatted, the runtime source was revalidated instead of reusing a checkpoint
with a different source digest. Fresh v2 S3 and S20 runs completed successfully.

- S3 summary alias: `EXTERNAL_RUNTIME_WORK/n2b2-s3-authorized-20260823-v2/`;
  SHA-256 `4f8e8a8f440be023bc63b3046bb911743467c4573a76e6b77ce1ccd2a49b93ef`.
- S20 summary alias: `EXTERNAL_RUNTIME_WORK/n2b2-s20-authorized-20260823-v2/`.
- S20 bundle count `20`; strict/observation/negative/unsupported `10/8/1/1`.
- S20 GPU peak `11338 MiB`; after unload `3529 MiB`.
- S20 `validation_summary.json` SHA-256:
  `5d90e7903867d3247285abf3264ff8910418b8c042ac5a14719760b4d63b7f3e`.
- S20 `checkpoint.json` SHA-256:
  `39417a37fbb6be44a992f3582b2171cfa30c8c2d7fc9e668b5ea74ffc28a4e9d`.
- S20 `runtime_metrics.json` SHA-256:
  `82c32dc8fa160907b205965d6a617c9b1883ac95e3fbaf79cdda138ec7dea7c5`.
- S20 `CHECKSUMS.sha256` SHA-256:
  `0ac856028e6cac725da5fa0311a384f1f49f023d0318df104853cf11e4167eb4`.
- No-op resume again returned exit `0` with 149 files before/after and zero
  changed or removed files.

Final-source quality evidence:

- pytest `540 passed`;
- unified quality `7 PASS / 0 FAIL / 0 NOT_AVAILABLE / 0 SKIPPED`;
- Ruff `0.15.21` check and format PASS;
- mypy `2.3.0` PASS, 68 source files;
- preflight `16/0`, handoff `7/0`, sensitive scan `0`.

The final candidate still requires the independent external Review result. No
main fast-forward, Real20, G1, real-photo, EXIF, SQLite, App, or production
Bundle action was performed.
