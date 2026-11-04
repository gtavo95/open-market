"""Words of the host's contract that are not handoff reasons, read from its source: effect kinds, memory kinds, arg keys.

All of it skips when the host's repo is not next to this one.
"""

from __future__ import annotations

import re
from pathlib import Path

from core_agent.roles.effects import DRAFT_KEYS, EFFECT_RULES
from wire.tables import VALUES

from .go import ROOT, needs_go, source

pytestmark = needs_go

READERS = ("adapters", "efectos", "turno", "memoria", "contrato", "handoff")
"""The folders of the host's Go code that read what open-market writes. Test files are not looked at."""


def go_text() -> str:
    parts: list[str] = []
    for folder in READERS:
        for path in sorted(Path(ROOT, folder).rglob("*.go")):
            if not path.name.endswith("_test.go"):
                parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_the_kinds_of_a_pending_effect_are_kinds_of_the_contract() -> None:
    contract = set(re.findall(r'Kind\w+\s*=\s*"([a-z_]+)"', source("contrato", "efectos_del_agente.go")))
    emitted = {intent.kind for intent in EFFECT_RULES.values()} | {"handoff"}

    assert len(contract) >= 10
    assert emitted <= contract, sorted(emitted - contract)


def test_the_memory_kinds_are_the_ones_the_host_writes() -> None:
    block = re.search(r"var memoryKinds = map\[string\]string\{(.*?)\n\}", source("memoria", "memoria_del_cliente.go"), re.S)
    assert block, "memoryKinds is no longer where it was"

    assert set(re.findall(r':\s*"([a-z]+)",', block.group(1))) == set(VALUES["memory_kind"].values())


def test_every_arg_key_the_interior_writes_is_one_the_host_reads() -> None:
    """The Spanish side of each key is quoted somewhere in the host's code (where it reads the arg, or where it names it)."""
    text = go_text()
    written = {"path", "item", "currency", "total", "origin", "reason"} | {key for _, key in DRAFT_KEYS}

    for key in sorted(written):
        wire = VALUES["args_key"][key]
        assert f'"{wire}"' in text, f"the host never reads {wire!r} (the interior's {key!r})"
