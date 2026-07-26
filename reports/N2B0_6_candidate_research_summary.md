# N2B0.6 Candidate Research Summary

Owner: Jovi. Scope: official metadata-only bundle evidence remediation.
Disposition: `N2B0_6_NO_OWNER_SELECTABLE_CANDIDATE`.

The fixed pool remains exactly two Pose and two lightweight person-segmentation
candidates. All four records now receive per-file and bundle validation even
though their final readiness is FAIL. There is no eligible pair and no eligible
single class.

The current evidence-binding remediation adds three fail-closed constraints:
each payload filename must equal the canonical basename of both its fixed
direct URL and the recorded final URL; each `MODEL_CONFIGURATION` evidence
item must point to that candidate's exact pinned OMZ `model.yml`; and each
license PASS is a typed evidence-ID decision rather than a non-null URL
string. Every payload also cross-references source, checksum, and model-license
evidence, with checksum assertions checked back against the payload fields.

| Class | Candidates | Static bundle records complete | Ready for Owner artifact selection |
|---|---:|---:|---:|
| Pose | 2 | 2 | 0 |
| Lightweight person segmentation | 2 | 2 | 0 |

All seven model payload files have direct official URLs, fixed source revision,
exact size, official SHA-384, and complete HEAD metadata in the candidate
record. The official SHA-256 requirement remains independently unsatisfied for
all four candidates, so `OFFICIAL_SHA256_CONFIRMED=FAIL` forces final readiness
to FAIL. SHA-384, ETag, Content-Length, or a local computation are not
substitutes.

MODNet is no longer represented as a checkpoint-only candidate: the static
record contains the source/config/converter dependency closure. Its output
artifacts are `NOT_GENERATED`, and its converter runtime is
`NOT_INSTALLED_NOT_VERIFIED`; neither is a measured model result.

Counters: payload download bytes 0; Range response bytes 0; dependency installs
0; conversions 0; model executions 0; archive/cache/quarantine writes 0;
real-photo reads 0; pushes/merges/releases 0. N2B1-Q/P, N2B2, G2, G3, and
N3-N8 remain locked.
