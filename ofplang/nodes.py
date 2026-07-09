"""Structured node validation: map / fold / do_while / branch (spec 16-21).

Intent: structured nodes wrap a target process with loop/branch control, and
each kind imposes extra well-formedness rules on top of the target's own Object
tracking completeness. This pass checks the kind-specific structural rules:

  * `fold` / `do_while` carry bindings need a matching same-name output on the
    target (structured carry compatibility, spec 16);
  * `do_while` requires an explicit `max_iterations` bound (spec 19); and
  * `branch` forbids one-sided Object-bearing outputs — an Object output must be
    common to both arms so its identity does not depend on the chosen arm
    (spec 20, 20.1).

Composite linearity intentionally skips structured nodes (their output shaping
differs — e.g. `map` wraps outputs in Array), so their Object flow is governed
by these node-local rules plus the target processes' completeness.
"""

from __future__ import annotations

from ofplang import errors
from ofplang.diagnostics import Diagnostics
from ofplang.objects import ProcSig
from ofplang.yamlnode import YMap, YScalar, YSeq, YNode


def _carry_names(node: YMap) -> list[str]:
    carry = node.get("carry")
    return carry.keys() if isinstance(carry, YMap) else []


def _check_carry_compat(
    diags: Diagnostics, node: YMap, nid: str, target: ProcSig, base: str
) -> None:
    """Every carry binding needs a same-name output on the target (spec 16).

    (Same-type/same-phase refinement layers on later; existence is the rule the
    current cases exercise, and a missing output is the primary failure mode.)
    """
    for cname in _carry_names(node):
        if cname not in target.outputs:
            diags.add(
                errors.CARRY_OUTPUT_MISSING,
                f"carry {cname!r} has no matching output on target process",
                f"{base}.nodes.{nid}.carry.{cname}",
            )


def _object_output_names(sig: ProcSig) -> set[str]:
    return {n for n, s in sig.outputs.items() if s.object_bearing}


def _check_branch(
    diags: Diagnostics, node: YMap, nid: str, sigs: dict[str, ProcSig], base: str
) -> None:
    """Reject Object-bearing outputs that are not common to both arms.

    We compare the Object-bearing output name sets of the two arm processes; any
    name present in one arm but not the other is a one-sided Object output. If
    `else` is omitted it acts as an implicit identity arm over the Object-bearing
    branch arguments (spec 20), so the "else side" is taken from `args`.
    """
    then_arm = node.get("then")
    else_arm = node.get("else")

    then_proc = then_arm.get("process") if isinstance(then_arm, YMap) else None
    then_obj: set[str] = set()
    if isinstance(then_proc, YScalar) and then_proc.text in sigs:
        then_obj = _object_output_names(sigs[then_proc.text])

    if isinstance(else_arm, YMap):
        else_proc = else_arm.get("process")
        else_obj: set[str] = set()
        if isinstance(else_proc, YScalar) and else_proc.text in sigs:
            else_obj = _object_output_names(sigs[else_proc.text])
    else:
        # Implicit identity else arm: it re-exposes each Object-bearing branch
        # argument as a same-name Object output (spec 20).
        else_obj = set()
        args = node.get("args")
        if isinstance(args, YMap):
            # An arg is Object-bearing if the then-arm's same-name *input* is;
            # arms share argument names/types, so the then signature is a proxy.
            then_inputs = sigs.get(then_proc.text) if isinstance(then_proc, YScalar) else None
            if then_inputs is not None:
                for aname in args.keys():
                    port = then_inputs.inputs.get(aname)
                    if port is not None and port.object_bearing:
                        else_obj.add(aname)

    for name in sorted(then_obj ^ else_obj):
        diags.add(
            errors.ONE_SIDED_OBJECT_OUTPUT,
            f"Object-bearing output {name!r} is not common to both arms",
            f"{base}.nodes.{nid}.{name}",
        )


def check_nodes(doc: YMap, diags: Diagnostics, sigs: dict[str, ProcSig]) -> None:
    processes = doc.get("processes")
    if not isinstance(processes, YMap):
        return

    for pname in processes.keys():
        proc = processes.get(pname)
        if not isinstance(proc, YMap):
            continue
        body = proc.get("body")
        if not isinstance(body, YMap):
            continue
        nodes = body.get("nodes")
        if not isinstance(nodes, YSeq):
            continue
        base = f"processes.{pname}.body"

        for item in nodes.items:
            if not isinstance(item, YMap):
                continue
            kind_node = item.get("kind")
            kind = kind_node.text if isinstance(kind_node, YScalar) else None
            if kind is None:
                continue  # ordinary node: handled by linearity, not here
            id_node = item.get("id")
            nid = id_node.text if isinstance(id_node, YScalar) else "?"

            proc_ref = item.get("process")
            target = sigs.get(proc_ref.text) if isinstance(proc_ref, YScalar) else None

            if kind == "fold":
                if target is not None:
                    _check_carry_compat(diags, item, nid, target, base)
            elif kind == "do_while":
                # max_iterations is required (spec 19, requirement 5).
                if item.get("max_iterations") is None:
                    diags.add(
                        errors.MISSING_MAX_ITERATIONS,
                        "do_while requires max_iterations",
                        f"{base}.nodes.{nid}",
                    )
                if target is not None:
                    _check_carry_compat(diags, item, nid, target, base)
            elif kind == "branch":
                _check_branch(diags, item, nid, sigs, base)
            # `map` has no carry/condition; its feature requirement is derived in
            # the feature pass and its Object flow by the target's completeness.
