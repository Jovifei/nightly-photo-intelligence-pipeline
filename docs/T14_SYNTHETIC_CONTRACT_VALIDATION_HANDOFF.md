# T14 Synthetic Contract Validation Handoff

Status: SYNTHETIC_CONTRACT_TEST_ONLY

This branch provides offline Bundle contract validation preparation only.

## Allowed

- PKB1 canonical JSON byte generation
- checksum verification preparation
- schema shape rejection tests
- manifest/path/hash validation helpers

## Forbidden

- producer golden vector claims
- real photo analysis
- model inference
- live service calls
- T14 compatibility approval
- READY promotion

## Current boundary

The App and Pipeline exchange only through Photo Intelligence Bundle v1.
A successful synthetic validation result means only that the contract tooling agrees with the bundle structure.
It is not evidence of production output quality or producer compatibility.
