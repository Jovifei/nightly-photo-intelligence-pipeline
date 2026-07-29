# N2B1R Local-Research Acquisition Report

## Result

`N2B1R_ACQUISITION_COMPLETE_AWAITING_LOCAL_VERIFICATION`

Three exact register-bound TorchVision checkpoint payloads were acquired from
`download.pytorch.org` into the approved external quarantine. The quarantine
parent was verified non-reparse. Each transfer used HEAD before GET, an Owner
byte cap, exclusive create, streaming SHA-256, post-write reread, and a
path-redacted transfer manifest.

| Artifact ID | Bytes | Local SHA-256 | Transfer-manifest SHA-256 |
|---|---:|---|---|
| `torchvision-lraspp-mobilenet-v3-large-coco-voc-v1` | 13,097,061 | `d234d4eae9d55d5f76de18b77cf0dc62c66fe5c5482758209d00f950c92bb280` | `d25cc430637cf19ebab31cd5aa99e344b4da58cd2b04db245c165181e3ff1f12` |
| `torchvision-deeplabv3-mobilenet-v3-large-coco-voc-v1` | 44,356,159 | `fc3c493d68e89cc31ef488c803d5d7dd2f3190fb570598faa49fef69be8e5e70` | `676054e8b2c366f591a1bbe1b4521e2ef7abdb08197534ca95eb11d434dd0cae` |
| `torchvision-keypointrcnn-resnet50-fpn-coco-v1` | 237,034,793 | `fc266e953d2b302cdcbb9ae66f71f6b0d4649928bf02dc573961e361e4918926` | `90da3eb000813841a980dcbaf8e1b31fdde15283a9d6b969156c5eb0ae21ce43` |

The filename SHA-256 prefixes match the locally calculated SHA-256 values. A
prefix is only an identity cross-check; it is not represented as a complete
official digest or a license grant.

## Rights and privacy boundary

All three payloads remain `UNKNOWN_NOT_COMMERCIAL_CLEARANCE` and restricted to
`LOCAL_RESEARCH_ONLY_NO_REDISTRIBUTION`. The report intentionally contains no
quarantine path, source-photo path, original image, image derivative, EXIF,
location, identity, Base64 payload, or cache path.

## Not performed

- Cache promotion, dependency installation, model loading, CUDA execution, and inference.
- Source-photo or EXIF reads, SQLite ingest writes, and derivative-image output.
- Cloud processing, Docker/WSL/driver changes, push, merge, or release.

## Required stop

The active N2B1R task requires a stop after acquisition evidence. N2B1P is not
an active capability, and its continuation condition currently mentions cache
promotion verification even though N2B1R forbids cache promotion. A separate,
non-circular N2B1P authorization/contract is required before creating the
isolated GPU environment, promoting a cache copy, loading any model, or
advancing toward the protected 20-photo benchmark.
