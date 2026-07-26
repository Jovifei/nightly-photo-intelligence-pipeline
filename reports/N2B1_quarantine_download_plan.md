# N2B1 Quarantine Download Plan (locked)

This is a future, non-executable plan. N2B1 is locked and no payload was
downloaded in N2B0.5.

N2B0.6 did not change this state: its bounded alternative-candidate research
now has complete static bundle evidence for four records, but every required
payload still lacks an official SHA-256. Therefore no N2B1-Q approval,
snapshot, quarantine destination, cache entry, or transfer is available. Any
future candidate must independently pass its own rights/revision/SHA-256
review and receive a separate Owner approval before this plan can be
considered. A SHA-384 value, ETag, or local computation is not a substitute.

1. Require a separate Owner approval bound to one exact artifact record and a
   second approval for any cache promotion. A valid N2B1-Q approval must bind
   artifact ID, exact expected artifact filename, official HTTPS request URL,
   allowed final domains, expected byte size, positive Owner byte ceiling,
   maximum redirects, quarantine-destination fingerprint, expiry, and Owner
   decision reference. It must also bind issued/not-before/expiry/revocation state,
   separate request/final domain allowlists, rights snapshot digest,
   project-state digest, and N2B0.5 baseline SHA. A missing field stops before
   quarantine starts.
2. Use only the per-artifact draft domain allowlist after rights closure;
   reject all redirects and final hosts not explicitly listed. Validate the
   final response URL (not the request URL): its one-time percent-decoded path
   basename must match the approved filename exactly, case-sensitively; a
   directory, empty name, separator/control escape, or mismatch is rejected.
3. Validate source/runtime/quarantine separation, external path ownership,
   reparse-point absence, available disk, and no photo-tree overlap.
4. Before a GET, validate the final response Content-Length is a positive
   integer, equals the approved expected size exactly, and is no greater than
   the explicit Owner byte ceiling. The server or artifact record cannot raise
   that ceiling. Stream bytes to a temporary quarantine filename, compute
   SHA-256, close handles, and never load/decode.
5. Require an exact closed artifact revision and official lower-case 64-hex
   SHA-256 that exactly equal the qualification snapshot evidence. The
   snapshot's revision/hash source URLs must be official HTTPS sources, and
   every evidence change must invalidate the canonical snapshot digest. Without
   one, stop at `OWNER_REVIEW_REQUIRED`; a local hash is not an official hash.
6. On any mismatch, delete the payload and retain only a redacted manifest.

All paths remain external placeholders; no real absolute path is stored.
Transport-policy errors record only the artifact ID, stable error code, and a
generic reason; they never record a signed URL, query, header, or local path.

Before any future GET, one composed no-I/O validator must strictly load the
approval, qualification snapshot, and project state; validate Schema,
semantics, current capability, rights, the required UTC-normalized
`issued_at <= not_before < expires_at` window, expiry, and all redirect hops; then
derive all transport expectations from the immutable approval. No caller may
provide or override filename, URL, domain list, redirect limit, size, cap, or
rights value separately. This design remains a future plan and grants no
current download authority.
