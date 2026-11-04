"""The `logbook.tsv` row: complete it with what the person who ran it knows and add it at the end.

`python -m evals` builds the row with `lever`, `arm` and `note` as `·`; with
`--lever=<name>` it adds the row by itself. `python -m evals.ab` with `--lever` adds
both, `A` as `baseline` and `B` as `new`. Without the flag it only prints,
so a run just to look does not dirty the logbook. The commit in the
logbook repo stays manual: it is another repo, shared.

It does not load the agent, so `evals.ab` uses it without importing `core_agent`.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

def checkout(repo: Path) -> Path:
    """The main checkout of `repo`, also from a git worktree.

    In a worktree `.git` is a file with `gitdir: <checkout>/.git/worktrees/<name>`, and the
    worktree lives inside the checkout (`.claude/worktrees/`): the sibling folder comes off the
    checkout and not off the worktree. Until Oct 3, 2026, from a worktree the logbook was
    looked up in `.claude/worktrees/logbook/`, which does not exist, and the row was not recorded.
    """
    git = repo / ".git"
    if git.is_file() and (line := git.read_text().strip()).startswith("gitdir:"):
        return Path(line.removeprefix("gitdir:").strip()).resolve().parents[2]
    return repo


LOGBOOK = checkout(Path(__file__).resolve().parents[1]).parent / "bitacora" / "bitacora.tsv"
"""The logbook of all the projects, in a `bitacora` checkout next to this one."""

COLUMNS = 15
LEVER, ARM, NOTE = 5, 6, 14
"""Where, counting from zero, the three columns filled in by the person who ran it go (see the TSV header)."""

FLAGS = ("--lever=", "--arm=", "--note=")
"""The logbook flags: they are not cases and do not change the run."""


def flag(argv: Sequence[str], name: str) -> str | None:
    """The value of `--<name>=<value>`, or `None` if it is not there."""
    prefix = f"--{name}="
    return next((a.removeprefix(prefix) for a in argv if a.startswith(prefix)), None)


def without_flags(argv: Sequence[str]) -> list[str]:
    """`argv` without the logbook flags, for what gets passed along or named with them."""
    return [a for a in argv if not a.startswith(FLAGS)]


def clean(value: str) -> str:
    """A cell: no tabs or newlines, which would split the row; empty is `·`."""
    return " ".join(value.split()) or "·"


def fill(line: str, lever: str, arm: str, note: str) -> str:
    """The row printed by the suite with `lever`, `arm` and `note` set."""
    cells = line.strip().split("\t")
    if len(cells) != COLUMNS:
        raise ValueError(f"the row has {len(cells)} columns and the logbook {COLUMNS}: {line!r}")
    cells[LEVER], cells[ARM], cells[NOTE] = clean(lever), clean(arm), clean(note)
    return "\t".join(cells)


def append(rows: Sequence[str], path: Path = LOGBOOK) -> bool:
    """Adds the rows at the end. If the logbook is not cloned alongside, it warns and returns `False`."""
    if not path.exists():
        print(f"  cannot find {path}: the rows stay printed above, not recorded")
        return False
    text = path.read_text()
    with path.open("a") as f:
        if text and not text.endswith("\n"):
            f.write("\n")
        f.writelines(f"{r}\n" for r in rows)
    print(f"  recorded in {path}: {len(rows)} row{'s' if len(rows) != 1 else ''}, the commit there is still pending")
    return True
