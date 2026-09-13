# Local Codex handoff — apply the delivered patch on the latest branch; do not reset main

Repository: Jovifei/nightly-photo-intelligence-pipeline
Branch: codex/n2b2-ollama-runtime-identity-revalidation-20260906
Frozen runtime candidate: da638bab6a61fe6fc466521cc60abcacfea9120a

## Scope of this handoff

The delivered patch is a review-tooling overlay, not a new model execution lease
or production phase transition. Read review_tools/README.md and
review_tools/AUDIT_AND_ROADMAP_20260913.md before proceeding. Do not merge main, force
push, amend published history, create a release or access real photos. Preserve the
Owner's dirty primary-worktree AGENTS.md byte-for-byte; record its complete before/
after hash locally without publishing paths. Do not stash, restore or commit it.

1. The remote source write was blocked; no new remote commit or branch update was
   made by the web agent. Fetch actual remote refs. The expected branch HEAD is
   da638bab6a61fe6fc466521cc60abcacfea9120a. If newer commits exist, inspect the
   delta and preserve them rather than resetting. The included overlay verifier
   deliberately accepts exactly one direct child of da638bab; do not force its
   profile onto an unknown newer lineage.

   On the expected baseline create a new clean non-elevated tooling worktree and a
   separate detached runtime-review worktree at da638bab. Do not use the dirty
   primary worktree. Verify the package hashes, then apply ONLY the ten additions
   using the included npi_review_tooling_20260913.patch:
   git apply --check <PATCH>
   git apply <PATCH>
   python -m unittest discover -s review_tools -p 'test_*.py' -v
   git diff --check
   git add -- review_tools
   Recompute all nine SHA-256 values from Git INDEX bytes and compare with
   review_tools/MANIFEST.sha256. Root MANIFEST and every original file must remain
   unchanged. Create one local child commit, then run the explicit overlay check
   and tests again on the clean candidate. Do not amend the published da638bab.
   Only after all overlay checks pass, push the local child to the same named
   remote branch with an ordinary non-force push. Do not update main or old refs.
   Record the new commit/tree and compare the remote branch after the push.

2. In the tooling worktree run:
   python review_tools/verify_overlay.py
   python -m unittest discover -s review_tools -p 'test_*.py' -v
   python review_tools/evidence_audit.py --help
   Record versions, commands, exit codes and complete test counts. Any unavailable
   filesystem tests are NOT native PASS. No dependency installation is needed.

3. In the frozen da638bab worktree rerun the project's existing full quality,
   preflight, MANIFEST and handoff checks in the already provisioned environment.
   Keep all output outside both worktrees and outside model cache/source/evidence.
   Do NOT run tools/verify_handoff.py on the tooling HEAD and then weaken it to make
   it green: it is a different acceptance artifact. The two-manifest tooling profile
   is not a substitute for the runtime gate. Report both matrices independently.

4. Locate only the known completed da638bab S3/S20 and remediation evidence roots
   from previous local records. No drive-wide or photo-directory discovery. Obtain
   the NEW S20 CHECKSUMS.sha256 digest from a retained execution/review record;
   do not reuse the previous Ollama 0.32.15 run's digest. Preserve a before inventory.
   Run the offline auditor from the tooling worktree with that explicit root/digest:
   python review_tools/evidence_audit.py --evidence-root <KNOWN_NEW_S20_ROOT> --checksums-sha256 <TRUSTED_NEW_DIGEST>
   Save stdout into a separate new review directory. Rehash original evidence after.
   This command does not contact Ollama, load models, modify checkpoint or grant PASS.

5. Complete the checks that the offline tool explicitly does not perform: all actual
   schemas, S3 evidence, exact da638bab full-tree provenance, receipt links, immutable
   old evidence, GPU telemetry, and a genuinely fresh separate-process no-op resume
   of the already COMPLETE new S20 from the frozen runtime worktree. Reuse only the
   legitimate historical review record and commands from the original run; never
   forge PASS or alter a checkpoint. Before resume verify exact saved/current full
   identity, COMPLETE checkpoint and all input bindings. If identity drifted again,
   stop the live check as INCONCLUSIVE but finish the offline review. Do not downgrade,
   spoof versions or repeat S3/S20 using the consumed one-shot permit. Do not invoke
   runtime-identity-revalidate as an audit command.

6. Read actual quality_matrix.json and remediation_result.md. Determine whether they
   contain full command evidence or only the CLI's placeholder-style runtime summary.
   Missing logs remain missing. Check whether final-source identity observations and
   a separate-process resume exit code exist. Report raw SHA-256 anchors for all major
   artifacts, hashes before/after, and declared vs instrumented forbidden counters.
   Redact local paths from any public summary. Do not modify the historical evidence.

7. Reproduce F1–F6 on synthetic/unit-test inputs only. The supplied reference geometry
   computes a bbox union proxy; it is NOT aesthetic negative space. Demonstrate the
   left/right subject example and overlap example. Inspect one-shot consumption and
   all output-root intersections before any inference. Record findings independently
   of whether the old synthetic run's artifact checks pass.

8. The next engineering patch should be small: integrate the tested geometry with an
   explicit method/version and denominator, add receipt-keyed atomic one-shot
   reservation, validate the entire set of protected/output/fixture roots before
   model activity, close the GPU numeric-validation gap, and enrich evidence with
   real commands/identity checkpoints. Preserve strict COMPLETE identity equality.
   Do not refactor unrelated modules, change models, or introduce another framework.
   This handoff does not create an Owner approval or a new consumed permit; stage
   code-only changes and synthetic tests only under the Owner's current coding scope.
   Before publishing any continuation, version its exact topology/manifest policy
   without rewriting da638bab or this overlay. A new inference attempt needs a fresh
   explicit Owner-bounded synthetic execution lease tied to the final code candidate;
   leave that lease as DRAFT until the Owner actually approves. Never fabricate dates,
   model identities, manifest digests or external review results to fill a template.

9. First return a bounded review packet with (a) exact runtime/tooling SHAs and tree
   relationship; (b) both quality matrices; (c) actual evidence hashes; (d) offline
   audit result; (e) live resume status and file deltas; (f) F1–F6 confirmations or
   counter-evidence; (g) AGENTS unchanged proof; (h) minimal code-only remediation
   diff/test status; (i) unresolved local/Owner actions. Use an independent reviewer
   for the implementation when available; an implementer's self-check is not one.
   Do not call the whole project complete or silently accept a missing hard gate.

10. After technical review and Owner acceptance, the product path is fresh Real20
    authorization → measured real-photo quality → minimal N3/N4 → N5 human review
    and APPROVED-only Bundle → actual App import/rollback → 100-photo pilot → full
    run → scheduler. Do not create a Real20 manifest, read photos, alter PROJECT_STATE,
    run a pilot or change the App in this handoff. Report the concrete prerequisite
    for the next gate rather than redesigning the entire project again.
