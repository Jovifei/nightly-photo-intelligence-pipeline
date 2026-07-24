# N2B0.5 artifact provenance and supply-chain closure

## Evidence rules

1. Official repository/model-index/model-card/license pages are the only
   provenance sources. Mirrors, package indexes, and community checkpoints are
   excluded.
2. HTTP `HEAD` is permitted for status, final URL/domain, redirect count,
   Content-Length, Content-Type, ETag, Last-Modified, Accept-Ranges, and
   Cache-Control. No response body is persisted. ETag and Last-Modified are
   never used as SHA-256 or immutable revision.
3. `READY_FOR_QUARANTINE_DOWNLOAD` is PASS only after code and weight rights,
   commercial use, exact identity, immutable revision (or explicit Owner
   exception), exact size, official hash policy, domain, redirect chain, and a
   separate N2B1 Owner approval are all closed.

## Draft domain set (not authorization)

| purpose | domain | current status |
|---|---|---|
| MMPose checkpoints | `download.openmmlab.com` | observed official, draft only |
| PaddleSeg inference ZIP | `paddleseg.bj.bcebos.com` | observed official, draft only |
| MediaPipe linked model object | `storage.googleapis.com` | observed official link, draft only |

`config/model_artifact_allowlist.draft.yaml` remains
`DRAFT_NOT_AUTHORIZED`; no domain is currently permitted for a download.

## Future quarantine protocol (N2B1-only)

- Use a fresh external quarantine directory outside Git, source/runtime roots,
  and the photo tree; reject symlink/junction/reparse-point paths.
- Re-resolve DNS/TLS and enforce the exact HTTPS host. Reject any redirect or
  final host not in the Owner-approved per-artifact allowlist.
- Stream to a temporary quarantine filename, enforce the expected byte count,
  compute SHA-256 during/after the stream, and close the handle before any
  further action. Never load or decode the file in N2B1.
- Compare against an official SHA-256 when published. If absent, record the
  locally computed hash as `OWNER_REVIEW_REQUIRED`, not as an official hash.
- On size/hash/domain/rights mismatch, delete the quarantine payload and retain
  only a redacted manifest (artifact ID, source domain, observed size, hash,
  timestamps, and failure code).

## Cache, deletion, and rollback

Promotion from quarantine to the external immutable cache requires a second
Owner approval bound to the exact artifact ID, URL, revision, size, computed
SHA-256, rights decision, and quarantine manifest. Cache entries are content
addressed and read-only; no payload is copied into Git or the source tree.
Rollback deletes the unpromoted quarantine/cache entry, verifies zero payload
bytes remain, and retains only the redacted audit record. A later benchmark
must re-check the cache hash before loading. No cache or quarantine exists in
this N2B0.5 commit.
