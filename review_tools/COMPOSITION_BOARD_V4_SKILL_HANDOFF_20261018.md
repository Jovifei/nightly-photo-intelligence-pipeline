# Composition board v4 — attachment delivery and local integration handoff

Status: DOCUMENTATION_DELIVERY_ONLY_NOT_EXECUTION_ELIGIBLE.
Date: 2026-10-18.
Owner request: revise the supplied composition-board-v3 Skill and analysis prompt into a photographer-directed reproduction workflow; assess a local RTX 4070 SUPER route before considering a separately scoped Codex/cloud fallback.
This is an unsigned documentation/scope record, not an Owner resource receipt or a phase acceptance.

## Exact repository context

Repository: Jovifei/nightly-photo-intelligence-pipeline only.
Inspected existing review branch: chatgpt/npi-fetcher-lease-crash-state-20261001.
Inspected commit: a6b515eed1f2a4b46a1adf14953417f8cf3e0686.
Inspected tree: 2ff9627f64bd2110d4f2f291009925ba35922764.
Delivery review branch: chatgpt/composition-board-v4-skill-20261018.
The final commit/tree containing this receipt are supplied by the GitHub creation result and the final conversation receipt; do not invent self-referential hashes inside this document.

Read: MASTER_EXECUTION_CONTRACT.md, PROJECT_STATE.json, docs/00_reading_order.md, AGENTS.md, current N2B1P task/approval; relevant tasks/todo history/current summary and the prior R1 trusted-bootstrap work package. This was not a full exact-SHA code review of the existing R1 implementation.

## Delivered artifact and binding

The complete revised Skill package is a conversation attachment, NOT installed pipeline code and NOT stored in this repository by this receipt-only commit. Local Codex must obtain the actual Owner-supplied attachment, verify its hashes, and read it before installation; a digest alone is not the file and must not be reconstructed by guessing.

Attachment: composition-board-v4_20261018.zip
Bytes: 30815
SHA-256: 5aa27261b6ee23bb87204f4b8ffc594ccabd92d5f881bd8b33dfa94e73935869

The archive contains composition-board-v4/ with:

```text
c058b6c8526f05c246bd3ccdc101cab5569ea51e7662e9661ab3d6f68a7bc229  SKILL.md
05ad23ae3f67140650194f3e63c0a64cfa79a16c0d5350b96dba987ea1f7a5fd  PROMPTS.md
064b2931010d54ea8d1238079bc6551f61725f36cd72a9c986b5d36894d97350  OWNER_REQUIREMENTS_composition_board_v4.md
a6b1eb75de9a010cc8780b417a90a6326ea3532bc524c8d0671ac2d85a60c757  LOCAL_CODEX_HANDOFF.md
8d3366f9bd8ec934cfb4da319e28c30326511bb22e302d1a5e95482ea068d261  SOURCES.md
20e311c9cf9360e13922759fdbbadebe3ebcf0e8519eeae8409141a9044f4bf0  VALIDATION_REPORT.json
de407ce8bdcfe1177310ced17e4a117ab6bc7aa07dbf866d28f087d2cd0f502b  verify_static_docs.py
```

MANIFEST.sha256 binds these seven archive members. No source photos, reference screenshots, crops, boards, model artifacts, databases or raw execution logs are in the archive or this commit. The two original uploaded Markdown files were retained unchanged.

## Findings in v3 and completed documentation changes

