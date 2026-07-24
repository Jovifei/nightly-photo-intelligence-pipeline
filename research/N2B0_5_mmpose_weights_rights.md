# N2B0.5 MMPose checkpoint rights and provenance

Status: `N2B0_5_RIGHTS_CLARIFICATION_BLOCKED`. This is official-source,
metadata-only research. No checkpoint response body was requested or saved.

## Official evidence

- Code/repository: MMPose `v1.3.0`, Apache-2.0 `LICENSE`.
- RTMPose model index: `configs/wholebody_2d_keypoint/rtmpose/coco-wholebody/rtmpose_coco-wholebody.yml`.
- RTMW model index: `configs/wholebody_2d_keypoint/rtmpose/cocktail14/rtmw_cocktail14.yml`.
- Both model indexes publish the exact checkpoint URL and COCO-WholeBody training-data name.
- The publisher URL is a stable filename reference, not an immutable checkpoint revision.

## HTTP HEAD-only observations (2026-07-24 UTC)

| artifact | status | redirects | final domain | Content-Length | Content-Type | ETag (not SHA-256) | Last-Modified |
|---|---:|---:|---|---:|---|---|---|
| `rtmpose-m_simcc-coco-wholebody_pt-aic-coco_270e-256x192-cd5e845c_20230123.pth` | 200 | 0 | `download.openmmlab.com` | 72010049 | `application/octet-stream` | `F9E98931F38C2EF2ACFF811F479197A2` | 2023-04-18T06:29:48Z |
| `rtmw-dw-l-m_simcc-cocktail14_270e-256x192-20231122.pth` | 200 | 0 | `download.openmmlab.com` | 129787113 | `application/octet-stream` | `BB41BBD1B54EB9AAE47FD9DFC7A35BEB` | 2023-12-08T07:52:52Z |

HEAD metadata is not an artifact hash, signature, or license grant.

## Rights matrix

| field | RTMPose-m | RTMW-m fallback |
|---|---|---|
| `CODE_LICENSE_CONFIRMED` | PASS | PASS |
| `WEIGHTS_LICENSE_CONFIRMED` | UNKNOWN | UNKNOWN |
| `COMMERCIAL_USE_CONFIRMED` | UNKNOWN | UNKNOWN |
| `ARTIFACT_IDENTITY_CONFIRMED` | PASS | PASS |
| `IMMUTABLE_REVISION_CONFIRMED` | UNKNOWN | UNKNOWN |
| `OFFICIAL_SIZE_CONFIRMED` | PASS (HEAD) | PASS (HEAD) |
| `OFFICIAL_HASH_CONFIRMED` | UNKNOWN | UNKNOWN |
| `DOWNLOAD_DOMAIN_CONFIRMED` | PASS | PASS |
| `REDIRECT_CHAIN_CONFIRMED` | PASS (0) | PASS (0) |
| `READY_FOR_QUARANTINE_DOWNLOAD` | FAIL | FAIL |

Commercial conclusion is `UNKNOWN` and requires Owner/legal confirmation. The
COCO-WholeBody dataset name is provenance context, not a training-data license
or commercial-use grant. A future N2B1 request must obtain an explicit weight
license/usage statement, immutable revision or an Owner-approved publisher
exception, and a verified SHA-256 after quarantine download.
