# G1 Owner Input Checklist

G1 (20-image calibration) is LOCKED. Before G1 may be authorized, the Owner
must provide or approve every item below. None of these were done in N0/N1
(real photo access is NOT_AUTHORIZED). This checklist is derived from
`OWNER_INPUTS_REQUIRED.md` and `reports/N1_unresolved_issues.md`.

## Owner decisions required

- [ ] **Real photo root authorization.** Explicit Owner approval of the real
      photo library root directory (absolute path provided by Owner, stored
      only in a local gitignored runtime config, never committed).
- [ ] **Windows/WSL read-only access method.** How the pipeline accesses the
      real photo root read-only (read-only ACL/share, `:ro` mount, or a
      read-only junction). Must not modify source permissions to "achieve"
      read-only.
- [ ] **20-image G1 calibration manifest.** An explicit list of 20 images
      (paths + SHA-256), not a whole directory. `--limit 20` does not enlarge
      permission; only manifest-listed assets may be processed.
- [ ] **File-extension whitelist confirmation.** Confirm the allowed
      extensions (candidate: `.jpg/.jpeg/.png/.webp/.tif/.tiff/.heic`).
- [ ] **Real EXIF read permission.** Whether real EXIF may be read (reading
      != inferring). VLM must not fabricate EXIF.
- [ ] **Disk budget** for runtime/work/artifacts/releases/cache.
- [ ] **Source library backup state confirmed.** Owner confirms the source
      library is backed up before any G1 processing.
- [ ] **Nightly/failure window.** Failure and recovery night window; stop
      threshold; human spot-check plan.
- [ ] **WAL decision.** Keep DELETE+FULL, or approve a WAL Benchmark + ADR.
- [ ] **Python 3.11 verification decision.** Accept 3.12-only, or require a
      3.11 test run.
- [ ] **G1 data-gate approval record.** A signed `approvals/data_gate_approval_*.yaml`
      with manifest, scope, expiry, and rollback method (per
      `OWNER_INPUTS_REQUIRED.md`).

## N1 readiness for G1 (already in place)

- Source guard: read-only, overlap/symlink/junction rejection, TOCTOU,
  pre/post integrity, path redaction.
- Real ingest: manifest-gated, idempotent, exact-duplicate merge, asset cap.
- State store: lease/heartbeat/retry/resume, append-only transitions,
  migration runner.
- DB stores only redacted source paths; no derived artifacts.
- G1 manifest membership check is the same mechanism as G0 (a 4th/non-manifest
  asset is rejected). G1 would supply a 20-image manifest.

## Still forbidden in G1 (unless separately approved)

- Model downloads (Pose/segmentation/VLM/embedding).
- 100 / full-library runs (G2/G3).
- Cloud, OpenClaw, main-App changes, push/merge.
