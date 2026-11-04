"""What knowledge posts to `/queries`, as it is, from `queries/*.json` (copied from knowledge).

Since agro#10 the input ignores what it does not know and warns about it with a WARNING, so validating is
not enough: a field knowledge starts sending and agro does not read would go by in silence. Each fixture
has to validate and leave no WARNING. The 422 of Oct 9, 2026 (`form` resent) would have
failed here.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from schemas.queries import Query

QUERIES = sorted((Path(__file__).parent / "queries").glob("*.json"))


def test_there_are_fixtures() -> None:
    assert QUERIES, "no fixtures in tests/contract/queries"


@pytest.mark.parametrize("path", QUERIES, ids=[p.stem for p in QUERIES])
def test_agro_reads_all_of_what_knowledge_sends(path: Path, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="schemas.queries"):
        Query.model_validate(json.loads(path.read_text(encoding="utf-8")))

    assert not caplog.records, caplog.text
