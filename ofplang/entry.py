"""Entry process resolution (spec 10.3).

Intent: a v0 document must have exactly one entry process. The rule has an
implicit-default form (`main`) so simple documents need no `entry` key, but an
explicit `entry` must name a real process. This pass reports the two failure
modes with distinct codes so authors can tell "you forgot to define an entry"
apart from "your entry points at a missing process".

Process-dependency acyclicity (also spec 10.2/10.3) is validated separately in
the object/graph layer where the full node graph is available.
"""

from __future__ import annotations

from ofplang import errors
from ofplang.diagnostics import Diagnostics
from ofplang.yamlnode import YMap, YScalar, YNode


def check_entry(doc: YNode, diags: Diagnostics) -> None:
    if not isinstance(doc, YMap):
        return  # a non-mapping root was already reported by the shape pass

    processes = doc.get("processes")
    process_names = set(processes.keys()) if isinstance(processes, YMap) else set()

    entry_node = doc.get("entry")

    # Implicit form: no `entry` key. `main` is the entry if it exists, otherwise
    # the document has no entry process at all.
    if entry_node is None:
        if "main" not in process_names:
            diags.add(
                errors.NO_ENTRY_PROCESS,
                "no 'entry' and no process named 'main'",
                "entry",
            )
        return

    # Explicit form: must be a scalar naming an existing process.
    if not isinstance(entry_node, YScalar):
        diags.add(errors.WRONG_VALUE_KIND, "entry must be a string", "entry")
        return
    if entry_node.text not in process_names:
        diags.add(
            errors.UNKNOWN_ENTRY_PROCESS,
            f"entry names unknown process {entry_node.text!r}",
            "entry",
        )
