# H0 — synthetic execution lease preparation delivery

**Base candidate:** `main@1b9997ba0b099fd159932a8de0697f78d1fc7867`  
**Purpose:** prepare a machine-generated, non-authorizing request packet for the next single synthetic S3/S20/resume execution.

H0 deliberately does **not** create an APPROVED lease, an Owner anchor, a runtime identity, or an execution. It adds a standalone request builder that is intended to run locally against a clean detached checkout of the reviewed base candidate and Git-external evidence.

## Why this is the next stage

The reviewed code now requires a separate Git-external Owner anchor that hashes the exact APPROVED lease. The remaining dynamic bindings—current runtime identity, fixture manifests, cache binding, and exact path plan—exist only on the Owner machine. Guessing them in Git would defeat the admission design. H0 therefore closes the manual-copy gap without pretending cloud code can observe local runtime state.

## H0 output

`lease_request.py` outputs one canonical JSON packet with:

- exact candidate commit/tree/full tracked-source digest;
- `PROJECT_STATE.json` digest and an enforced `N2B2=LOCKED` check;
- external review and quality-evidence hashes;
- current Qwen/Ollama identity and canonical identity digest;
- S3/S20 fixture-manifest hashes;
- model-cache binding hash;
- exact path-plan digest matching the controlled adapter shape;
- a proposed **DRAFT** lease with every real-photo/App/Bundle/system boundary false;
- an explicit list of Owner actions still required.

The packet always states `execution_authorized=false` and `owner_anchor_created=false`.

## Stage sequence

- **H0 (this commit):** cloud lease-request tooling and tests.
- **H1 (local Codex):** run the builder against `main@1b9997ba`, real Git-external review/quality evidence, existing local cache/fixtures/path plan, and a read-only current identity record. Do not start Ollama just to satisfy H1; if the identity source is unavailable, report it as the blocker.
- **H2 (Owner):** independently inspect the request. Only the Owner may select the validity window, create exact APPROVED lease bytes outside Git, hash those bytes, and create the separate external anchor. Approval of H2 is synthetic-only.
- **H3 (local Codex):** one fresh S3/S20 plus same-identity no-op resume using the approved lease/anchor.
- **H4:** independent review of the new runtime evidence and Owner phase decision.
- Then, and only then, a **separate** Real20 data authorization.

## Development validation

H0 unit tests use temporary synthetic Git repositories and files only. They exercise clean-source binding, full source identity, N2B2 lock enforcement, identity validation, duplicate JSON rejection, exact path-plan shape, path collision, and bad-digest rejection. No model/network/photo/SQLite/App operation is performed.
