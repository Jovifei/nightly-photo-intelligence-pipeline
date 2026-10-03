# T14 Synthetic Contract Validation Handoff

Status: `SYNTHETIC_CONTRACT_TEST_ONLY`; `authority=false`; `ready_for_t14=false`.

## Scope

Offline PKB1 canonical serialization and bounded digest checks only. This helper
is separate from the legacy Photo Intelligence Bundle v1 contract. No pipeline,
model, database, service, release, schema, approval or gate state is changed.

`tools/pkb1_canonical.py` is the single implementation. The validation module
imports it, preserving both public function names. Canonical bytes start with
`PKB1\n`. Every field name and value is a separate UTF-8 byte-length token;
root reference IDs precede photography fields; reference array order is retained;
integrity metadata is excluded. No Unicode normalization is performed.

## Evidence boundary

`tests/fixtures/consumer_origin_synthetic_pkb1.json` is an exact-byte copy of the
App consumer fixture `docs/reference/fixtures/photo_knowledge_bundle_consumer.v1.json`.
Its independently frozen canonical digest is
`9bd85c8b1be3e3544d9a74b4140e59fc57f85e6b97a343d7c6fba2018048bb69`.
This consumer-origin synthetic contract regression fixture is NEVER producer
golden-vector evidence, production output, complete T14 compatibility or READY.

The serialization API expects a schema-validated mapping and checks required
string values/array shape. It does not implement the full consumer JSON Schema,
manifest/path/hash rules, asset validation, or producer provenance.

The CLI reads at most 512 KiB + 1 bytes, rejects invalid UTF-8/JSON, duplicate
object keys and non-finite constants, and checks the declared SHA-256 digest.
It emits a generic failure with exit 1 and no sensitive input content.

## Bounded verification

Run `python -m unittest discover -s tests -p 'test_pkb1*.py' -v`.
Tests load the actual frozen fixture and cover its digest, UTF-8 byte lengths,
root reference ID, field mutations, array order, object key order, integrity
exclusion, input limits, strict JSON failures, and CLI success/failure exits.
Run the CLI with `python tools/pkb1_contract_validation.py tests/fixtures/consumer_origin_synthetic_pkb1.json`.
No broad pipeline suite is part of this contract-only check.

## Final local verification (2026-10-03)

Parent reran8 focused tests after supporting uppercase declared hex. App-side25 intake and20 existing progress cases passed separately. N2B2/PROJECT_STATE/approvals/business schemas remain unchanged. This is proposed offline synthetic tooling only; consumer-origin fixture is not independent producer evidence. No T14 or release authority is granted.
