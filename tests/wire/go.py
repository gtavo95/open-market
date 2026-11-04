"""Where knowledge's Go code is, for the tests that hold the wire against it.

The host's repository sits next to this one, with its service at `services/knowledge`. Its fixtures
and its constants are read from there and never copied: a copy would go stale without a test noticing,
and the repo here is public (which is also why the sibling folder is found by its shape and not named).
When the code is not there (CI, another machine) those tests skip; `KNOWLEDGE_DIR` points at it when it
lives somewhere else.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest


def locate() -> Path:
    """`KNOWLEDGE_DIR`, or the first sibling folder of this repo that has `services/knowledge`."""
    if given := os.environ.get("KNOWLEDGE_DIR"):
        return Path(given)
    siblings = Path(__file__).resolve().parents[3]
    return next(iter(sorted(siblings.glob("*/services/knowledge"))), siblings / "knowledge")


ROOT = locate()
TESTDATA = ROOT / "turno" / "testdata"

needs_go = pytest.mark.skipif(not ROOT.is_dir(), reason=f"knowledge's Go code is not at {ROOT} (set KNOWLEDGE_DIR)")


def fixtures(kind: str) -> list[Path]:
    """The host's `kind` fixtures (`consultas` or `respuestas`), sorted; none when its repo is not here."""
    return sorted((TESTDATA / kind).glob("*.json"))


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def source(*parts: str) -> str:
    """The text of a Go file of the host, by its path under `ROOT`."""
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")
