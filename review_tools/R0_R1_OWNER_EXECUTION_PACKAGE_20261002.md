# R0 Owner Recovery Package and R1 Next Stage Plan

## R0 resource recovery package (approval required)

This document does not select resources for Owner.

## Cache target choices

### A1 preferred: recover original approved cache-root object

Goal:
restore the historical approved cache-root object while preserving object identity binding.

Acceptance:
- configured root exists;
- handle-bound identity matches approved runtime configuration;
- no reparse/overlap violation;
- artifact verification succeeds.

### A2 fallback: authorize new versioned cache root

Requires separate Owner approval.

Must create:
- new runtime identity binding;
- new attestation;
- new review evidence.

It must not impersonate historical cache identity.

## Payload source choices

### B1 preferred: restore exact approved quarantine hierarchy

Preserve:
- artifact bytes;
- manifest evidence;
- historical provenance.

### B2 fallback: exact-three controlled reacquisition

Requires:
- explicit Owner selection;
- exact source evidence;
- required review receipt;
- one-shot admission.

No network execution is authorized by this document.

## R0 execution order after approval

1. Resolve cache target choice.
2. Resolve payload source choice.
3. Validate source and target identities.
4. Promote each artifact independently.
5. Validate each artifact postcondition.
6. Stage closure validates all three CACHE_HIT.
7. Run local full quality.
8. Remote exact review.

## R1 next stage package

Scope:
Real20 admission only. Not execution authorization.

Selected design:

trusted runtime configuration
-> approved bootstrap contract
-> Codex bootstrap
-> runtime identity v3
-> cleanup_capability
-> restricted helper
-> pre-open cleanup handle inheritance
-> probe proof
-> cleanup proof
-> Real20 admission

No second Windows account is required.

Bootstrap requires independent contract, review and authorization before execution.

## R1 acceptance gates

- candidate commit/tree frozen;
- Python 3.12 quality environment verified;
- exact code review accepted;
- data receipt and frozen manifest bound;
- runtime identity v3 accepted;
- cleanup_capability restrictions proven;
- helper cannot expand permissions or search paths;
- one-shot lease remains unconsumed;
- Owner accepts REAL20_READY.

Real20, models, photos and EXIF remain separately gated.
