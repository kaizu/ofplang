"""ofplang v0 validator -- public API contract.

The implementation is intentionally a stub for now: the conformance test suite
is authored first (test-driven development) and defines the behavioral contract
that the real validator must satisfy.

The stable API surface the tests depend on is:

    validate(source, *, mode="strict", base_dir=None) -> ValidationResult

where ``source`` is a path to the root document (a ``.yaml`` file). The
returned :class:`ValidationResult` exposes ``ok`` and ``diagnostics``. Each
:class:`Diagnostic` carries a ``code`` drawn from :mod:`ofplang.errors`.

Until the validator is implemented, ``validate`` raises
:class:`NotImplementedError`; the conformance runner treats that as "pending
implementation" (xfail) unless run in strict mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Validation modes.
STRICT = "strict"
EXTENSION_TOLERANT = "extension-tolerant"
MODES = frozenset({STRICT, EXTENSION_TOLERANT})


@dataclass(frozen=True)
class Diagnostic:
    """A single validation finding.

    ``code`` is a stable identifier from :mod:`ofplang.errors`. ``path`` is an
    optional human-oriented location hint (e.g. ``processes.main.inputs.x``)
    and is not required for fixture matching unless a fixture opts in.
    """

    code: str
    message: str = ""
    path: str | None = None


@dataclass
class ValidationResult:
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.diagnostics

    @property
    def codes(self) -> list[str]:
        return [d.code for d in self.diagnostics]


def validate(
    source: str | Path,
    *,
    mode: str = STRICT,
    base_dir: str | Path | None = None,
) -> ValidationResult:
    """Validate an ofplang v0 document rooted at ``source``.

    Parameters
    ----------
    source:
        Path to the root YAML document.
    mode:
        ``"strict"`` (portable v0) or ``"extension-tolerant"`` (accepts ``x-``
        extension keys/features/preference kinds).
    base_dir:
        Optional base directory for resolving relative ``$import`` paths.
        Defaults to the directory containing ``source``.
    """
    if mode not in MODES:
        raise ValueError(f"unknown validation mode: {mode!r}")
    raise NotImplementedError(
        "ofplang v0 validator is not implemented yet; conformance suite defines "
        "the contract to build against."
    )
