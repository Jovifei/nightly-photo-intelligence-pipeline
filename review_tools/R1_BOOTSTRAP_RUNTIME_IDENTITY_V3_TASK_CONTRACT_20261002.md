# R1 Bootstrap Runtime Identity v3 Task Contract

State: PLANNING CONTRACT ONLY

## Entry gate

Requires a separate Owner-approved transition from N2B1P toward Real20 admission preparation.

This contract does not change PROJECT_STATE authorization.

## Scope

Allowed code-only scope:

- schema definitions;
- validators;
- proof verification logic;
- synthetic fixture tests;
- admission ordering tests.

Not allowed:

- creating Windows users;
- changing ACLs;
- creating production ledger;
- consuming Real20 credentials;
- opening photos;
- loading models;
- CUDA execution;
- SQLite production writes.

## Evidence chain

Required before Real20 admission:

runtime configuration
+
bootstrap review
+
runtime identity v3 binding
+
ledger/probe proof
+
cleanup_capability proof
+
live attestation

## Acceptance

Code acceptance:

- exact SHA review;
- schema tests;
- negative security tests;
- manifest/handoff update.

Execution acceptance:

separate local Windows validation after required resources exist.

## Resource decisions owned by Jovi

- whether and when to authorize bootstrap execution;
- runtime parent/probe resource availability;
- cleanup capability provisioning;
- Real20 transition timing.

Agent must not infer these decisions.
