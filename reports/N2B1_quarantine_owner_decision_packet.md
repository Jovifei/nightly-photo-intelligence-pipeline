# N2B1 Quarantine Owner Decision Packet (not an approval)

N2B1 remains `LOCKED`. This packet records choices for a future Owner action;
it does not authorize a GET, cache write, dependency install, model load, or
inference.

## Required future gate sequence

1. N2B1-Q must be expressly authorized for one artifact and include a second,
   artifact-bound Owner approval before a quarantine request can begin.
2. A complete transfer is not promotable without the computed local SHA-256
   matching the approved exact SHA-256. A mismatch is rejected for deletion by
   the future N2B1 procedure; no cache promotion follows.
3. N2B1-P must receive a separate Owner approval before cache promotion.
   Promotion never grants N2B2 execution.
4. N2B2 stays locked until a separate execution approval. ZIP entry metadata
   must reject path escape, symlink, executable, count, and expanded-size
   violations; `.pth` quarantine must not call `torch.load`.

HTTP HEAD 200, ETag, Last-Modified, Content-Length, code Apache-2.0, or a
draft allowlist are individually insufficient for every step above.

## Suggested, unapproved transfer ceilings

These are planning tolerances only, not Owner approval and not a mutation of
the `DRAFT_NOT_AUTHORIZED` allowlist. Each is the recorded HEAD length plus
1 MiB (1,048,576 bytes); a future Owner may choose a lower value or refuse the
artifact entirely. The approval must name the selected exact value.

| artifact | recorded HEAD bytes | suggested maximum bytes |
|---|---:|---:|
| RTMPose-m | 72,010,049 | 73,058,625 |
| RTMW-m fallback | 129,787,113 | 130,835,689 |
| PP-HumanSegV2-Lite | 11,349,952 | 12,398,528 |
| MediaPipe Selfie general fallback | 249,505 | 1,298,081 |

For any future N2B1-Q transfer, the final HTTPS response basename must equal
the approved exact filename, after one percent-decoding and Unicode NFC
normalization, with case-sensitive comparison. Query and fragment do not
alter the name. A redirect whose final name differs is rejected. The final
response Content-Length must be positive, equal the approval's expected size,
and no greater than the separately approved Owner maximum; neither the server
nor the draft can increase that maximum.

## Future approval composition requirements

The approval must include an approval ID, Owner identity, Owner decision
reference, issued/not-before/expiry time, revocation state, exact artifact identity,
request URL, separate request/final allowlists, redirect limit, expected size,
Owner cap, quarantine fingerprint, all rights statuses, rights snapshot digest,
project-state digest, and N2B0.5 baseline SHA. A single composed validator
must strict-parse duplicate members and validate fixed approval,
qualification-snapshot, and catalog-selected project-state Schemas before it
derives transport expectations from the approval. Its frozen returned metadata
is not a credential: a future action must revalidate raw documents and cannot
accept a hand-built or previously returned DTO.

The approval must also exactly reproduce the snapshot's closed immutable
revision object (`kind`, `value`, official HTTPS source URL) and its official
lower-case 64-hex artifact SHA-256. `not_before` is mandatory and the accepted
window is `issued_at <= not_before < expires_at` in UTC. No status label,
ETag, Last-Modified, Content-Length, local quarantine hash, or computed future
hash can substitute for this evidence.

Current artifacts cannot meet this approval: all four retain unknown weight
terms, unresolved commercial evidence, immutable revision, and official hash,
so `READY_FOR_QUARANTINE_DOWNLOAD = FAIL`. This packet remains a decision aid,
not an approval or a download instruction.

## Option A — keep all downloads locked (recommended)

Wait for official weight licenses, commercial-use statements, immutable
artifact revisions, and official SHA-256 values for at least one Pose and one
Segmentation candidate. No external state change.

## Option B — rights clarification only

Owner may approve sending the draft questions in
`research/N2B0_5_upstream_questions_draft.md` through an explicitly named
channel. This still authorizes no download and no external message until a
separate approval names the channel and recipients.

## Option C — prepare a future exact N2B1 selection

Owner may nominate RTMPose-m + PP-HumanSegV2-Lite, or their fallbacks, for a
future N2B1 request after the blocking rights fields close. A later approval
  must separately bind artifact ID, filename, URL, allowed final domains,
  revision, expected size, Owner maximum bytes, redirect maximum, computed
  SHA-256, quarantine fingerprint, expiry, Owner decision reference, and
  deletion/rollback policy.

Current decision: no option opens N2B1. `DRAFT_NOT_AUTHORIZED` remains true.
