# N2B Owner Inputs Required

Before any model download or inference, Owner approval must identify each
artifact separately:

- exact model ID and immutable revision;
- exact filename, expected size, official URL, and SHA-256 procedure;
- code/checkpoint/training-data/commercial licenses;
- external cache destination and deletion/rollback policy;
- runtime/dependency/Docker/WSL requirements;
- approved 20-case benchmark manifest and human-review rubric;
- memory/latency/OOM stop thresholds;
- whether any derivative output may be retained.

Until these inputs and an independent review exist, N2B remains LOCKED and the
CLI must return `NPI_MODEL_NOT_AUTHORIZED` for execution.

The exact artifact identity, artifact hash, and checkpoint-license terms remain
blocking inputs. N2A remediation does not infer or fill any of them.

## Gate decision

`N2B_NOT_READY_FOR_OWNER_APPROVAL`

In addition to the listed Owner inputs, the future N2B approval must lock the
exact artifact filename/size and immutable revision, verified SHA-256, and
license/usage authority before any download. Real VRAM, latency, OOM, and
quality measurements have not been collected. This N2A remediation neither
downloads a model nor reads a real photo.

The exact N2A review target SHA is supplied externally after commit creation.
The report is bound to the immutable G1 parent SHA and current repository content.
