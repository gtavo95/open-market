---
type: product
title: "Raíz Viva"
tags:
  - mycorrhiza
  - solubilizer
  - organic-approved
  - fertilizer-related
certified_crops: all_crops
org_id: demo
normalized_name: raiz viva
wiki_id: "raiz viva"
bucket_path: ""
state: current
reference_id: "Raiz Viva.pdf"
generated:
  - { by: claude-code/claude-opus-5-5, at: 2026-10-09T12:00:00-06:00 }
sources:
  - id: datasheet
    resource: "/raw/Raiz Viva.pdf"
    title: "Manufacturer's datasheet"
  - id: pricelist
    resource: "/raw/prices/demo_precios_2026.pdf"
    title: "Price list 2026"
---

<!-- Fictional product of the demo bundle. There is no PDF in raw/: the datasheet below is handwritten. -->

# Summary
Consortium of bacteria and mycorrhizal fungi that widens the soil zone the root explores. It is
applied to the soil, 1.5 to 2.5 L/ha, on any crop. It speeds up the growth of the root system and
with it the uptake of nutrients and water. Zero days to harvest and approved for organic farming. It
helps the plant recover faster after a pest attack, because the root goes back to taking up water
and nutrients sooner.

# Presentations
| Size | Unit | Price | Price/unit | Currency | SAP Code |
|---|---|---|---|---|---|
| 1 | L | 220.00 |  | GTQ |  |
| 20 | L | 4,100.00 |  | GTQ |  |

# Ingredients
- Pseudomonas fluorescens (5.00% m/v)
- Azotobacter vinelandii (8.00% m/v)
- Glomus intraradices (12.00% m/v)
- Gigaspora margarita (10.00% m/v)

# Equivalents
| Country | Name |
|---|---|
| Guatemala | RAÍZ VIVA |
| El Salvador |  |
| Nicaragua |  |
| Honduras |  |
| Costa Rica |  |
| Panamá |  |
| Belice |  |
| R. Dominicana |  |

# Agronomy
```json
{
  "schema": "product/agronomy/v1",
  "is_biological": true,
  "application_domains": ["agriculture"],
  "crop_scope": "all_crops",
  "default_regimens": [
    {
      "id": "general",
      "dose": {"min": 1.5, "max": 2.5, "unit": "l", "basis": "ha"},
      "route": "soil",
      "source_refs": ["datasheet"]
    }
  ],
  "safety": {
    "water_ph_min": 5.5,
    "water_ph_max": 7.5,
    "chlorine_free_water": true,
    "min_humidity_pct": 60,
    "incompatibilities": ["fungicides, fertilizers or surfactants without a prior compatibility test"],
    "separation_hours": 72,
    "phytotoxicity": "Causes no phytotoxicity at the recommended doses",
    "notes": ["Zero days to harvest", "Do not apply 72 hours before or after bactericides and fungicides"]
  },
  "sources": [{"id": "datasheet", "kind": "technical_datasheet", "ref": "/raw/Raiz Viva.pdf"}]
}
```

# Datasheet
## TECHNICAL DATASHEET

## MYCORRHIZAL INOCULANT

Suspension concentrate.

MODE OF ACTION: the mycorrhizal fungi colonize the root and extend their hyphae into the soil, where
they take up phosphorus, water and micronutrients the root alone cannot reach. The bacteria solubilize
phosphorus and fix nitrogen.

BENEFITS:

- More root and more soil volume explored.
- Approved for organic and conventional farming.
- Compatible with fertilizers.
- Zero days to harvest.

HOW TO APPLY: to the soil, by drench or through irrigation, with the soil at 60 % humidity or more.
Water with pH between 5.5 and 7.5 and no chlorine.

## USE RECOMMENDATIONS:

| Crop | Target | Dose |
|---|---|---|
| All crops | Root development and nutrient uptake | 1.5 - 2.5 L/ha to the soil. (1.0 - 1.75 L/Mz) |
