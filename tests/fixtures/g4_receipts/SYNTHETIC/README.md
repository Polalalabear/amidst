# CQ-21-T SYNTHETIC fixtures

Only artificial JSON/schema examples. No original assets, RGB, GT, routes, human
returns, private paths, or actual G4 approval. `example.invalid` references and
`SYNTHETIC_UNSELECTED_PURPOSE` are test placeholders, never production authority.
The graph has three cameras, one same-region zero-edge transition, one nonzero
transition, DRAFT graph declarations and a PROPOSED/G4=false tracking scope.

Six receipt cases are fixed here: `approved`, `pending`, `decisions_tampered`,
`registry_pin_mismatch`, `draft`, `missing_field`. "Approved" means a synthetic
header/decision example only. In particular it does not establish B1 graph/scope
gates or choose the B3 vocabulary. All derived legal transition lists are empty.
Each `registry_*.json` is only the existing `documents` pin fragment for the
offline checker, not a complete API registry or a choice of CQ-21a A2.

The checker validates #260@d560f224be0f93cf62076f5ae2fa78b0ae957d15's PROPOSED
five-key preimage, explicit bytes pins and bounded structural types. It always
reports `authority_verified=false`, never loads graphs, never applies an overlay,
never fetches a reference and never authenticates human approval. Draft or
nonapproved headers are negative checker inputs. Unknown proposed gate fields
and next-version receipt formats fail closed; adopting #308's new gate table
requires a later checker/fixture revision, not silently extending this preimage.

Generate and inspect using the existing uv environment:

```sh
uv run python tests/fixtures/g4_receipts/SYNTHETIC/build_fixtures.py
uv run python scripts/check_g4_receipt.py \
  --receipt tests/fixtures/g4_receipts/SYNTHETIC/receipt_approved.json \
  --registry tests/fixtures/g4_receipts/SYNTHETIC/registry_approved.json
uv run python -m pytest -q tests/q1q5/test_g4_receipt_overlay.py
```

`MANIFEST.json` pins the JSON bytes and independent builder's golden decision
hash. Rebuilding these synthetic files changes no source assets or runtime state.

## Future implementation acceptance

The production adapter/function signature is not defined yet (CQ-21a C1). Tests
use an external **TEST-ONLY** Python driver with `exercise_case(case_name,
inputs=..., contract_options=...)`. This is not a proposed product API. The driver
must invoke the real selected implementation, inject a registry-replacement
hook for the reload case, and report observations. It must not fabricate expected
fixture answers. It must consume explicit selected-contract receipt bytes after
U8; it must never upgrade this five-key fixture into a new gate/schema version.

Set `AMIDST_G4_OVERLAY_DRIVER` to that test driver module. With no driver, tests
use `pytest.importorskip`; `AMIDST_REQUIRE_IMPL=1` converts missing implementation
or unbound driver into a failure. No local replacement adapter is supplied to
turn those tests green.

`AMIDST_RECEIPT_CONTRACT` is an explicit JSON object or file path. Its group IDs
match #308's PROPOSED option table; there is no default recommendation. Before
U8, keep every group UNSELECTED. The test-only IDs are cross-checked against
[#351@03b369a519c8a81ffe9e5a3136d6a6ab0eb56bd3](https://github.com/Polalalabear/amidst/pull/351)
(`Q1Q5_G4_RECEIPT_BINDING_PROPOSAL_20261029.md` SHA-256
`162a3f6a3ee1fae23e1c5c2dac1e4dbd201de6f141d5fadb7ece17167aefaf30`).
This is a PROPOSED reference, not an implementation dependency or U8 adoption.
`contract_options.UNSELECTED.json` is the explicit fail-closed template, including
unset C2 paths and an empty selected-contract case map. C3 alternatives carry
`contract_option("C3", "PINNED_FAIL_CLOSED")` and
`contract_option("C3", "LEGACY_READ_ONLY_NO_OVERLAY")` markers. Once a choice is
explicitly supplied, collection deselects the other alternative for this file
only. Both options forbid restoring live authority without a receipt; the latter
only displays unchanged old bytes with a nonempty downgrade marker.

The `_test` object is harness configuration only, never receipt/registry wire:
`C2_provenance_paths` must supply nonempty string arrays named
`response_file_sha256`, `response_decisions_sha256`, `journal_file_sha256`, and
`journal_decisions_sha256`. Response paths are relative to the driver's actual
session observation; journal paths are relative to each actual journal row.
The driver is responsible for exposing bounded pinned external provenance when
that alternative is selected. Missing paths fail in strict mode, so tests do
not invent or adopt production field names.

Runtime receipt cases also require `_test.selected_contract_cases[case_name]`.
Each case is an explicit test-only object with `fixture_role: SYNTHETIC_ONLY` and
a nonempty `receipts` array. Each receipt provides `raw_utf8` (the exact chosen
wire bytes as a JSON string), its `file_sha256`, approved-content
`decisions_sha256`, and the matching `registry_fragment` for that chosen contract.
The harness checks exact bytes/pins and never runs its old five-key projection on
next-version wire. The named case keys are visible at the `selected_case=` calls
in the tests. C2 cases need two receipts with different approved-content hashes.
Missing selected fixtures skip normally and fail under `AMIDST_REQUIRE_IMPL=1`;
they are intentionally absent before U8. Five-key fixtures remain checker and
negative-format examples. New-version success must not be faked by resealing or
promoting those v1 bytes.

The test driver returns observations used by the named tests, including the
actual candidate snapshot, error code, whether an overlay/authority was published,
unchanged graph bytes/hash maps, sessions with actual response/journal artifacts,
and unchanged replay bytes. The test-only `published_snapshots=[]` observation
means no partially verified effective view was published after an error.
Selected decision-mutation cases must supply matching synthetic bytes/registry
pins; they must not fail only because an old registry pinned other bytes. The positive control
must exercise a genuinely fully bound selected contract and admit the nonzero
camera C. Unresolved-decision cases must show that control C was legal and becomes
excluded after the mutation; an adapter that rejects everything cannot pass.
Unaffected transitions need not be rejected with the unresolved one. These are
synthetic acceptance requirements, not permission to add new production wire
fields before U8.

The C1 negative case is specifically **bytes of the same already pinned
generation changed during reload**. Both C1 alternatives must reject that stale
pin before publication. A valid atomic switch to a separate fully pinned new
generation is a different case: it may affect new sessions while an immutable
old session continues with its original pins. This test does not require that
legal atomic generation switch to raise an error.

After implementation and U8 option binding:

```sh
AMIDST_REQUIRE_IMPL=1 AMIDST_RECEIPT_CONTRACT=<CQ-21a 核定後的選項 JSON> \
  uv run python -m pytest -q tests/q1q5/test_g4_receipt_overlay.py
python scripts/check_g4_receipt.py --receipt <收據> --registry <registry>
```

The second command is preserved verbatim from #309; operational Python commands
in this repository use `uv run python` with the same arguments. A strict red run
while the implementation is absent is evidence that acceptance remains pending,
not a completed overlay implementation or a G4 acceptance.
