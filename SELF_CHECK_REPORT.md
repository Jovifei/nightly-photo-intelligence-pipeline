# Handoff Self-Check Report

- Command: `python tools/verify_handoff.py`
- Result: `PASS`
- Scope: delivery package integrity, authorization, fixtures, JSON/YAML syntax,
  examples, App fixture checksums, sensitive/large-file scan, local links, manifest.
- Note: this validates the handoff package; it does not claim N0 implementation or hardware capability.

```text
NPI handoff verification
========================
PASS: required files exist
PASS: only N0/G0 is authorized
PASS: N1-N8 task files are locked
PASS: approval templates are not approvals
PASS: three synthetic fixtures and duplicate relation verified
PASS: all JSON files parse
PASS: all YAML files parse
PASS: valid item passes core rules
PASS: invalid examples fail expected core rules
PASS: valid item passes Draft 2020-12 validation
PASS: invalid items are rejected by Draft 2020-12 validation
PASS: App fixture bundle checksums verified
PASS: no unexpected large files
PASS: no private keys or likely personal home paths detected
PASS: local Markdown links resolve
PASS: MANIFEST.sha256 verifies all package files
Summary: 16 pass, 0 warn, 0 fail
HANDOFF_VALID: N0/G0 only; all later phases remain locked
```
