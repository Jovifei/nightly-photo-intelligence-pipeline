# Local validation of the remote GitHub candidate

Status: CHANGES_REQUIRED. This is test evidence, not a DONE review receipt.

## Identity and collaboration scope

- Remote branch: `chatgpt/n2b1p-final-review-20260930`.
- Tested remote commit: `fb54b4a6c5b44868e275d6651cc1acf79889c704`.
- Local feedback branch: `codex/npi-remote-receive-20261001`.
- Owner instruction: reuse the existing Cache Recovery Plan chat in the
  Nightly Photo Composition Analysis Project; remote GPT reviews, repairs,
  implements the next bounded stage and commits a handoff; local Codex receives,
  tests and returns evidence through GitHub review branches.
- Owner explicitly authorized the review-branch push and this repository
  handoff loop. This does not authorize main merge or release.

## Actual validation

Used the existing qualified external Python 3.12 quality environment, without
environment creation or dependency installation.

1. `python -m pytest -q tests/test_review_candidate_governance.py tests/test_n2b1p_b_source_network_reacquisition_v1.py`
   - Exit 1: 58 passed, 5 failed.
   - All five failures arise from `NameError: OWNER_PATH` in
     `tools/verify_review_candidate.py::_change_category`.
2. Focused Ruff check of the changed source, CLI, governance tool and tests:
   - Exit 1: five findings.
   - `OWNER_PATH` and `RUNTIME_PATH` are undefined in the governance tool.
   - `_change_category` exceeds the configured return-count limit.
   - One line in the governance tool and the receipt-schema pin line in the
     B-source module exceed the configured line length.
3. `python -m mypy src/nightly_photo_intelligence_pipeline`
   - Exit 0: 102 source files, no issues.

Full quality was not broadened after focused regressions failed. No model,
CUDA, photograph, EXIF, SQLite, payload acquisition, cache promotion, or
external DONE receipt was executed or created.

## Required remote follow-up

Repair the concrete source failures on the existing remote review branch,
refresh both manifests, and supply the committed review report, next bounded
stage plan and local Codex handoff. Mark remote tests NOT_RUN if no terminal
is available. The next local step is to fetch the final handoff commit, review
the diff, rerun the focused matrix, then execute required complete gates and
return the exact tested SHA for remote review before any payload acquisition.
