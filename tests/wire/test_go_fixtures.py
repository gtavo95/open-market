"""The wire held against the host's real fixtures: what knowledge posts, and what it reads back.

The fixtures are the Go repo's own (`turno/testdata/consultas` and `respuestas`, the ones its
tests decode and encode), read from where they live and never copied here. Every test skips when
that repo is not next to this one (`tests/wire/go.py`).

What is held:

- a request, Spanish to English and back, comes out equal to what knowledge posted, key by key
  (`extras=True` keeps what the interior has no use for, so nothing hides);
- what the interior gets validates against `Query` and leaves no WARNING;
- an answer the interior writes in English comes out with the same keys knowledge's own answers
  have: the in-repo English fixtures (`tests/contract`) are the translation of these, so the
  tables must turn them back into the same shape and the same contract words;
- the words and keys the tables lack are exactly the ones said below, so a new one in the host is red.

The host also serves a vertical whose billing form has other fields; its fixtures sit in the same
folders and are not this service's contract. The way to tell without naming it is the form: a fixture
is open-market's when every field id of its form is one of this bundle's.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from schemas.queries import AnswerOut, Query
from wire import to_english, to_wire
from wire.tables import VALUES

from .go import fixtures, load, needs_go

pytestmark = needs_go

Gap = tuple[str, str]
IN_REPO = Path(__file__).resolve().parents[1] / "contract"

KNOWN_GAPS: dict[Gap, str] = {
    ("effect_id", "send_quote"): "the host sends a quote's summary; open-market never proposes it",
    ("args_key", "cobra"): "an arg of the host's own charge effect; open-market never writes it",
    ("handoff_reason", "pide_humano"): "the host's fixture reason: it is not in its own `validHandoffMotivos` either",
}
"""The words and keys of the host's fixtures that open-market has no twin for, and why. Each crosses unchanged with a WARNING."""

UNFILLED = re.compile(
    r"^\.(conversationId|turnId|traza)$"  # the host's own ids and the trace
    r"|^\.modelo\."  # the model's count of the turn: the interior has the adapter's total, not the turn's
    r"|precio_de$"  # the price a line starts from: no source in the interior
    r"|^\.venta\.juicio\.estado\."  # keys the judge's model chose for its notes: each side's fixture has its own
)
"""Paths knowledge's answers and requests have and open-market does not fill (see `answer_of` in `routes/consultas.py`)."""

PAIRS = {
    "queries": (
        "consultas",
        "Query",
        {"first_turn": "primer_turno", "memory": "memoria", "pending_payment": "pago_pendiente", "resumption": "retomada", "second_turn": "segundo_turno", "with_deal": "con_deal"},
    ),
    "answers": (
        "respuestas",
        "AnswerOut",
        {
            "changes_with_form": "cambios_con_formulario",
            "handoff": "handoff",
            "line_without_price": "renglon_sin_precio",
            "payment_link": "link_de_pago",
            "restart_turn": "reinicio",
            "sale_with_cart": "venta_con_carrito",
            "simple_answer": "respuesta_simple",
        },
    ),
}


