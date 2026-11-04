"""The catalog as files: where the bundle lives, what is read whole and what is parsed into data.

Nothing here calls the model or the judge. This is the bundle's format and
nothing else: `corpus()` is the text the searcher's REPL receives whole, `voice()`
is who attends the customer, and the rest are the derived indexes that `workshop`
puts in that REPL (see `roles/searcher.py`). An index is not the source: if it
differs from the datasheet, the datasheet wins, and the docstrings of `products`
and `closed_vocabulary` carry the number that put each one there.

`BUNDLE` is resolved at import time, from `DEMO_BUNDLE` in the environment: without
the variable it is `okf/`, the copy that travels in the repo (see
`okf/ (the bundle lives in the repo)`); to run the evals it points at the live
bundle, which is the one that brings `evals/`. A
host that moves it after import has to move it HERE (`BUNDLE` in this
module, as `tests/core_agent/test_searcher_repl.py` does with `monkeypatch`), not in the
module that reads it: every function in this file looks at this global each time it
runs, on purpose, so a catalog that changed on disk is read fresh without a restart.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable

from catalejo.rlm.repl import strip_accents

CATALOG = Path(__file__).resolve().parents[3] / "okf"
"""The repo's catalog, at its root: three folders above this file."""

BUNDLE = Path(os.environ.get("DEMO_BUNDLE") or CATALOG)

FOLDERS = ("products", "ontology", "company_info")
VOICE_FILE = "voice.md"


def corpus() -> str:
    """The datasheets, the ontology and the company info, each file with its path in front."""
    parts = []
    for f in sorted(BUNDLE.rglob("*.md")):
        rel = f.relative_to(BUNDLE)
        if rel.parts[0] in FOLDERS:
            parts.append(f"=== {rel} ===\n{f.read_text(errors='replace')}")
    return "\n\n".join(parts)


def voice() -> str:
    """Who attends the customer, if the bundle says so (`voice.md` at its root); otherwise empty.

    Without the frontmatter: okf requires it in every `.md`, and it tells the writer nothing.
    """
    path = BUNDLE / VOICE_FILE
    if not path.is_file():
        return ""
    text = path.read_text(errors="replace")
    if text.startswith("---\n"):
        text = text[4:].split("\n---\n", 1)[-1]
    return text.strip()


def vocabulary(text: str) -> list[dict[str, Any]]:
    """The concept table of a sheet in `ontology/`, one entry per row.

    The first table that opens with `| id |`, the columns of the header, and
    `alias` is the only one split by comma.
    """
    lines = iter(text.splitlines())
    columns: list[str] = []
    for line in lines:
        if line.startswith("| id |"):
            columns = [c.strip() for c in line.strip().strip("|").split("|")]
            next(lines, None)
            break
    entries: list[dict[str, Any]] = []
    for line in lines:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        row: dict[str, Any] = dict(zip(columns, cells))
        if "alias" in row:
            row["alias"] = [a.strip() for a in row["alias"].split(",") if a.strip()]
        entries.append(row)
    return entries


def target_ids(text: str) -> list[str]:
    """The `id`s of `targets` in a datasheet's `# Agronomy` block, or empty if it does not parse."""
    if "\n# Agronomy" not in text:
        return []
    after = text.split("\n# Agronomy", 1)[1]
    if after.count("```") < 2:
        return []
    try:
        data = json.loads(after.split("```", 2)[1].removeprefix("json"))
    except json.JSONDecodeError:
        return []
    return [t["id"] for t in data.get("targets", []) if "id" in t]


def tag_ids(text: str) -> list[str]:
    """The ids of `tags:` in a datasheet's frontmatter, or empty if it has none."""
    if not text.startswith("---\n"):
        return []
    body = text[4:].split("\n---", 1)[0]
    in_tags = False
    ids: list[str] = []
    for line in body.splitlines():
        if line.startswith("tags:"):
            in_tags = True
        elif in_tags and line.startswith("  - "):
            ids.append(line[4:].strip().strip('"'))
        elif in_tags and not line.startswith(" "):
            in_tags = False
    return ids


