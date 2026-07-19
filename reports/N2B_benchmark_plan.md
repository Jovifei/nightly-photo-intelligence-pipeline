# N2B Benchmark Plan (Locked)

N2B is not authorized. This plan is a future approval artifact, not execution
evidence.

The fixed 20-case matrix covers single-person body/half-body/seated, hands near
face, held object, occlusion, two people, small subject, crop/collage, mirror
and left/right ambiguity, backlight/window, hair/clothing/translucent edges,
out-of-frame, portrait/landscape orientation, and deterministic rerun.

Pose metrics: person detection, primary-person selection, keypoint availability,
left/right correctness, occlusion state, mirror consistency, and deterministic
angle error against human-reviewed references.

Segmentation metrics: primary-person selection, boundary quality, hair/clothing
edge errors, occlusion, leakage/holes, lightweight-to-escalation rate, and
deterministic rerun.

Resource metrics: cold/warm latency, peak GPU memory, peak CPU memory, OOM,
failure reason, and retry outcome. Unknown values remain `null` with
`NOT_MEASURED`; estimates are prohibited.

N2A remediation adds an executable synthetic-only validation path, but it does
not measure any of these resource metrics or authorize a model-backed run.

## N2B authorization status

`N2B_NOT_READY_FOR_OWNER_APPROVAL`

The remediation verifies only finite model-free metadata. Exact model revision,
artifact filename and size, checkpoint/license terms, SHA-256, real VRAM,
latency, OOM behavior, and real-model quality remain unmeasured and unresolved.
No model was downloaded or run, and no real photo was read.

The exact N2A review target SHA is supplied externally after commit creation.
The report is bound to the immutable G1 parent SHA and current repository content.
