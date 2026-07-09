"""Scheduling policy checks (spec 23, 24).

Intent: scheduling policies are best-effort preferences, so policy *misses* and
conflicts are never validation errors. What v0 does constrain is placement and
payload shape: policies live only on composite processes, and each preference
kind fixes whether an `object` target is required or forbidden. This pass
validates the `prefer.kind` name and its object-target rule.

Placement on the wrong process kind (`scheduling` on an atomic) is reported by
the shape pass with `scheduling_on_atomic`; to avoid double-reporting, this pass
only inspects composite processes.
"""

from __future__ import annotations

from ofplang import errors
from ofplang.diagnostics import Diagnostics
from ofplang.validator import EXTENSION_TOLERANT
from ofplang.yamlnode import YMap, YScalar, YSeq, YNode

# Object-target rule per v0 preference kind (spec 23.4): gaps forbid an object
# target, temperature requires one.
_GAP_KINDS = {"max_gap", "min_gap"}
_OBJECT_REQUIRED = {"temperature"}
_V0_KINDS = _GAP_KINDS | _OBJECT_REQUIRED


def _check_policy(diags: Diagnostics, policy: YMap, base: str, mode: str) -> None:
    prefer = policy.get("prefer")
    kind = None
    if isinstance(prefer, YMap):
        kind_node = prefer.get("kind")
        if isinstance(kind_node, YScalar):
            kind = kind_node.text

    has_object = policy.get("object") is not None

    # Unknown preference kind: only x- extension kinds are tolerated, and only in
    # extension-tolerant mode (spec 23.4).
    if kind is None or (kind not in _V0_KINDS and not kind.startswith("x-")):
        diags.add(errors.UNKNOWN_PREFER_KIND, f"unknown prefer kind {kind!r}", f"{base}.prefer.kind")
        return
    if kind.startswith("x-"):
        if mode != EXTENSION_TOLERANT:
            diags.add(errors.UNKNOWN_PREFER_KIND, f"extension kind {kind!r}", f"{base}.prefer.kind")
        return

    # Object-target rules with dedicated codes so the author sees the exact rule.
    if kind in _GAP_KINDS and has_object:
        diags.add(errors.GAP_WITH_OBJECT, f"{kind} must not target an object", base)
    if kind in _OBJECT_REQUIRED and not has_object:
        diags.add(errors.TEMPERATURE_WITHOUT_OBJECT, f"{kind} requires an object target", base)


def check_scheduling(doc: YMap, diags: Diagnostics, mode: str) -> None:
    processes = doc.get("processes")
    if not isinstance(processes, YMap):
        return
    for pname in processes.keys():
        proc = processes.get(pname)
        if not isinstance(proc, YMap):
            continue
        # Only composites: atomic placement is the shape pass's concern.
        kind_node = proc.get("kind")
        if not (isinstance(kind_node, YScalar) and kind_node.text == "composite"):
            continue
        scheduling = proc.get("scheduling")
        if not isinstance(scheduling, YMap):
            continue
        policies = scheduling.get("policies")
        if not isinstance(policies, YSeq):
            continue
        for i, policy in enumerate(policies.items):
            if isinstance(policy, YMap):
                _check_policy(diags, policy, f"processes.{pname}.scheduling.policies[{i}]", mode)
