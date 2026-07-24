# N2B0.5 PaddleSeg PP-HumanSegV2-Lite rights and provenance

Status: `N2B0_5_RIGHTS_CLARIFICATION_BLOCKED`. Only official repository/model
page metadata and HTTP HEAD were used; no ZIP body was requested or saved.

## Official evidence

- Repository/revision: PaddleSeg `release/2.10`, Apache-2.0 `LICENSE`.
- The official PP-HumanSeg README lists the general PP-HumanSegV2-Lite
  192x192 model and links the exact inference ZIP used below.
- The README's phrase “zero cost” is product guidance, not a standalone
  checkpoint license or legal commercial-use authorization.

## HTTP HEAD-only observation (2026-07-24 UTC)

| artifact | status | redirects | final domain | Content-Length | Content-Type | ETag (not SHA-256) | Last-Modified |
|---|---:|---:|---|---:|---|---|---|
| `human_pp_humansegv2_lite_192x192_inference_model.zip` | 200 | 0 | `paddleseg.bj.bcebos.com` | 11349952 | `application/zip` | `1466d9f339d803f7fb74e777f65326a9` | 2022-07-19T12:46:49Z |

## Rights matrix

| field | PP-HumanSegV2-Lite |
|---|---|
| `CODE_LICENSE_CONFIRMED` | PASS |
| `WEIGHTS_LICENSE_CONFIRMED` | UNKNOWN |
| `COMMERCIAL_USE_CONFIRMED` | UNKNOWN |
| `ARTIFACT_IDENTITY_CONFIRMED` | PASS |
| `IMMUTABLE_REVISION_CONFIRMED` | UNKNOWN |
| `OFFICIAL_SIZE_CONFIRMED` | PASS (HEAD; README also reports 192x192 model) |
| `OFFICIAL_HASH_CONFIRMED` | UNKNOWN |
| `DOWNLOAD_DOMAIN_CONFIRMED` | PASS |
| `REDIRECT_CHAIN_CONFIRMED` | PASS (0) |
| `READY_FOR_QUARANTINE_DOWNLOAD` | FAIL |

The model page also describes a portrait 256x144 variant; it is not silently
substituted for the authorized 192x192 general-human candidate. No checkpoint
or inference-model terms, training-data rights, or SHA-256 are published in the
checked record. Commercial use therefore remains `UNKNOWN`.