def closed_vocabulary(markdown: str, ids_of: Callable[[str], list[str]]) -> list[dict[str, Any]]:
    """A closed vocabulary with `datasheets` computed here and not by the model: which products each entry covers, children included.

    `markdown` is the markdown of a table in `ontology/`; `ids_of` pulls the ids out of
    a datasheet (`target_ids` for pests, `tag_ids` for product types).
    Giving the model only the `id` so it would cross it against the products itself,
    `old/agro.py` measured that in 3 of 6 rodenticide runs the join went wrong
    (a dict treated as a list) and closed with "no product covers rats": a
    piece of data that opens a new path to a false zero is worse than the text. The join
    comes done, and a parent covers what its children cover (`FORMAT.md`).
    """
    sheet = vocabulary(markdown)
    direct: dict[str, set[str]] = {}
    for f in sorted((BUNDLE / "products").glob("*.md")):
        if f.name == "index.md":
            continue
        rel = f"products/{f.name}"
        for id_ in ids_of(f.read_text(errors="replace")):
            direct.setdefault(id_, set()).add(rel)
    children: dict[str, list[str]] = {}
    for e in sheet:
        children.setdefault(e["parent"], []).append(e["id"])

    def covers(id_: str) -> set[str]:
        paths = set(direct.get(id_, ()))
        for child in children.get(id_, ()):
            paths |= covers(child)
        return paths

    return [{**e, "datasheets": sorted(covers(e["id"]))} for e in sheet]


def targets() -> list[dict[str, Any]]:
    """The pests as data: `ontology/targets.md` parsed. See `closed_vocabulary`."""
    text = (BUNDLE / "ontology" / "targets.md").read_text(errors="replace")
    return closed_vocabulary(text, target_ids)


def product_types() -> list[dict[str, Any]]:
    """The product types as data: `ontology/product-types.md` parsed. See `closed_vocabulary`.

    Same mechanism as `targets()`, same reason: without the join done here, the
    searcher improvised grep against the `tags:` of each loose datasheet. Measured in
    `lab/logbook.tsv` (row `product_type_quality/manual_audit_n3`): the
    request "an adjuvant", identical across 3 runs, returned a different product
    each time out of the 3 valid candidates, and one run recommended a product without
    the `rooter` tag because it caught it by an agronomy sentence with "root" instead
    of the `tags:` axis. Before that, a closed vocabulary without this join had already
    raised aquacal from 2/3 to 3/3 (row `type_axis`); this is the step that same
    round left noted as pending: "types as data".
    """
    text = (BUNDLE / "ontology" / "product-types.md").read_text(errors="replace")
    return closed_vocabulary(text, tag_ids)


FIELDS = ("title", "state", "tags", "certified_crops", "alternatives")


def frontmatter(text: str) -> dict[str, object]:
    """The frontmatter fields that get queried, without bringing in a YAML parser.

    Reads scalars and dash lists, the two forms the bundle uses in those
    keys. The rest stays in `catalog` and grep reaches it.
    """
    if not text.startswith("---\n"):
        return {}
    body = text[4:].split("\n---", 1)[0]
    data: dict[str, object] = {}
    key = ""
    for line in body.splitlines():
        if line.startswith("  - "):
            if key in FIELDS:
                listing = data.setdefault(key, [])
                if isinstance(listing, list):
                    listing.append(line[4:].strip().strip('"'))
        elif not line.startswith(" ") and ":" in line:
            key, value = (x.strip() for x in line.split(":", 1))
            if value and key in FIELDS:
                data[key] = value.strip('"')
    return data


def agronomy(text: str) -> dict[str, Any]:
    """The `# Agronomy` block parsed, or empty with the reason if it could not be."""
    if "\n# Agronomy" not in text:
        return {}
    after_block = text.split("\n# Agronomy", 1)[1]
    if after_block.count("```") < 2:
        return {"error": "the block has no fenced code"}
    try:
        data = json.loads(after_block.split("```", 2)[1].removeprefix("json"))
    except json.JSONDecodeError as e:
        return {"error": f"invalid JSON: {e}"}
    return data if isinstance(data, dict) else {"error": "the block is not an object"}


def keys(sheet: list[dict[str, Any]]) -> dict[str, str]:
    """From an ontology sheet, the dictionary folded term -> id.

    The id, the label and each alias go in, folding case and accents. If two
    rows claim the same term the first one wins.
    """
    table: dict[str, str] = {}
    for row in sheet:
        for term in (row.get("id", ""), row.get("label", ""), *row.get("alias", [])):
            key = strip_accents(term).lower().strip()
            if key:
                table.setdefault(key, row["id"])
    return table


