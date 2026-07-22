# N2B0 License and Supply-chain Review

Every candidate remains `RESEARCH_ONLY_DOWNLOAD_NOT_AUTHORIZED`. Code license and weights/checkpoint license are different evidence objects. Official MMPose, PaddleSeg, and MediaPipe repository records publish Apache-2.0 code licenses; neither fact authorizes a checkpoint. RTMPose-m, RTMW-m, and PP-HumanSegV2-Lite URLs are now recorded, but their exact weight terms, exact byte sizes, and SHA-256 values remain unverified. rtmlib and SAM 2 likewise require the exact artifact's official terms before an Owner decision.

The minimum future download allowlist is the exact official artifact host recorded in an Owner-approved N2B1 record; no redirect to an unlisted domain is allowed. `UNKNOWN`, `NOT_PUBLISHED`, or missing hash/license/immutable-revision fields fail closed. If an official SHA-256 is absent, N2B1 may only download into the external quarantine directory, calculate SHA-256 without loading, report it to Owner, and wait for a second approval before cache promotion.

Supply-chain verdict: `LICENSE_SUPPLY_CHAIN_CHANGES_REQUIRED`. No artifact has passed N2B1 eligibility.
