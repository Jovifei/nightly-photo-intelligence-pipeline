# N2B2 Benchmark Execution Plan (locked)

N2B2 is not authorized. This plan remains metadata-only and creates no model
output.

## Future benchmark shape

- First run the three existing synthetic smoke fixtures with one approved model
  at a time and retain no skeleton, mask, cutout, or image derivative.
- Then, only after a separate N2B2 approval, run the Owner-frozen 20-case G1
  benchmark serially with source SHA pre/post checks and redacted metrics.
- Record model revision, artifact SHA-256, runtime versions, input shape,
  latency, peak memory/VRAM, OOM/failure causes, and quality rubric results.
- Stop on hash mismatch, unauthorized artifact, path escape, OOM threshold,
  unsupported runtime, or any attempt to access an unapproved photo.

No real photo, model, or model dependency was accessed during N2B0.5.
