"""The searcher's REPL is built per turn: `notes` empty each time, the index from disk, and the child closed on exit."""

from __future__ import annotations

import multiprocessing
from pathlib import Path

import pytest
from core_agent.roles.searcher import search_catalog
from core_agent.world import catalog
from catalejo.core import Log, Message, Role
from catalejo.llm import ScriptedModel
from catalejo.rlm import Dossier

DATASHEET = """---
title: Larvane
tags:
  - insecticide
certified_crops:
  - Tomato
---

# Agronomy

```json
{"targets": [{"id": "thrips", "name": "Thrips", "kind": "insect", "aliases": []}], "default_regimens": [], "overrides": [], "safety": {}}
```
"""

TABLE = """| id | label | parent | alias | note |
|---|---|---|---|---|
| thrips | Thrips |  | thrips |  |
"""


@pytest.fixture
def bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A minimal bundle with what `workshop` parses, and `catalog.BUNDLE` pointing there."""
    (tmp_path / "products").mkdir()
    (tmp_path / "products" / "larvane.md").write_text(DATASHEET)
    (tmp_path / "ontology").mkdir()
    for name in ("targets.md", "crops.md", "product-types.md"):
        (tmp_path / "ontology" / name).write_text(TABLE)
    monkeypatch.setattr(catalog, "BUNDLE", tmp_path)
    return tmp_path


class Script(ScriptedModel):
    """A `ScriptedModel` that is also a `Provider`: it has a name and can be closed."""

    model = "script"

    async def aclose(self) -> None:
        pass


def block(code: str) -> str:
    return f"```python\n{code}\n```"


QUESTION = Log(said=(Message(Role.USER, "thrips on tomato"),))
CLOSING = "Nothing else.\nSOURCE: none"


def output(dossier: Dossier) -> str:
    """The first line the REPL printed on the last turn, taken from the dossier."""
    (t,) = dossier.drain()
    repl = next(m.text for m in t.said if m.role is Role.USER and m.text.startswith("[repl]"))
    return repl.splitlines()[1]


class TestTheWorkshopPerTurn:
    async def test_notes_starts_empty_on_each_turn(self, bundle: Path) -> None:
        dossier = Dossier()
        model = Script(block('notes.append("x"); print(len(notes))'), CLOSING, block("print(len(notes))"), CLOSING)
        cell = search_catalog(catalog.corpus(), model, dossier=dossier)

        await cell(QUESTION)
        first = output(dossier)
        await cell(QUESTION)
        second = output(dossier)

        assert (first, second) == ("1", "0")

    async def test_what_the_model_mutates_does_not_change_the_index_for_the_next_turn(self, bundle: Path) -> None:
        dossier = Dossier()
        model = Script(block("products.clear(); print(len(products))"), CLOSING, block("print(len(products))"), CLOSING)
        cell = search_catalog(catalog.corpus(), model, dossier=dossier)

        await cell(QUESTION)
        assert output(dossier) == "0"
        await cell(QUESTION)

        assert output(dossier) == "1"

    async def test_contained_runs_in_a_child_that_does_not_outlive_the_turn(self, bundle: Path) -> None:
        dossier = Dossier()
        model = Script(block("print(len(products))"), CLOSING)
        cell = search_catalog(catalog.corpus(), model, dossier=dossier, contained=True)

        await cell(QUESTION)

        assert output(dossier) == "1"
        assert multiprocessing.active_children() == []
