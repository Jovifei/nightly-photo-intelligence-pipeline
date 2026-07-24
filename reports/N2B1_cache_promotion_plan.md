# N2B1 Cache Promotion and Rollback Plan (locked)

Quarantine promotion is a separate Owner decision after a successful
download-only verification. The cache is outside Git and outside all source
and photo roots.

- Content-address the immutable cache entry by computed SHA-256 and record the
  artifact ID, exact URL, approval/snapshot-bound revision, official expected
  SHA-256, byte count, rights decision, and redacted
  quarantine manifest.
- Keep the payload read-only and never expose it to runtime until N2B2 is
  separately approved.
- If rights, hash, size, domain, or provenance changes, delete the unpromoted
  entry, verify zero payload bytes remain, and retain only the redacted audit
  record.
- Rollback removes the cache pointer and quarantined file; it never rewrites a
  previously approved manifest or Git baseline.

No cache or quarantine directory was created by N2B0.5.

Any future cache path must independently revalidate the three raw documents
through the single composed N2B1-Q validator at its action boundary. A
hand-built approval object, separately validated transport fields, or a prior
frozen validation result is not a credential. N2B1-P remains independently
locked and requires its own Owner approval even after a composed N2B1-Q check.
