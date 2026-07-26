# N2B0.6 Lightweight Person-Segmentation Candidate Bundles

Status: metadata-only bundle review; the segmentation cap remains consumed at
2/2. No model payload body, model dependency, conversion, model execution,
cache/quarantine write, or photo read occurred.

| Candidate | Locked bundle | Static qualification |
|---|---|---|
| `instance-segmentation-person-0007` | FP16 OpenVINO IR XML + BIN, input `1x3x320x544`. XML is 3,975,487 B / SHA-384 `6e91ab4b808253a7a83fe9c94e4508743aabfeaa9bf850cf976d8c34ba0034dc78d81a4d7a475c53bc006fb90595d538`; BIN is 14,121,850 B / SHA-384 `26039d9fe430569662a0ea6b0810c31aa7f268309657b98c45eff09632f4b952ec61d4c85f8b68f3dc30decfb46edc39`. | Closed static IR pair passes bundle, licence, revision, SHA-384, size, direct-domain, zero-redirect, and local-relative-path checks. Official SHA-256 remains FAIL; readiness FAIL. |
| `modnet-webcam-portrait-matting` | Source-and-conversion bundle: checkpoint `modnet_webcam_portrait_matting.ckpt`, 26,255,603 B / SHA-384 `fab9c2ee2995642e21656a3180e75c9a73d3442a2500e5f0e0a08e14bfe9c4640fccf7c055162ff039f4dd066102652c`; fixed OMZ `model.py`, fixed OMZ conversion script, and fixed MODNet `modnet_onnx.py` plus all three imported `src/models/backbones` files. | The static source/recipe closure is recorded and validates. Expected ONNX and IR outputs are explicitly `NOT_GENERATED`; converter runtime is `NOT_INSTALLED_NOT_VERIFIED`. No official SHA-256 exists for the checkpoint, so readiness FAIL. |

The MODNet conversion record uses OMZ commit
`7cc29a91472b4cb1289a11e655ba3e188e1d4a31` and original MODNet commit
`2938675e4b5c60ab5f5d7a2b2191c68256f99d70`. It records the model YAML command
contract, config and converter identity, exact source-file identities, and
the three ungenerated output names without inventing output sizes, hashes, or
performance.

For both payloads, HEAD observed HTTP 200, a direct zero-redirect official
storage URL, exact Content-Length, Content-Type, ETag, Last-Modified, and
`Accept-Ranges: bytes`. Those observations and all direct URLs are stored per
file in `research/N2B0_6_candidate_records.json`; ETags are not checksums.

Apache-2.0 code/model licence and commercial-use evidence is pinned separately
for OMZ and, for MODNet, the original source. Neither candidate is a runtime
qualification, and no future mask adapter, threshold, conversion, or output
was produced.
