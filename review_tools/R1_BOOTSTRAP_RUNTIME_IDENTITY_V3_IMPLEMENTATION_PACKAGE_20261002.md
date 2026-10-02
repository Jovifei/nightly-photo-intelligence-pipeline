# R1 Bootstrap Runtime Identity v3 Implementation Package

Status: CODE-ONLY IMPLEMENTATION PACKAGE (NOT EXECUTION AUTHORIZATION)
Base: 8bffaac5fad6d0de4e596943d709448ac40546de

## Boundary

This package prepares R1 Real20 admission infrastructure only. It does not authorize Real20 execution, photo reads, EXIF reads, model execution, CUDA, SQLite writes, or production state transition.

R0 resource gates remain independent and OPEN.

## Selected architecture

The selected route is:

trusted runtime configuration
→ reviewed bootstrap contract
→ Codex bootstrap implementation
→ runtime identity v3
→ cleanup_capability
→ restricted cleanup helper
→ pre-open cleanup handle inheritance
→ synthetic probe proof
→ cleanup proof
→ Real20 admission eligibility

No second Windows account is required by this route.

## Runtime identity v3 contract

Top-level control object:

- schema_version: exact v3 identifier
- runtime_observation: existing runtime observation domain
- ledger_acl_probe: proof domain
- cleanup_capability: restricted cleanup authorization domain

The domains remain separated:

- runtime observation describes runtime facts;
- ledger proof describes synthetic inheritance evidence;
- cleanup capability describes only bounded cleanup authority.

A change in any bound domain invalidates the candidate identity digest.

## Bootstrap contract

Bootstrap is a separate reviewed capability. This document does not authorize execution.

Bootstrap must:

1. consume only trusted runtime configuration;
2. derive ledger/probe locations from approved configuration;
3. create only synthetic probe resources;
4. never read photo sources;
5. never modify production ledger ACLs;
6. never create real reservation/lease state;
7. emit candidate-bound proof artifacts only.

## Cleanup helper qualification

The helper is restricted by capability, not by a broad account model.

Required properties:

- receives pre-opened cleanup handle only;
- receives nonce-bound object identity;
- cannot recursively search paths;
- cannot access source/cache/output/real ledger;
- cannot widen ACLs;
- cannot repair failed security policy.

## Admission ordering

Required order:

1. Validate contract version.
2. Validate runtime identity binding.
3. Validate ledger/probe proof.
4. Validate cleanup proof.
5. Validate live runtime attestation.
6. Validate remaining phase/data gates.
7. Only then allow future Real20 reservation path.

Failure before reservation must result in zero reservation consumption.

## Required code/test package

Future implementation should add:

- bootstrap contract schema;
- runtime identity v3 schema validator;
- cleanup_capability validator;
- restricted helper interface;
- synthetic probe proof verifier;
- negative tests for missing/expired/mismatched proofs.

Required tests:

- missing proof rejects before reservation;
- expired proof rejects before reservation;
- altered cleanup capability rejects;
- altered runtime observation invalidates digest;
- altered ledger proof invalidates digest;
- helper cannot escape pre-opened handle boundary.

## NOT RUN

No local Windows ACL execution.
No probe creation.
No cleanup helper execution.
No Real20 execution.
No model/photo/EXIF/SQLite execution.
