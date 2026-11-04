"""A small bundle shaped like the real one, so as not to depend on `okf/`."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from core_agent.world.catalog import CATALOG
from host import Catalog, load

ISARIA = """---
title: "Hyphavane"
state: active
tags:
  - insecticide
  - organic-approved
certified_crops:
  - Tomato
  - Sweet pepper
description: entomopathogen
---

# Summary

Entomopathogenic fungus for sucking pests.

# Agronomy

```json
{json}
```

# Datasheet

Apply at dusk.
"""

AGRONOMY = {
    "crop_scope": "registered_only",
    "targets": [
        {"id": "thrips", "name": "Thrips", "kind": "insect", "aliases": ["Frankliniella occidentalis"]},
        {"id": "myzus", "name": "Myzus", "kind": "insect", "aliases": ["Myzus persicae"]},
    ],
    "default_regimens": [
        {"dose": {"min": 1.0, "max": 1.5, "unit": "l", "basis": "ha"}, "route": "foliar", "water_volume": {"min": 200, "unit": "l/ha"}}
    ],
    "overrides": [
        {
            "match": {"crops": ["banana"]},
            "regimens": [{"dose": {"min": 2.0, "max": 2.0, "unit": "l", "basis": "ha"}, "route": "foliar"}],
        }
    ],
    "safety": {"water_ph": "5.5-7", "incompatibilities": ["copper fungicides"], "days_to_harvest": 0},
}

RODENTICIDE = """---
title: Rodenticide
tags:
  - rodenticide
---

No agronomy block yet.
"""

TARGETS = """---
type: ontology
axis: targets
---

Prose up top | with bars | that is not a table.

| id | label | parent | alias | note |
|---|---|---|---|---|
| sucking-pests | Sucking pests |  | sucking pest | grouping |
| aphid | Aphid | sucking-pests | aphids, aphididae |  |
| myzus | Myzus | aphid | myzus spp. |  |
| thrips | Thrips | sucking-pests | thrip, Frankliniella |  |
| leafcutter-ant | Leafcutter ant |  | zompopo |  |
"""

CROPS = """| id | label | parent | alias | note |
|---|---|---|---|---|
| solanaceae | Solanaceae |  | solanaceous |  |
| tomato | Tomato | solanaceae | jitomate |  |
| pepper | Pepper | solanaceae | sweet pepper, bell pepper |  |
| sugarcane | Sugarcane |  |  |  |
"""

TYPES = """| id | label | parent | alias | note |
|---|---|---|---|---|
| insecticide | Insecticide |  | insecticides |  |
| rodenticide | Rodenticide |  | raticide |  |
"""


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    products = tmp_path / "products"
    products.mkdir()
    (products / "hyphavane.md").write_text(ISARIA.replace("{json}", json.dumps(AGRONOMY)))
    (products / "rodenticide.md").write_text(RODENTICIDE)
    (products / "index.md").write_text("# Index\n")
    ontology = tmp_path / "ontology"
    ontology.mkdir()
    (ontology / "targets.md").write_text(TARGETS)
    (ontology / "crops.md").write_text(CROPS)
    (ontology / "product-types.md").write_text(TYPES)
    company = tmp_path / "company_info"
    company.mkdir()
    (company / "payments.md").write_text("# Payments\n\nPayment link or transfer.\n")
    (company / "bank-accounts.md").write_text("# Bank accounts\n\nBanco Industrial, account 123.\n")
    shutil.copytree(CATALOG / "governance", tmp_path / "governance")
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "isaria.md").write_text("raw OCR")
    (tmp_path / "index.md").write_text("root")
    return tmp_path


@pytest.fixture
def small_catalog(bundle: Path) -> Catalog:
    return load(bundle)


_NO_PROD_CATALOG = not (Path(__file__).resolve().parents[1] / "okf/products/reapvane.md").exists()
_NEED_PROD_CATALOG = set((Path(__file__).parent / "need_prod_catalog.txt").read_text().split())


def pytest_collection_modifyitems(config, items):
    if not _NO_PROD_CATALOG:
        return
    skip = pytest.mark.skip(reason="reads the production catalog; the demo branch carries the fictional bundle")
    for item in items:
        if item.nodeid in _NEED_PROD_CATALOG:
            item.add_marker(skip)