1. Existing v3 covers layout and basic eye/hand/body fields but does not define a complete camera-position and stepwise directing workflow. V4 now requires whole-image relationships -> visual effect -> reproduction constraints, then camera side/height/pitch/framing/perspective/props and per-subject detail.
2. Add separate photographer setup, ordered second-person spoken commands, observable checks, corrective commands and shutter cues. Add explicitly fictional scene/emotion guidance, action beats and a neutral alternative; do not infer a depicted person's real history or psychology.
3. Separate observed/measured/estimated/unknown/not-applicable facts from reproduction suggestions. Do not fabricate exact focal length, 3D body angles, geographic sun azimuth, distances or exposure. Approved pose geometry remains authoritative; VLM text cannot invent or override it.
4. Resolve image-side versus anatomical-side ambiguity and mirror cases. Closed eyes have no visible gaze target; invisible eyes and fingers remain unknown. Each hand has visibility, placement, height, finger/prop details and evidence.
5. Preserve the source photo at native aspect; a full-width middle band; faithful same-photo lineart at lower left; evidence-consistent topdown at lower right; footer and light explanation. Cropped source bodies must not be outpainted as full-body measurements. Dynamic text layout replaces truncating a fixed band height.
6. One scene_geometry feeds text, overlays and topdown. Explicit local coordinates, light-origin versus light-travel direction, uncertainty markers, no unjustified north arrow, and separate mirror optical-path reasoning.
7. Distinguish automatic checks, AI self-review, actual human review and Owner sample acceptance. Preserve 2-6 sample approval before authorized batching/sync, and independently gate installation and export.
8. Correct the old C-drive temporary-output example against the Owner's approved local output requirement. Exact machine paths stay in the local attachment/configuration rather than this tracked receipt.
9. Local VLM inference and cloud Codex image analysis are different data paths. Default local provider, no automatic cloud fallback, existing qualified artifact identity first, one heavy model at a time, synthetic qualification before separately authorized photo samples. Hardware feasibility is not a local benchmark result.

## Local actions still required

- Continue the existing project/handoff context; do not open a new chat merely to recover a connection.
- Confirm the actual local workspace and current exact commit, all reading-order requirements, current task/approval records and data/phase gates.
- Obtain and verify the attachment; locate the actual installed Skill and active pipeline implementation. Do not assume uploaded path/function hints establish local capabilities.
- Install the new Skill through the actual local mechanism, preserve the old version, bind Skill/Prompt identity and ensure v3/v4 do not both claim the task.
- Implement the defined closed JSON Schema, semantic rejection tests, provenance/mapping, shared geometry, directing fields and rendering changes only under applicable code authority. The attachment defines these contracts; it does not implement the existing pipeline's validator or patch its functions.
- Read approved local GPU/runtime/model identity evidence before resource execution. When authorized, qualify synthetic input, then separately authorized 2-6 photo boards. Verify runtime performance and photography detail quality separately.
- Use existing export contracts for future App integration. Do not access/change the App repository from this documentation task.
- Report exact branch/commit/tree, actual commands and exit codes, limitations, scoped manifests and remaining Owner gates. Do not send photos or raw logs back remotely.

## Test evidence and limitations

Executed in the remote sandbox on text files only:

```text
python verify_static_docs.py --originals <directory-containing-the-two-uploaded-Markdown-files> --report <approved-report-output>
exit 0; 12 static checks PASS; 0 FAIL; 0 SKIPPED with both original files present.
```

Without --originals, the original-file integrity comparison is explicitly SKIPPED, not PASS. Checks cover UTF-8/nonempty files, frontmatter markers, balanced code fences, exact Prompt extraction, numbered section/layout order, required rule markers and unchanged uploaded Markdown hashes. These are lexical/document checks, not schema implementation tests or visual correctness tests.
Archive CRC test: PASS. Member SHA-256 manifest generated from actual bytes.

NOT_RUN/NOT_IMPLEMENTED: Windows/native/GPU/Ollama/model/cache/bootstrap execution; real-photo analysis; EXIF/GPS/SQLite; board rendering and visual quality; pipeline schema/semantic validator integration; repository full quality and root-manifest eligibility; App integration, sync/install and TTS.

This receipt-only branch changes no implementation, production state, task approval, existing R1 branch or root MANIFEST.sha256. Root/overlay qualification has NOT been reissued for this new documentation commit. It must not be passed to resource admission as a newly qualified execution candidate. Bind/refresh appropriate manifests under the separate integration task before claiming execution eligibility.

## Remaining gates

No resource or stage acceptance is granted. Main merge, release, real-photo/EXIF/SQLite/model execution, native bootstrap, expanded datasets/downloads, App changes, phone installation, N8/full-library/OpenClaw and actual cloud transmission remain subject to their separate gates. All future authorized downloads remain under the existing Owner-approved download root. Final project goal remains PILOT_APP_INTEGRATION_PASS; this documentation delivery does not claim that goal has been reached.
