# Review tooling overlay — 2026-09-13

## Two different artifacts, two different checks

Frozen inference/runtime candidate: `da638bab6a61fe6fc466521cc60abcacfea9120a`.
This directory is a **tooling-only overlay**, not a successor authorized to run models.
It is delivered as a patch: the web agent did not publish a new remote commit.
The runtime source, schemas, approvals, tasks, PROJECT_STATE and root MANIFEST remain
byte-for-byte unchanged. Do not claim that the historical 560 tests, 8/8 handoff,
or GPU results were freshly obtained on the overlay commit.

The existing `tools/verify_handoff.py` and production Git-topology tests are pinned
to the frozen runtime lineage. Run those on a detached worktree at `da638bab`, not
on this tooling HEAD. On this HEAD use the explicit tooling check below. This is
not a replacement for production preflight and grants no runtime or data authority.

The root `MANIFEST.sha256` binds the original runtime artifact. The separate
`review_tools/MANIFEST.sha256` binds every overlay file except itself. The overlay
verifier checks their **union against the complete Git index**, verifies that all
base files are unchanged, checks approved tags, and accepts exactly one direct
child of `da638bab` with exactly the ten declared added files. Unexpected files,
dirty trees, changed runtime bytes, hash errors and extra commits fail closed.

## Commands (from repository root)

```sh
python review_tools/verify_overlay.py
python -m unittest discover -s review_tools -p 'test_*.py' -v
python review_tools/evidence_audit.py --help
```

No dependencies need to be installed for these tools. They use Python's standard
library and Git (for the overlay check only). Cloud test environment: Python 3.13.5,
Linux; this is not a claim of validation of the project's Windows/Python 3.11–3.12
runtime. Symlink/hardlink tests need the corresponding local filesystem capability;
unavailable capabilities must be reported, never hidden as a passing native test.

## Audit a known external S20 evidence directory

```sh
python review_tools/evidence_audit.py \
  --evidence-root <KNOWN_EXTERNAL_S20_RELEASE> \
  --checksums-sha256 <TRUSTED_64_HEX_CHECKSUMS_SHA256>
```

Use a checksum digest from an independently retained local execution/review record,
not a value silently read from the very same untrusted directory. Obtain it from the
actual completed `da638bab` run; do not substitute the old Ollama 0.32.15 anchors.
Never point this command at source photos, model cache, App data or an entire drive.
Only JSON artifacts and CHECKSUMS are read. No image is opened, no endpoint contacted,
no database opened, no model imported and no evidence rewritten. Output is JSON on
stdout; any redirection must go to a **new separate review directory**.

The auditor verifies a bounded 149-file COMPLETE synthetic S20 layout, exact external
checksums, saved identity binding, inner bundle checksums, fact digests, cross-round
facts, primary/repeat Qwen response bindings, checkpoint response hashes, required
finite GPU peak and summary/metrics agreement. It compares stored composition
metrics to an explicitly defined bbox proxy without rewriting the stored facts.
Probe coverage is identity binding only; full schemas, GPU telemetry authenticity,
source-tree provenance and a fresh live resume remain separate reviewer checks.

Exit 0 means `ARTIFACT_CONSISTENCY_VERIFIED_NOT_RUNTIME_REVALIDATED`, **not**
`PASS_FOR_OWNER_REVIEW`, not an export approval and not Real20 authorization.
Declared zero counters are reported as declarations, not independently measured OS
telemetry. Nonempty stories/prompts are coverage, not a photographic quality score.
Double hashing and reparse rejection detect at-rest corruption and common races;
this is not a claim of Windows handle-level, race-proof filesystem confinement.

## Bbox empty-area reference algorithm

`negative_space.measure_bbox_empty_area(boxes, width, height)` clips rectangles,
computes their union and measures the empty area in each half-frame. It uses the
corresponding half-frame area as denominator. For a 100×100 frame with one person
box `(0,0)-(20,100)`, results are left=0.6, right=1.0, top=bottom=0.8, total=0.8.
Duplicate/overlapping boxes are not counted twice. Missing or nonfinite coordinates
fail instead of becoming invented zero observations.

This is a **bounding-box empty-area proxy**, not measured background simplicity,
subject saliency or aesthetic negative space. Its method/version and denominator
must be explicit when integrated. It is intentionally **not wired into the frozen
N2B2 runner**: integration changes the fact contract/digest and needs its own tested
candidate and fresh, expressly authorized synthetic evidence. Old facts must not
be edited or retroactively signed with the new algorithm.

See `AUDIT_AND_ROADMAP_20260913.md` and `NEXT_LOCAL_CODEX_PROMPT.md`.
