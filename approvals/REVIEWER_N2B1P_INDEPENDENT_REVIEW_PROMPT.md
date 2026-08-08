# Independent Review — N2B1P Local-Research Cache Promotion

You are the **independent external reviewer** for the `N2B1P_LOCAL_RESEARCH_CACHE_PROMOTION`
phase of the **nightly-photo-intelligence-pipeline** project. The executing agent stopped
correctly at `N2B1P_REMEDIATION_COMPLETE_AWAITING_EXTERNAL_REVIEW`. Your job is to
independently verify the on-disk evidence is genuine (not merely asserted), then record a
PASS in the evidence file. Do NOT run any model, download, or modify any governance state
other than the three review fields described at the end.

---

## 1. Files to read (repository root: `<REPO_ROOT_REDACTED>`)

1. `research/N2B1P_cache_promotion_evidence.json` — the promotion evidence (primary object of review).
2. `tasks/phase_n2b1p_local_research_cache_promotion.yaml` — the task contract (what was authorized & forbidden).
3. `approvals/owner_n2b1p_cache_promotion.yaml` — Owner approval.
4. `approvals/n2b1p_runtime_configuration.json` — runtime config (`cache_root` path + `cache_root_identity`).
5. `research/N2B1R_acquisition_evidence.json` — the source acquisition evidence the promotion is bound to.
6. `research/N2B1R_local_research_artifact_register.json` — the artifact register (authoritative source of the three approved IDs / filenames / byte-counts / SHA-256).

## 2. On-disk artifacts to physically verify

Cache root (from runtime config): `<CACHE_ROOT_REDACTED>` (resolve it from
`approvals/n2b1p_runtime_configuration.json`; never transcribe the literal path into
version-controlled files)
Content-addressed layout: `<local_sha256>/<approved_filename>`

| Artifact ID | Expected cache path | Expected SHA-256 (`local_sha256`) |
|---|---|---|
| torchvision-lraspp-mobilenet-v3-large-coco-voc-v1 | `<CACHE_ROOT_REDACTED>\d234d4eae9d55d5f76de18b77cf0dc62c66fe5c5482758209d00f950c92bb280\lraspp_mobilenet_v3_large-d234d4ea.pth` | `d234d4eae9d55d5f76de18b77cf0dc62c66fe5c5482758209d00f950c92bb280` |
| torchvision-deeplabv3-mobilenet-v3-large-coco-voc-v1 | `<CACHE_ROOT_REDACTED>\fc3c493d68e89cc31ef488c803d5d7dd2f3190fb570598faa49fef69be8e5e70\deeplabv3_mobilenet_v3_large-fc3c493d.pth` | `fc3c493d68e89cc31ef488c803d5d7dd2f3190fb570598faa49fef69be8e5e70` |
| torchvision-keypointrcnn-resnet50-fpn-coco-v1 | `<CACHE_ROOT_REDACTED>\fc266e953d2b302cdcbb9ae66f71f6b0d4649928bf02dc573961e361e4918926\keypointrcnn_resnet50_fpn_coco-fc266e95.pth` | `fc266e953d2b302cdcbb9ae66f71f6b0d4649928bf02dc573961e361e4918926` |

Recompute SHA-256 of each `.pth` file (e.g. `certutil -hashfile "<path>" SHA256` on Windows,
or `sha256sum`) and confirm it equals the `local_sha256` in the evidence. Confirm file byte
size equals `byte_count`. A match proves `verification_status: CACHE_HIT` is real, not asserted.

## 3. Verification checklist (audit these)

1. **Evidence-binding integrity:** For each of the 3 artifacts, the `id`, `cache_filename`,
   `byte_count`, and `local_sha256` in `N2B1P_cache_promotion_evidence.json` EXACTLY match the
   corresponding entry in `N2B1R_local_research_artifact_register.json` (and
   `N2B1R_acquisition_evidence.json`). No ID / filename / SHA was altered.
2. **Cache-hit authenticity:** The 3 `.pth` files exist at the expected content-addressed paths
   and their recomputed SHA-256 + size match. (`verification_status: CACHE_HIT` is genuine.)
3. **Cache-manifest consistency:** For each artifact, `cache_manifest_sha256` matches a
   path-redacted manifest file written adjacent to the promoted payload, and `cache_root_identity`
   equals `15cb613d6ecb39247799adca13c6fcbfd9c9edb72c223db7cebf1ee975d7b2ba` (from runtime config).
4. **Runtime-config binding:** `runtime_configuration.configuration_digest` in the evidence
   (`462e999671c2073ef8d02cbeaccd561cbc1f4734c4f312baee079a8134040bfd`) equals
   `configuration_digest` in `approvals/n2b1p_runtime_configuration.json`, and
   `n2b1r_evidence_sha256` matches the N2B1R evidence file's hash.
5. **Prohibited actions all NOT_PERFORMED:** Confirm `prohibited_actions` shows no model
   load/inference, no CUDA, no SQLite ingest write, no EXIF/source-photo read, no network/download,
   no dependency install, no cache/quarantine delete. Cross-check the filesystem: no new downloads,
   no modified Git history, no created DB/EXIF artifacts.
6. **Containment boundaries:** Quarantine and cache parents are non-reparse, outside the Git repo
   and outside the runtime work root; the two-repo boundary and read-only source rule are intact.
7. **Correct stop:** `result == N2B1P_REMEDIATION_COMPLETE_AWAITING_EXTERNAL_REVIEW`,
   `mandatory_stop.value == true`, `next_action == EXTERNAL_REVIEW_N2B1P_REMEDIATION`. The agent did
   NOT proceed to N2B2 / model execution / CUDA / real-photo access.
8. **Handoff verifier (recommended):** from the repo root run
   `python tools/verify_handoff.py` — it is N2B1P-pinned and should report PASS at this stage.

## 4. How to record the PASS (only if ALL checks above pass)

Edit `research/N2B1P_cache_promotion_evidence.json` and ADD (do not remove or alter other fields)
these three fields at top level:

```json
"review_verdict": "PASS",
"independent_reviewer": "<your-name-or-agent-id>",
"external_review": {
  "reviewed_at_utc": "<ISO-8601 timestamp>",
  "method": "independent on-disk SHA-256 recomputation + evidence-binding cross-check",
  "all_three_artifacts_cache_hit_verified": true,
  "prohibited_actions_confirmed": true,
  "notes": "<short free-text summary of what you verified>"
}
```

Do NOT change `result` unless the project schema explicitly requires a reviewed state — adding the
three fields above is what unlocks the N2B2 gate (the N2B2 contract checks for their presence).
After editing, re-run `python tools/verify_handoff.py` to confirm the handoff verifier still passes.

## 5. Out of scope / forbidden for the reviewer

- Do NOT run any model, Ollama, CUDA, or download anything.
- Do NOT mark N2B2 authorized; do NOT edit `PROJECT_STATE.json`, `tasks/index.json`, or any governance verifier.
- Do NOT push/merge. Just record the three review fields and stop.
