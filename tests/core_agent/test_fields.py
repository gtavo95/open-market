"""The REPL description comes from the data: the fields are not written by hand, and the notes, which are, point at fields that exist."""

from __future__ import annotations

from core_agent.roles.searcher import SEARCHER
from core_agent.world.catalog import PRODUCT_NOTES, VOCABULARY_NOTES, product_types, products, targets
from core_agent.world.fields import describe, paths, unknown

DATASHEETS = [
    {"name": "larvane", "state": "current", "crops": ["tomato", "corn"], "doses": [{"for": {"target_ids": ["thrips"]}, "min": 1.0}]},
    {"name": "kelthar", "state": "discontinued", "crops": "all_crops", "doses": [{"for": {}, "min": 2}]},
]


class TestDescribe:
    def test_one_field_per_line_with_its_type_and_an_example(self) -> None:
        text = describe(DATASHEETS)

        assert '- `name`: text: "larvane" or "kelthar"' in text
        assert '- `state`: text: "current" or "discontinued"' in text
        assert "`doses`: list of dicts with `for` (dict with `target_ids` (list of texts)), `min` (number)" in text

    def test_a_field_of_two_types_says_both(self) -> None:
        assert '- `crops`: text: "all_crops" or list of texts' in describe(DATASHEETS)

    def test_the_note_goes_beside_its_field_and_inside_what_is_nested(self) -> None:
        text = describe(DATASHEETS, {"name": "the id", "doses.for": "which pests"})

        assert '"kelthar" — the id' in text
        assert "(dict with `target_ids` (list of texts); which pests)" in text

    def test_a_new_field_shows_up_without_touching_anything(self) -> None:
        assert "`price`" in describe([*DATASHEETS, {"name": "x", "price": 250.0}])

    def test_the_paths_include_what_is_nested(self) -> None:
        assert {"doses", "doses.for", "doses.for.target_ids", "doses.min"} <= paths(DATASHEETS)
        assert unknown(DATASHEETS, {"doses.for": "", "doses.crop": ""}) == {"doses.crop"}


class TestTheCatalogNotes:
    def test_each_product_note_points_at_a_field_of_record(self) -> None:
        assert unknown(products(), PRODUCT_NOTES) == set(), "a note was left pointing at a field `record` no longer builds"

    def test_each_vocabulary_note_points_at_a_field(self) -> None:
        assert unknown(targets(), VOCABULARY_NOTES) == set()
        assert unknown(product_types(), VOCABULARY_NOTES) == set()

    def test_the_contract_carries_the_real_fields(self) -> None:
        for key in products()[0]:
            assert f"`{key}`" in SEARCHER, f"`{key}` is in `products` and the contract does not say it"
