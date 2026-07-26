# N2B0.6 Official Artifact and Bundle Identity Review

Evidence collection was limited to official source text/API metadata and HTTP
HEAD. Model payload GET/Range bytes, local cache writes, extraction, loading,
conversion, and execution were all 0.

The closed v2 candidate record is the authoritative per-file evidence:
`research/N2B0_6_candidate_records.json`, validated by
`schemas/n2b0_6_candidate_record_v2.schema.json`. It records, for each of the
seven model payload files, the direct HTTPS target, request/final host, zero
redirect expectation and observation, HTTP 200, Content-Length, Content-Type,
ETag, Last-Modified, `Accept-Ranges`, exact SHA-384, safe local-relative bundle
path, and typed source/checksum/model-license evidence IDs. The validator
requires filename equality with canonical direct/final URL basenames, fixed
candidate-specific OMZ `model.yml` bindings, and exact checksum assertions.

| Bundle | Required payload files | Identity conclusion |
|---|---|---|
| Pose 0001 | FP32 XML + FP32 BIN | Complete direct official IR pair; no precision mixing. |
| Pose 0005 | FP32 XML + FP32 BIN | Complete direct official IR pair; no precision mixing. |
| Person 0007 | FP16 XML + FP16 BIN | Complete direct official IR pair; no precision mixing. |
| MODNet | Pinned checkpoint plus source-and-conversion closure | Checkpoint direct identity is complete; source/config/converter identities are fixed separately and are never represented as payload hashes. |

Each selected payload has official SHA-384 from the pinned OMZ model
configuration. SHA-384 is recorded as independent payload identity evidence;
it is not relabelled as SHA-256. No official lower-case SHA-256 was found for
any required payload file. Therefore all four candidates have
`OFFICIAL_SHA256_CONFIRMED=FAIL` and
`ready_for_owner_artifact_selection=FAIL`.

The MODNet static recipe lists its checkpoint, `model.py`, conversion tool
script, `modnet_onnx.py`, and the three imported backbone files. Its possible
ONNX/XML/BIN outputs are `NOT_GENERATED`, with no made-up final hashes, sizes,
or runtime result. This is a complete metadata record, not a converted model.
