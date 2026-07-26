# N2B0.6 License and Commercial Review

This review separates code license from Artifact/weight license. It never
infers a weight grant solely from a repository-level code license. The current
record binds each PASS to typed immutable evidence IDs, an exact source project
and revision, the current candidate bundle, and every declared payload file.

| Candidate group | Code license at immutable revision | Explicit Artifact/weight coverage | Commercial internal benchmark, cache, and derived results | Result |
|---|---|---|---|---|
| Intel OMZ pose 0001 / 0005 | Typed `CODE_LICENSE` evidence at the pinned OMZ commit. | PASS only through a typed `MODEL_LICENSE` decision whose immutable evidence applies to the complete declared payload bundle. | PASS only through a decision citing both model-license and commercial-terms evidence, with notice/license obligations retained. | Still not ready: official SHA-256 is absent. |
| Intel OMZ person 0007 | Same typed pinned OMZ code-license evidence. | Same typed model-license and payload applicability binding. | Same typed commercial-terms and model-license binding. | Still not ready: official SHA-256 is absent. |
| Intel OMZ MODNet portrait matting | Typed immutable OMZ and original MODNet code-license evidence. | PASS only through the pinned original-MODNet `MODEL_LICENSE` evidence that applies to the candidate checkpoint bundle. | PASS only through the model-license plus pinned commercial-terms evidence. | Still not ready: official SHA-256 is absent. |

No candidate is marked `UNKNOWN` for code/weight license or commercial use.
No performance, VRAM, accuracy, training-data, or legal advice claim is made:
those are `NOT_MEASURED` or `NOT_VERIFIED` unless an official Artifact term
explicitly states them. The hard `OFFICIAL_SHA256_CONFIRMED=FAIL` result blocks
all four records before any Owner Artifact selection. The MODNet static
source-and-conversion closure makes its evidence record complete; it does not
assert that an uninstalled converter or `NOT_GENERATED` output has succeeded.
