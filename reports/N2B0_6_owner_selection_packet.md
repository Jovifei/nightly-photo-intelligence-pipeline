# N2B0.6 Owner Selection Packet

Status: `N2B0_6_NO_OWNER_SELECTABLE_CANDIDATE`.

The four fixed candidate records are now complete metadata bundles, but all
four independently fail the frozen official-SHA-256 selection condition. This
is not a recommendation to download or to compute a local substitute hash.

1. Select a Pose + segmentation pair: unavailable. Pose is 0/2 ready and
   segmentation is 0/2 ready.
2. Select a qualified single-class candidate: unavailable. Neither class has a
   ready candidate.
3. Keep every download and later stage locked: the only available and
   recommended disposition.

The SHA-256-only rule remains frozen in this remediation. No alternative hash
policy is being proposed, reviewed, or applied; SHA-384 remains recorded only
as existing distinct metadata and does not unlock a candidate.

MODNet remains source-and-conversion evidence only: its possible outputs are
`NOT_GENERATED`, and no runtime has been installed. N2B1-Q/P, N2B2, G2, G3,
and all photo/model operations remain locked.
