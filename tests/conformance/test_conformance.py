"""The conformance test: run every discovered case through the validator and
compare the produced error codes against the case's expected outcome.

Each case is a separate parametrized test so failures point at a single fixture.

While the validator is unimplemented, ``validate`` raises ``NotImplementedError``
and cases are reported as ``xfail`` ("pending implementation"). Set the env var
``OFPLANG_STRICT_TESTS=1`` to turn that escape hatch off so a finished validator
is held to the full contract (and any remaining ``NotImplementedError`` fails).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ofplang import validate
from tests.conformance.cases import (
    INVALID,
    MATCH_EXACT,
    VALID,
    Case,
    discover_cases,
)

CASES_ROOT = Path(__file__).parent / "cases"
_STRICT = os.environ.get("OFPLANG_STRICT_TESTS") == "1"

_CASES = discover_cases(CASES_ROOT) if CASES_ROOT.exists() else []


def _run(case: Case):
    try:
        return validate(case.root_doc, mode=case.mode)
    except NotImplementedError:
        if _STRICT:
            raise
        pytest.xfail("validator not implemented yet")


def _assert_outcome(case: Case, result) -> None:
    produced = set(result.codes)
    expected = set(case.expected_codes)

    if case.outcome == VALID:
        assert result.ok, (
            f"expected valid, got errors {sorted(produced)}"
            + (f"\nnote: {case.notes}" if case.notes else "")
        )
        return

    # INVALID
    assert not result.ok, "expected validation errors, got none"
    if case.match == MATCH_EXACT:
        assert produced == expected, (
            f"error code set mismatch\n  expected: {sorted(expected)}\n"
            f"  produced: {sorted(produced)}"
            + (f"\nnote: {case.notes}" if case.notes else "")
        )
    else:  # superset
        missing = expected - produced
        assert not missing, (
            f"missing expected error codes: {sorted(missing)}\n"
            f"  produced: {sorted(produced)}"
        )


@pytest.mark.parametrize("case", _CASES, ids=lambda c: c.id)
def test_conformance(case: Case) -> None:
    result = _run(case)
    _assert_outcome(case, result)


def test_at_least_one_case_discovered() -> None:
    assert _CASES, f"no conformance cases found under {CASES_ROOT}"
