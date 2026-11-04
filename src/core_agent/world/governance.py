"""The judge's rules as data: the bundle's `governance/`, one row per rule.

Every question the advisor uses to decide something by reading text, and every code gate that
closes the same thing, has a row in okf with its id (`domain/rule_tag`, the `_tag` for governed tag), the key the
judge answers, the threshold and what happens when it fires. It is edited in okf and arrives through
`okf/ (the bundle lives in the repo)`, like the datasheets. Here the table is only read: what each
row means is told by okf (`governance/index.md`), and what value it has in a turn is told by
`host/rules.py`.

Without the folder (a bundle from before Oct 3, 2026) there are no rules, and
`Answer.rules` comes out empty: nothing fails.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import catalog

FOLDER = "governance"

COLUMNS = ("id", "question", "type", "reads", "threshold", "action", "crm_reason", "same_fact")
"""The table's columns, in order. okf's `verify.sh` fails if a sheet brings others."""

ARGMAX = "argmax"
"""The threshold of a `choice` where the highest option wins."""


@dataclass(frozen=True, slots=True)
class Rule:
    """A row of the table.

    `threshold` is a number, `ARGMAX`, or `None` in a code rule, which has no p.
    `question` goes as is: `key`, or `label=a,b` for the sum of those options.
    """

    id: str
    question: str
    kind: str
    reads: str
    threshold: float | str | None
    action: str
    reason: str
    same_fact: tuple[str, ...]

    @property
    def label(self) -> str:
        """The key the judge answers, without the options."""
        return self.question.split("=", 1)[0]

    @property
    def options(self) -> tuple[str, ...]:
        """The options of `label=a,b`; empty if the question does not name them."""
        _, _, rest = self.question.partition("=")
        return tuple(o.strip() for o in rest.split(",") if o.strip())


def _threshold(cell: str) -> float | str | None:
    if not cell:
        return None
    return ARGMAX if cell == ARGMAX else float(cell)


def table(text: str) -> tuple[Rule, ...]:
    """The rules of a sheet: the rows of the table that opens with `| id |`."""
    rows: list[Rule] = []
    open_ = False
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells[0] == "id":
            open_ = True
            continue
        if not open_ or not cells[0] or set(cells[0]) <= {"-"}:
            continue
        cells += [""] * (len(COLUMNS) - len(cells))
        id_, question, kind, reads, threshold, action, reason, same = cells[: len(COLUMNS)]
        rows.append(
            Rule(
                id=id_,
                question=question,
                kind=kind,
                reads=reads,
                threshold=_threshold(threshold),
                action=action,
                reason=reason,
                same_fact=tuple(s.strip() for s in same.split(",") if s.strip()),
            )
        )
    return tuple(rows)


def rules(bundle: Path | None = None) -> tuple[Rule, ...]:
    """All the bundle's rules, sheet by sheet in name order. Without `governance/`, none."""
    root = (bundle or catalog.BUNDLE) / FOLDER
    if not root.is_dir():
        return ()
    out: list[Rule] = []
    for f in sorted(root.glob("*.md")):
        if f.name != "index.md":
            out.extend(table(f.read_text(errors="replace")))
    return tuple(out)
