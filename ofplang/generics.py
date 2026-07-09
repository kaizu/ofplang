"""Generic type parameters and `where` constraints (spec 8, 8.1).

Intent: v0 generics are deliberately minimal — parameters carry only a domain,
constraints are nominal trait memberships, and type arguments are *inferred*
from input bindings (there is no explicit type-argument syntax). This pass
validates the parts that are decidable from a process definition alone:

  * each type parameter declares a valid domain;
  * every type parameter appears in at least one input port type (spec 8.1),
    since inference has nothing to bind it to otherwise; and
  * each `where` constraint is a well-formed `TraitName<Param>` naming a known
    trait and a declared parameter.

Constraint *satisfaction* (checking the inferred concrete type implements the
trait) requires an invocation site and is performed during graph validation by
the node layer; it is out of scope here.
"""

from __future__ import annotations

import re

from ofplang import errors
from ofplang.diagnostics import Diagnostics
from ofplang.types import (
    ArrayT,
    Atom,
    TypeEnv,
    TypeExpr,
    TypeParseError,
    parse_type,
    process_type_params,
)
from ofplang.yamlnode import YMap, YScalar, YSeq, YNode

# A `where` constraint: TraitName<Param>, whitespace allowed only inside the
# angle brackets (spec 8.1) — mirrors the type-expression whitespace rule.
_CONSTRAINT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)<[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]*>$")


def _atoms(expr: TypeExpr) -> set[str]:
    """All atom names occurring in a type expression (recursing into Array)."""
    if isinstance(expr, ArrayT):
        return _atoms(expr.elem)
    if isinstance(expr, Atom):
        return {expr.name}
    return set()


def _input_atoms(proc: YMap) -> set[str]:
    """Collect every type-atom name used across the process's input ports."""
    names: set[str] = set()
    inputs = proc.get("inputs")
    if isinstance(inputs, YMap):
        for pname in inputs.keys():
            port = inputs.get(pname)
            if isinstance(port, YMap):
                tnode = port.get("type")
                if isinstance(tnode, YScalar) and tnode.is_str:
                    try:
                        names |= _atoms(parse_type(tnode.text))
                    except TypeParseError:
                        pass
    return names


def check_generics(doc: YMap, diags: Diagnostics, env: TypeEnv) -> None:
    processes = doc.get("processes")
    if not isinstance(processes, YMap):
        return

    for pname in processes.keys():
        proc = processes.get(pname)
        if not isinstance(proc, YMap):
            continue
        base = f"processes.{pname}"
        tp_node = proc.get("type_params")
        if not isinstance(tp_node, YMap):
            continue

        tp = process_type_params(proc)  # only well-formed 'data'/'object' params

        # Each declared parameter must have a valid domain (spec 8). A missing or
        # bad domain is reported so the parameter is visibly rejected.
        for name in tp_node.keys():
            decl = tp_node.get(name)
            dom = decl.get("domain") if isinstance(decl, YMap) else None
            if not isinstance(dom, YScalar):
                diags.add(errors.MISSING_TYPE_PARAM_DOMAIN, f"{name!r} needs a domain", f"{base}.type_params.{name}")
            elif dom.text not in ("data", "object"):
                diags.add(errors.BAD_TYPE_PARAM_DOMAIN, f"invalid domain {dom.text!r}", f"{base}.type_params.{name}")

        # Every parameter must appear in an input port type so inference can bind
        # it (spec 8.1). Parameters used only in outputs/where are errors.
        used = _input_atoms(proc)
        for name in tp:
            if name not in used:
                diags.add(
                    errors.TYPE_PARAM_NOT_IN_INPUT,
                    f"type parameter {name!r} not used by any input port",
                    f"{base}.type_params.{name}",
                )

        # `where` constraints: well-formed, known trait, declared parameter.
        where = proc.get("where")
        if isinstance(where, YSeq):
            for i, item in enumerate(where.items):
                cpath = f"{base}.where[{i}]"
                if not isinstance(item, YScalar) or not item.is_str:
                    diags.add(errors.MALFORMED_CONSTRAINT, "constraint must be a string", cpath)
                    continue
                m = _CONSTRAINT_RE.match(item.text)
                if not m:
                    diags.add(errors.MALFORMED_CONSTRAINT, f"malformed constraint {item.text!r}", cpath)
                    continue
                trait, param = m.group(1), m.group(2)
                # The constraint must target a declared parameter of this process.
                if param not in tp:
                    diags.add(errors.MALFORMED_CONSTRAINT, f"{param!r} is not a type parameter", cpath)
                    continue
                # The trait must be `Numeric` (built-in) or a declared trait.
                if trait != "Numeric" and trait not in env.traits:
                    diags.add(errors.UNKNOWN_TRAIT, f"unknown trait {trait!r}", cpath)
