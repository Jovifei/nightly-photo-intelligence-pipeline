# N2B0.5 MediaPipe Selfie Segmentation artifact identity

Status: `N2B0_5_RIGHTS_CLARIFICATION_BLOCKED`. The official legacy model index
now exposes exact filenames and storage URLs, but it does not close model-card
rights or an immutable revision. No TFLite body was requested or saved.

## Official identity

The official MediaPipe model-card index links:

- general: `selfie_segmentation.tflite`
  (`https://storage.googleapis.com/mediapipe-assets/selfie_segmentation.tflite`)
- landscape: `selfie_segmentation_landscape.tflite`
  (`https://storage.googleapis.com/mediapipe-assets/selfie_segmentation_landscape.tflite`)

The selected fallback record is the general model. The official Selfie
Segmentation page describes prominent-human/selfie use, 256x256 general input,
and 144x256 landscape input; it does not claim general multi-person photo
coverage.

## HTTP HEAD-only observations (2026-07-24 UTC)

| artifact | status | redirects | final domain | Content-Length | Content-Type | ETag (not SHA-256) | Last-Modified |
|---|---:|---:|---|---:|---|---|---|
| `selfie_segmentation.tflite` | 200 | 0 | `storage.googleapis.com` | 249505 | `application/octet-stream` | `16db9d4b2d1b11a174af22cb5040817a` | 2023-05-06T00:22:43Z |
| `selfie_segmentation_landscape.tflite` (not selected) | 200 | 0 | `storage.googleapis.com` | 250145 | `application/octet-stream` | `7ed7c3b64299722cb31c20008509fba6` | 2023-05-06T00:22:41Z |

## Rights matrix (selected general fallback)

| field | MediaPipe Selfie Segmentation general |
|---|---|
| `CODE_LICENSE_CONFIRMED` | PASS (repository Apache-2.0) |
| `WEIGHTS_LICENSE_CONFIRMED` | UNKNOWN (model card not a weight license) |
| `COMMERCIAL_USE_CONFIRMED` | UNKNOWN |
| `ARTIFACT_IDENTITY_CONFIRMED` | PASS |
| `IMMUTABLE_REVISION_CONFIRMED` | UNKNOWN |
| `OFFICIAL_SIZE_CONFIRMED` | PASS (HEAD) |
| `OFFICIAL_HASH_CONFIRMED` | UNKNOWN |
| `DOWNLOAD_DOMAIN_CONFIRMED` | PASS (official model index link) |
| `REDIRECT_CHAIN_CONFIRMED` | PASS (0) |
| `READY_FOR_QUARANTINE_DOWNLOAD` | FAIL |

The model-card link is hosted through `mediapipe.page.link` and resolves to a
Google Drive preview; its terms were not treated as confirmed without a
machine-verifiable weight-license statement. Landscape remains an unselected
alternative, not an additional authorized artifact.
