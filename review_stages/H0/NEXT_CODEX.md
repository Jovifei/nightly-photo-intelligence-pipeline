# H1 local Codex handoff — build the DRAFT request, do not execute

1. Fetch the repository and verify `origin/main == 1b9997ba0b099fd159932a8de0697f78d1fc7867` unless a newer Owner-approved main is present. Do not reset published history. Use a new clean detached checkout of the exact reviewed runtime candidate for source binding; the H0 tooling may be read from its delivery branch separately.
2. Preserve the user's primary-worktree `AGENTS.md` change. Do not stage, reset, restore, stash-pop, or commit it.
3. Run H0 unit tests with the supported Python 3.12 environment. H0 tests are model-free.
4. Prepare Git-external inputs only from already-known Owner-controlled locations:
   - independent review artifact for the reviewed runtime candidate;
   - complete quality-evidence JSON from the supported 3.12 validation;
   - current runtime identity JSON with the exact six identity fields;
   - exact S3 and S20 `fixture_manifest.json` files;
   - current `cache_root_identity` from the validated runtime configuration;
   - one path-plan JSON with the exact `inputs/outputs/protected` labels expected by the current controlled adapter.
5. Do **not** scan a photo library. Do not read real photos/EXIF. Do not use G1 source paths to infer anything.
6. Do not start or upgrade Ollama just to make H1 pass. If no trustworthy current identity record can be obtained under the present authorization, stop with `H1_BLOCKED_RUNTIME_IDENTITY_UNAVAILABLE` and report what is missing.
7. Run `lease_request.py` against a clean detached checkout of the reviewed runtime candidate. Save the request packet outside Git. Re-run independently and require byte-identical output when the external inputs are unchanged.
8. Verify the request says `DRAFT_OWNER_REVIEW_REQUIRED`, `execution_authorized=false`, `owner_anchor_created=false`, and the proposed lease status is `DRAFT`.
9. Do not change the DRAFT to APPROVED, do not create the Owner anchor, do not consume a lease, and do not execute S3/S20/resume. Those are H2/H3 and require an explicit Owner decision.
10. Return the request path + SHA-256, candidate/tree/source digest, state hash, review/quality hashes, runtime identity hash, fixture/cache/path hashes, and any blocker. Stop at `H1_DRAFT_REQUEST_READY_FOR_OWNER_REVIEW` or an honest blocked state.

Product route after H4 remains: fresh Real20 -> human review -> APPROVED-only Bundle -> actual App import/display/reject/rollback -> 100-photo pilot -> full 500-600 library -> nightly scheduler. Do not detour into new models/vector DB/OpenClaw now.
