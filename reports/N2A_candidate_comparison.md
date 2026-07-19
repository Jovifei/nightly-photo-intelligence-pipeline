# N2A Candidate Comparison

| Candidate | Role | Strength | Risk / unresolved | N2A status |
|---|---|---|---|---|
| MMPose RTMPose/RTMW | pose | broad body/hand/face/whole-body ecosystem | framework and checkpoint terms; exact revision and VRAM pending | research only |
| rtmlib | pose | lightweight wrapper around RTMPose-family models | artifact and runtime compatibility pending | research only |
| MediaPipe Selfie Segmentation | segmentation baseline | small documented tensor sizes and real-time orientation | close prominent-human scope; hair/multi-person/small-subject risk | conditional research only |
| PaddleSeg PP-HumanSeg | segmentation | human segmentation candidates and lightweight options | exact model artifact/license/runtime pending | research only |
| SAM 2 | fine segmentation escalation | prompted fine-detail possibility | checkpoint/license/dependency and memory review required | escalation only |

No candidate was downloaded, benchmarked, or recommended for production. VRAM,
latency, OOM, and quality are explicitly not measured.

The N2A fake-harness result does not select any candidate or close these gaps.

## Current authorization boundary

Finite-number, BBox, taxonomy, and measurement remediation changes only the
model-free N2A contract harness. It does not select a candidate, download an
artifact, inspect a real photo, or create an inference result.

The exact N2A review target SHA is supplied externally after commit creation.
The report is bound to the immutable G1 parent SHA and current repository content.