def resolve(terms: object, sheet: Mapping[str, str]) -> list[str]:
    """The ids of a list of crops written the way the datasheet writes it.

    A term the sheet does not know is kept folded: dropping it would be a
    certified crop disappearing without notice. A scalar gives empty.
    """
    if not isinstance(terms, list):
        return []
    seen: list[str] = []
    for term in terms:
        key = strip_accents(str(term)).lower().strip()
        id_ = sheet.get(key, key)
        if id_ and id_ not in seen:
            seen.append(id_)
    return seen


def record(path: Path, text: str, sheet: Mapping[str, str] | None = None) -> dict[str, Any]:
    """A product as queryable data: what the frontmatter and the `# Agronomy` block already say.

    It is an index, not a source. Nothing is computed or normalized, except
    `crops`: the ids of `certified` resolved through the crops sheet,
    because the id is what filters without depending on the accent.

    `doses[].for` is the override's `match` as it stands (by pest, crop or
    route); flattening it would invent a rule the datasheet does not state. Empty is the
    default regimen.
    """
    front_matter = frontmatter(text)
    agronomy_data = agronomy(text)
    certified = front_matter.get("certified_crops", [])
    doses = [
        {
            "for": {},
            "dose": r.get("dose", {}),
            "route": r.get("route", ""),
            "water": r.get("water_volume", {}),
        }
        for r in agronomy_data.get("default_regimens", [])
    ] + [
        {
            "for": o.get("match", {}),
            "dose": r.get("dose", {}),
            "route": r.get("route", ""),
            "water": r.get("water_volume", {}),
        }
        for o in agronomy_data.get("overrides", [])
        for r in o.get("regimens", [])
    ]
    return {
        "name": path.stem,
        "title": front_matter.get("title", path.stem),
        "state": front_matter.get("state", ""),
        "alternatives": front_matter.get("alternatives", []),
        "path": f"products/{path.name}",
        "tags": front_matter.get("tags", []),
        "certified": front_matter.get("certified_crops", []),
        "crops": resolve(certified, sheet or {}),
        "scope": agronomy_data.get("crop_scope", ""),
        "pests": [
            {"id": t.get("id", ""), "name": t.get("name", ""), "alias": t.get("aliases", [])}
            for t in agronomy_data.get("targets", [])
        ],
        "doses": doses,
        "safety": agronomy_data.get("safety", {}),
        **({"error": agronomy_data["error"]} if agronomy_data.get("error") else {}),
    }


PRODUCT_NOTES: dict[str, str] = {
    "certified": "the crops as the datasheet writes them",
    "crops": "the same ones, as ids of `ontology/crops.md`",
    "alternatives": "on a product no longer sold, the paths of the current ones that replace it",
    "doses.for": "which pests, crops or routes that dose applies to; empty is the default dose",
}
"""What the data from `record` does not say by itself, by field path. `fields.describe` extracts the structure.

A test checks that each path exists in the real records: if `record`
renames a field, the old note fails there and not in the prompt.
"""

VOCABULARY_NOTES: dict[str, str] = {
    "datasheets": "the paths of the products that cover that entry or one of its children",
}
"""The same for `targets` and `product_types`, which have the same shape."""


def products() -> list[dict[str, Any]]:
    """One record per datasheet in `products/`, already parsed. See `record`.

    `old/agro.py` measured that, with this in the REPL, the searcher prefers it over
    grep for the first filter: of 42 queries in a run, 36 started
    with `products` (row `two_steps/baseline` of `lab/logbook.tsv`). It is an
    index derived from the text, not the source: if the index and the datasheet differ,
    the datasheet wins.
    """
    sheet = keys(vocabulary((BUNDLE / "ontology" / "crops.md").read_text(errors="replace")))
    return [
        record(f, f.read_text(errors="replace"), sheet)
        for f in sorted((BUNDLE / "products").glob("*.md"))
        if f.name != "index.md"
    ]


DATASHEETS = "products/"
"""Where the datasheets live in the corpus: the only thing `send_datasheet` sends."""

