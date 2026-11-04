"""The catalog bundle, loaded once: the text the model queries and the voice that serves.

Until Sep 18, 2026 this module had its own copy of the agent's
`corpus`, `index`, `frontmatter` and `vocabulary`. It went away with the hand copy
(see `agent.py`): `core_agent.build` reads the corpus and the searcher builds the
index and the ontology per turn from the `BUNDLE` of `core_agent.world.catalog`, and
the only thing this module does is point that `BUNDLE` at the service catalog
and say what it found. Nothing here calls the model or knows about HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import core_agent
from core_agent.world import catalog


@dataclass(frozen=True, slots=True)
class Catalog:
    """What is loaded from the bundle only once.

    `text` is what the model queries with `grep` (`core_agent.corpus()`: datasheets,
    ontology and company info, each file with its path in front). `sheets`
    is how many products there are, which is `len(core_agent.products())` and not the
    `=== products/` headers of the text, which also count `products/index.md`. `voice`
    is `voice.md` at the bundle root, empty if there is none: who serves, for the
    writer (see `core_agent.voice`).
    """

    text: str
    sheets: int
    voice: str


def load(bundle: Path) -> Catalog:
    """Points the `BUNDLE` of `core_agent.world.catalog` at the service catalog and reads it.

    `BUNDLE` is a variable of that module that `corpus()`, `products()` and
    `voice()` read on every call, so reassigning it is what makes
    `core_agent.build` build the agent over this catalog and not over the sample
    bundle that travels with the example. It is assigned in the module that READS it and not in
    plain `advisor`: the package re-exports it, but that re-export is a
    copy of the value, and moving it there would move nobody's catalog (the
    docstring of `world/catalog.py` says so). The `DEMO_BUNDLE` of the environment would do the
    same before importing; it is done here because the path comes from `Settings` and
    because a deployment that fails has to say why, not import oddly.
    It is the only global state the service touches, and it touches it once, at
    startup.

    The two errors have their own message because `/health` shows them: a
    directory that does not exist and one that exists without datasheets are two different
    deployments that get fixed differently.
    """
    if not bundle.is_dir():
        raise FileNotFoundError(f"the catalog bundle does not exist: {bundle}")
    catalog.BUNDLE = bundle
    text = core_agent.corpus()
    if not text:
        raise FileNotFoundError(f"the bundle has no datasheets in {core_agent.FOLDERS}: {bundle}")
    return Catalog(text=text, sheets=len(core_agent.products()), voice=core_agent.voice())
