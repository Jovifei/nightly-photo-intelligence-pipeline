# N2B0.6 Pose Alternative Candidate Bundles

Status: metadata-only bundle review; the Pose cap remains consumed at 2/2.
No model payload body or Range response was requested, saved, installed, or
executed, and no photo was read.

The fixed official Open Model Zoo revision is
`7cc29a91472b4cb1289a11e655ba3e188e1d4a31`. Each candidate is a closed,
preconverted OpenVINO IR bundle: its selected precision, XML graph, and BIN
weights must stay together. The complete direct URLs, canonical SHA-384
values, local-relative placeholders, and full per-file HEAD observations are
versioned in `research/N2B0_6_candidate_records.json`.

| Candidate | Locked bundle | Official payload identity | Static qualification |
|---|---|---|---|
| `human-pose-estimation-0001` | FP32 IR: XML + BIN; input `1x3x256x456` | XML: 152,120 B, SHA-384 `64e24ceca496aba4fb818edbea7c3a1405bc42c3166eac1b4be4f6cc89623c80cb9a1fd4c32d245d423653aa588e1a0b`; BIN: 16,394,708 B, SHA-384 `64ef06d261ae522409172a396d927f7345525dbde011e3e2bff487f73e7b1d8cf622091feba9c23c7d4625c0aab0a3e5` | All required bundle, licence, immutable-revision, SHA-384, size, direct-domain, zero-redirect, and local-relative-path checks PASS. Official SHA-256 FAIL; final readiness FAIL. |
| `human-pose-estimation-0005` | FP32 IR: XML + BIN; input `1x3x288x288` | XML: 849,150 B, SHA-384 `b0735a220aff32a5c885b0b2e311b8dae21584edf06356246c7ad0634fb8b3a2ddf488097b5288252025dee487d029f0`; BIN: 32,601,720 B, SHA-384 `5711b763909990db35f20ce3dc82710001d030ea600ae81b8187d908d9f751ded6dd9bdbbdc2182225dc79cac92ffb1d` | Same result: static bundle record complete, but no official SHA-256; final readiness FAIL. |

The model configuration binds the versioned `2023.0/models_bin/1` storage
mapping. For each selected payload, HEAD observed HTTP 200, direct final URL,
zero redirects, `storage.openvinotoolkit.org` as request/final domain, exact
Content-Length, content type, ETag, Last-Modified, and `Accept-Ranges: bytes`.
ETag and transport headers are retained only as transport observations.

Code, model/weight licence, and commercial-use evidence is Apache-2.0 at the
pinned official sources. That rights conclusion does not replace the frozen
official-SHA-256 rule. The runtime and both decoders are `NOT_INSTALLED`; no
performance, compatibility, or quality result is claimed.