@contextmanager
def caught() -> Iterator[list[logging.LogRecord]]:
    """The WARNINGs the walker logs while the block runs."""
    records: list[logging.LogRecord] = []

    class Catch(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler, log = Catch(logging.WARNING), logging.getLogger("wire.translate")
    log.addHandler(handler)
    try:
        yield records
    finally:
        log.removeHandler(handler)


def gap_of(record: logging.LogRecord) -> Gap:
    """A WARNING as the pair it is about: (table, word) for a value, ("field", key) for a name."""
    args = record.args
    assert isinstance(args, tuple)
    if "is not in the" in record.msg:
        return (str(args[2]), str(args[1]))
    if "has no field" in record.msg:
        return ("field", str(args[1]))
    return ("other", record.getMessage())


def gaps(shape: str, data: Any) -> set[Gap]:
    with caught() as records:
        to_english(shape, data, extras=True)
    return {gap_of(r) for r in records}


def partition(kind: str, shape: str) -> tuple[list[Path], list[Path]]:
    """The fixtures that are this service's contract, and the ones of the other vertical (a form id the bundle lacks)."""
    ours: list[Path] = []
    other: list[Path] = []
    for path in fixtures(kind):
        (other if any(table == "form_field" for table, _ in gaps(shape, load(path))) else ours).append(path)
    return ours, other


REQUESTS, OTHER_REQUESTS = partition("consultas", "Query")
ANSWERS, OTHER_ANSWERS = partition("respuestas", "AnswerOut")


def ids(paths: list[Path]) -> list[str]:
    return [p.stem for p in paths]


def paths_of(x: Any, at: str = "") -> set[str]:
    """Every key path of a payload: `.deal.items[].sku`; an empty list or dict is a path of its own."""
    if isinstance(x, dict):
        found = {p for k, v in x.items() for p in paths_of(v, f"{at}.{k}")}
        return found or {at + "{}"}
    if isinstance(x, list):
        found = {p for v in x for p in paths_of(v, at + "[]")}
        return found or {at + "[]="}
    return {at}


def leaves_of(x: Any, at: str = "") -> dict[str, Any]:
    if isinstance(x, dict):
        return {p: v for k, item in x.items() for p, v in leaves_of(item, f"{at}.{k}").items()}
    if isinstance(x, list):
        return {p: v for i, item in enumerate(x) for p, v in leaves_of(item, f"{at}[{i}]").items()}
    return {at: x}


def count(x: Any) -> int:
    if isinstance(x, dict):
        return sum(1 + count(v) for v in x.values())
    if isinstance(x, list):
        return sum(1 + count(v) for v in x)
    return 0


def test_the_host_has_fixtures() -> None:
    assert REQUESTS and ANSWERS, "no fixtures where the host keeps them"
    assert len(OTHER_REQUESTS) + len(OTHER_ANSWERS) < len(REQUESTS) + len(ANSWERS)


@pytest.mark.parametrize("path", REQUESTS, ids=ids(REQUESTS))
class TestWhatKnowledgePosts:
    def test_spanish_to_english_and_back_is_what_it_posted(self, path: Path) -> None:
        posted = load(path)

        assert to_wire("Query", to_english("Query", posted, extras=True)) == posted

    def test_the_interior_reads_all_of_it_without_a_warning(self, path: Path, caplog: pytest.LogCaptureFixture) -> None:
        posted = load(path)

        with caplog.at_level(logging.WARNING):
            query = Query.model_validate(to_english("Query", posted))

        assert not caplog.records, caplog.text
        assert query.question == posted["pregunta"]

    def test_what_is_dropped_is_only_what_the_interior_has_no_use_for(self, path: Path) -> None:
        posted = load(path)
        kept = to_english("Query", posted)
        everything = to_english("Query", posted, extras=True)

        assert set(everything) - set(kept) <= {"trace", "turn_id", "conversation_id", "attachments", "notice", "closed_ids"}
        assert count(everything) == count(posted), "nothing is lost on the way in"


@pytest.mark.parametrize("path", ANSWERS, ids=ids(ANSWERS))
class TestWhatKnowledgeReads:
    def test_spanish_to_english_and_back_is_what_it_wrote(self, path: Path) -> None:
        answered = load(path)

        assert to_wire("AnswerOut", to_english("AnswerOut", answered, extras=True)) == answered

    def test_the_interior_schema_reads_it(self, path: Path) -> None:
        answered = load(path)

        answer = AnswerOut.model_validate(to_english("AnswerOut", answered))

        assert answer.answer == answered["respuesta"]
        assert answer.tokens == answered["tokens"]


@pytest.mark.parametrize("path", OTHER_REQUESTS + OTHER_ANSWERS, ids=ids(OTHER_REQUESTS + OTHER_ANSWERS))
def test_the_other_verticals_fixtures_lose_nothing_and_differ_only_in_their_form_ids(path: Path) -> None:
    shape = "Query" if path in OTHER_REQUESTS else "AnswerOut"
    data = load(path)

    assert {table for table, _ in gaps(shape, data)} == {"form_field"}
    assert count(to_english(shape, data, extras=True)) == count(data)


def test_the_only_words_the_tables_lack_are_the_ones_said() -> None:
    """A word or key the host starts using that has no twin turns this red; so does one it stops using."""
    found: set[Gap] = set()
    for shape, paths in (("Query", REQUESTS), ("AnswerOut", ANSWERS)):
        for path in paths:
            found |= gaps(shape, load(path))

    assert found == set(KNOWN_GAPS)


class TestTheEnglishFixturesOfThisRepoAreTheseSameThings:
    """`tests/contract` holds the English twin of each fixture: written by hand, so an independent reading of the tables."""

    CASES = [(kind, shape, english, spanish) for kind, (_, shape, names) in PAIRS.items() for english, spanish in names.items()]

    def host(self, kind: str, stem: str) -> Any:
        folder = PAIRS[kind][0]
        return load(next(p for p in fixtures(folder) if p.stem == stem))

    def english(self, kind: str, name: str) -> Any:
        return load(IN_REPO / kind / f"{name}.json")

    def test_every_pair_exists(self) -> None:
        for kind, (folder, _, names) in PAIRS.items():
            assert {p.stem for p in fixtures(folder)} >= set(names.values())
            assert {p.stem for p in (IN_REPO / kind).glob("*.json")} == set(names)

    @pytest.mark.parametrize("kind, shape, english, spanish", CASES, ids=[c[2] for c in CASES])
    def test_turned_to_spanish_it_has_the_keys_of_the_hosts(self, kind: str, shape: str, english: str, spanish: str) -> None:
        mine = to_wire(shape, self.english(kind, english))
        theirs = self.host(kind, spanish)

        ours_only = {p for p in paths_of(mine) - paths_of(theirs) if not UNFILLED.search(p)}
        theirs_only = {p for p in paths_of(theirs) - paths_of(mine) if not UNFILLED.search(p)}

        assert not ours_only, f"keys the interior writes and the host's answer does not have: {sorted(ours_only)}"
        assert not theirs_only, f"keys the host has and the interior neither writes nor is known to leave out: {sorted(theirs_only)}"

    @pytest.mark.parametrize("kind, shape, english, spanish", CASES, ids=[c[2] for c in CASES])
    def test_turned_to_spanish_it_says_the_contract_words_the_host_says(self, kind: str, shape: str, english: str, spanish: str) -> None:
        """Where either side holds a word of the tables, the two sides hold the same one. Prose (the customer's words, labels) is not compared."""
        words = {w for table in VALUES.values() for w in table.values()}
        mine = leaves_of(to_wire(shape, self.english(kind, english)))
        theirs = leaves_of(self.host(kind, spanish))

        differ = {p: (mine[p], theirs[p]) for p in mine.keys() & theirs.keys() if mine[p] != theirs[p] and (mine[p] in words or theirs[p] in words)}

        assert not differ, differ
