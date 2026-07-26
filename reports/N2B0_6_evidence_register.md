# N2B0.6 Bundle Evidence Register

All entries are metadata-only evidence. No model payload body or real photo was
opened.

| Evidence class | Fixed official evidence | What it proves | What it does not prove |
|---|---|---|---|
| Candidate schema and semantic validator | Closed v2 record and always-on per-file validator | Typed evidence, URL/filename binding, fixed model configuration revision/path, source/checksum/license cross-references, and matrix recomputation are present even when final readiness is FAIL | Download, install, conversion, execution, or phase authorization |
| OMZ model configuration | Commit `7cc29a91472b4cb1289a11e655ba3e188e1d4a31`, exact `models/intel|public/<model-id>/model.yml` path | Candidate-specific model configuration binding and checksum-metadata source identity | Official SHA-256 or payload bytes |
| Official payload HEAD | HTTP 200/direct final URL/zero redirects/Content-Length/Content-Type/ETag/Last-Modified/Accept-Ranges per required payload | Bounded transport metadata and size observation | Payload content hash, licence, or a saved artifact |
| MODNet fixed source closure | OMZ commit plus MODNet commit `2938675e4b5c60ab5f5d7a2b2191c68256f99d70` | Pinned config, converter, imports, and expected ungenerated outputs | A generated ONNX/IR artifact or runtime compatibility |
| Licence evidence | Typed immutable `CODE_LICENSE`, `MODEL_LICENSE`, and `COMMERCIAL_USE_TERMS` records | Separate code, model/weight, and commercial-use PASS decisions with required evidence IDs covering the candidate bundle and its declared payloads | Legal advice or runtime qualification |

All candidates are structurally complete research records. Their common final
gate is the frozen policy: each required payload lacks an official SHA-256, so
all readiness values remain FAIL. For MODNet, the uninstalled converter runtime
and `NOT_GENERATED` outputs are separately visible and are not described as a
successful conversion.
