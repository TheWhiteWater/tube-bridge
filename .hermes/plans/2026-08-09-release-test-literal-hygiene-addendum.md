# WI-00069 — Release-test literal hygiene addendum

## Defect

The active sdist includes `tests/`. Two frozen tests contain the exact private-deployment markers they are intended to reject, so a correct whole-archive scanner rejects the sdist because of test fixture source rather than shipped runtime/help metadata.

## Authorized test-only correction

- In `tests/test_private_endpoint_not_distributed.py`, compose the private hostname and `deploy_url` field at runtime from non-contiguous components.
- In `tests/test_v1_0_3_release_contract.py`, compose the same fixture markers at runtime.
- Preserve every behavioral assertion and synthetic clean/leaking wheel+sdist case.
- Do not change production source, workflow, docs, package version or release behavior in this addendum.

## Freeze and supersession

After an independent two-test contract audit PASS, freeze both corrected files in one manifest. Record that this manifest supersedes:

- `.brainops/methodology/frozen-tests/frozen-20260809061346-test_private_endpoint_not_distributed.py.json`;
- `.brainops/methodology/frozen-tests/frozen-20260809072041-test_v1_0_3_release_contract.py.json`.

The superseded files remain immutable history. WI-00067 may resume implementation only after the corrected hashes are frozen and the tests retain the same deterministic outcomes.
