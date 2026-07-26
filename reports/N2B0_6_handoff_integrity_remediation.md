# N2B0.6 Current-Stage Handoff Integrity Remediation

Scope: remediate the independent review finding against the sole unapproved
N2B0.6 candidate. This document is not a completion approval, model-download
approval, or authorization for N2B1/N2B2/N3.

## Trigger

The fresh read-only review of `03f110296d256ce896eebd0bf9afb5b2a01b57e6`
returned `CHANGES_REQUIRED`: `tools/verify_handoff.py` was explicitly N0-only
and its historical manifest no longer bound current-stage governance and
evidence. The master and Codex entry documents still named N0 as current.

## Remediation boundary

- The verifier checks the current N2B0.6 authorization contract, approved
  immutable baselines, exact tracked-file manifest, clean worktree, and
  sensitive-path/model-artifact exclusions.
- The N0 archival command returns `N0_ARCHIVAL_SUPERSEDED`, exit 8; it is not
  reported as a pass or a current-stage preflight.
- Current entry documents point to the N2B0.6 metadata-only task.
- The manifest is regenerated from tracked files after all edits and must hash
  every one of them exactly.

## Prohibited-action attestation

No payload or Range download, dependency installation, model loading or
inference, real-photo read, cache/quarantine write, archive extraction,
system change, push, merge, or release occurs in this remediation.

## Required follow-up evidence

The amended candidate must pass the full quality suite and a new independent
read-only review. Until then, N2B0.6 remains awaiting review and every
follow-on phase stays locked.

## Clean-candidate result

The clean amended candidate passed 421 tests, Ruff, formatting, mypy,
`tools/run_quality.py` (7 pass / 0 fail / 0 not available / 0 skipped), the
sensitive-file scan (0 violations), strict JSON scan (0 production duplicate
members / 0 malformed), preflight (15 pass / 0 fail), current-stage handoff
verification (5 pass / 0 fail), and `git diff --check`. The historical N0
mode returned exit 8 and was not counted as a pass. A fresh independent review
is still pending; no completion approval/tag exists.
