"""What comes out of the bundle: the text for `grep`, how many datasheets there are and the voice that answers.

The parsers (frontmatter, the agronomy block, the ontology, the index) belong to
`core_agent/world/catalog.py` and are tested in catalejo.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import core_agent
from core_agent.world import catalog
from host import Catalog, load


class TestLoad:
    def test_products_ontology_and_company_with_their_path_up_front(self, bundle: Path) -> None:
        """`company_info/` has come in since Sep 16, 2026: the CONTRACT cites `payments.md`."""
        text = load(bundle).text

        assert "=== products/hyphavane.md ===" in text
        assert "=== ontology/targets.md ===" in text
        assert "=== company_info/payments.md ===" in text and "account 123" in text
        assert "raw OCR" not in text
        assert "=== index.md ===" not in text
        assert text.startswith("=== company_info/")

    def test_points_the_agro_bundle_at_the_service_one(self, bundle: Path) -> None:
        """The agent reads the `BUNDLE` of `core_agent.world.catalog` on each query: loading is what moves it from the sample one to this one."""
        load(bundle)

        assert catalog.BUNDLE == bundle
        assert [p["name"] for p in core_agent.products()] == ["hyphavane", "rodenticide"]

    def test_without_bundle_fails_with_the_path(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="bundle does not exist"):
            load(tmp_path / "nothing")

    def test_a_directory_without_datasheets_also_fails(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="has no datasheets"):
            load(tmp_path)


class TestCatalog:
    def test_the_datasheets_do_not_count_the_index(self, small_catalog: Catalog) -> None:
        assert small_catalog.sheets == 2

    def test_without_voice_md_the_voice_is_empty(self, small_catalog: Catalog) -> None:
        assert small_catalog.voice == ""

    def test_the_voice_is_voice_md_at_the_bundle_root(self, bundle: Path) -> None:
        (bundle / "voice.md").write_text("You are the advisor of Insumos del Sur.\n")

        cat = load(bundle)

        assert cat.voice == "You are the advisor of Insumos del Sur."
        assert "Insumos del Sur" not in cat.text, "the voice is not corpus: the searcher neither greps nor cites it"

    def test_the_frontmatter_of_voice_md_does_not_enter_the_voice(self, bundle: Path) -> None:
        """The okf hook asks for frontmatter in every `.md`; the writer reads only what is below."""
        (bundle / "voice.md").write_text('---\ntype: reference\ntitle: "The voice"\n---\n\nYou are the advisor of Insumos del Sur.\n')

        assert load(bundle).voice == "You are the advisor of Insumos del Sur."
