# N2B0.7 RTX 4070 SUPER Artifact Decision Packet

Status: `N2B0_7_ARTIFACT_QUALIFICATION_BLOCKED`.

This is metadata-only N2B0.7 evidence. No wheel, model payload, model process,
real photo, cache, or quarantine directory was created or opened.

## Environment compatibility

Read-only inspection found Python 3.12.10 and an NVIDIA GeForce RTX 4070
SUPER with 12,282 MiB reported VRAM. The project environment does not contain
Torch. Official PyTorch package indexes list the planned Windows CPython 3.12
CUDA 12.8 wheel line, but no installation was attempted.

## Artifact results

| Role | Correct official artifact | Claimed size | Digest evidence | Rights result | Disposition |
|---|---|---:|---|---|---|
| Pose primary | KeypointRCNN `COCO_V1`, `...fc266e95.pth` | 226.054 MB | 8-hex SHA-256 prefix only | weights/commercial use unknown | BLOCKED |
| Segmentation primary | LRASPP MobileNetV3 Large, `...d234d4ea.pth` | 12.49 MB | 8-hex SHA-256 prefix only | weights/commercial use unknown | BLOCKED |
| Segmentation fallback | DeepLabV3 MobileNetV3 Large, `...fc3c493d.pth` | 42.301 MB | 8-hex SHA-256 prefix only | weights/commercial use unknown | BLOCKED |

The planned Pose pairing is internally inconsistent: TorchVision v0.22.1 maps
`COCO_V1` to `...fc266e95.pth`; `...9f466800.pth` is `COCO_LEGACY`, not
`COCO_V1`. The 8-hex filename tokens are declared as prefixes, never as full
SHA-256 values. A future local SHA-256 could bind a quarantined file but cannot
repair unknown weights rights or commercial permission.

## Rights conclusion

Torch/TorchVision code is BSD-3-Clause. That does not grant use rights for the
pretrained weights. TorchVision v0.22.1 metadata exposes these official URLs
but no distinct weights license or commercial-use grant. COCO/VOC-related
dataset terms likewise do not provide blanket commercial clearance for every
underlying image. Therefore the required separate weights and commercial
conclusions are `UNKNOWN`, which blocks N2B1.

The decision record links the exact official TorchVision v0.22.1 model-source
revision, the PyTorch model-host URLs, the TorchVision code license, and the
COCO/VOC terms. It records only the available filename SHA-256 *prefixes*;
it does not represent any prefix as a full published digest.

## Evidence pointers for the blocked rights result

The machine-readable record names the exact official model definitions,
category metadata, code license, PyTorch hash-prefix contract, and COCO/VOC
terms. The listed TorchVision v0.22.1 metadata has no separate pretrained
weights license or commercial-use grant; that absence is recorded as a scoped
inspection result, not as evidence that such permission exists elsewhere.

## Current-stage real-photo boundary remediation

The historical approved G1 record remains an immutable history fact. It is not
current N2B0.7 execution authority. `PROJECT_STATE.json` now explicitly binds
the active N2B0.7 capability to `source_photo_content_read=NOT_AUTHORIZED` and
`sqlite_ingest_write=NOT_AUTHORIZED`. The public permit, all public ingest
runners, `npi ingest`, and `npi resume` check this current-state boundary
before a source read-only probe, source enumeration/open, EXIF parsing,
manifest load, root validation, or state-database access. Synthetic-only
negative tests cover each denied path.

## Future N2B1 design, not authorization

If a later artifact is independently qualified and Owner-approved, its transfer
must use only the approved official domains; an exclusive quarantine file;
Content-Length and streaming digest checks; local full SHA-256 plus reread;
an atomic promotion into a hash-named cache entry; a cache manifest; and a
rollback that removes only that cache entry after reference checks. This design
is not implemented or exercised here.

## Owner options

1. **Keep blocked (recommended).** Retain N2B1/N2B2/N3 locked.
2. **Supply an explicit publisher weight/commercial grant and select the exact
   corrected Pose artifact.** N2B0.7 must then be requalified before any
   download approval is considered.
3. **Authorize a new, bounded alternative-artifact research phase.** It must
   establish official source, rights, commercial terms, revision, and hash
   policy before it can request N2B1.

Primary evidence is recorded in
`research/N2B0_7_torchvision_artifact_qualification.json`. No source photo
name, path, EXIF, GPS, identity, or image derivative appears in this packet.
