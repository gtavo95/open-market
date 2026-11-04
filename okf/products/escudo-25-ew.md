---
type: product
title: "Escudo 25 EW"
tags:
  - fungicide
  - microbial
  - organic-approved
  - ipm-approved
certified_crops:
  - Zucchini
  - Güicoy
  - Cucumber
  - Watermelon
  - Melon
org_id: demo
normalized_name: escudo 25 ew
wiki_id: "escudo 25 ew"
bucket_path: ""
state: current
reference_id: "Escudo 25EW.pdf"
generated:
  - { by: claude-code/claude-opus-5-5, at: 2026-10-09T12:00:00-06:00 }
sources:
  - id: datasheet
    resource: "/raw/Escudo 25EW.pdf"
    title: "Manufacturer's datasheet"
  - id: pricelist
    resource: "/raw/prices/demo_precios_2026.pdf"
    title: "Price list 2026"
---

<!-- Fictional product of the demo bundle. There is no PDF in raw/: the datasheet below is handwritten. -->

# Summary
Contact microbial fungicide with Trichoderma harzianum, Bacillus subtilis and Lecanicillium lecanii,
for foliage fungi. Registered on cucurbits against downy mildew (Pseudoperonospora cubensis) and
powdery mildew (Erysiphe cichoracearum). 1.25 L/ha foliar in 250 L of water. Zero days to harvest and
approved for organic farming.

# Presentations
| Size | Unit | Price | Price/unit | Currency | SAP Code |
|---|---|---|---|---|---|
| 1 | L | 240.00 |  | GTQ |  |
| 20 | L | 4,400.00 |  | GTQ |  |

# Ingredients
- Trichoderma harzianum (12.00% m/v)
- Bacillus subtilis (5.00% m/v)
- Lecanicillium lecanii (8.00% m/v)

# Equivalents
| Country | Name |
|---|---|
| Guatemala | ESCUDO 25 EW |
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
  "targets": [
    {
      "id": "downy-mildew",
      "name": "Downy mildew",
      "kind": "fungus",
      "aliases": ["Pseudoperonospora cubensis"],
      "source_refs": ["datasheet"]
    },
    {
      "id": "erysiphe-cichoracearum",
      "name": "Powdery mildew",
      "kind": "fungus",
      "aliases": ["Erysiphe cichoracearum"],
      "source_refs": ["datasheet"]
    }
  ],
  "default_regimens": [
    {
      "id": "foliar",
      "dose": {"min": 1.25, "unit": "l", "basis": "ha"},
      "route": "foliar",
      "water_volume": {"min": 250, "unit": "l", "basis": "ha"},
      "source_refs": ["datasheet"]
    }
  ],
  "safety": {
    "water_ph_min": 5.5,
    "water_ph_max": 7.5,
    "chlorine_free_water": true,
    "incompatibilities": ["fungicides, fertilizers or surfactants without a prior compatibility test"],
    "separation_hours": 72,
    "phytotoxicity": "Causes no phytotoxicity at the recommended doses",
    "notes": ["Zero days to harvest", "Do not apply 72 hours before or after bactericides and fungicides"]
  },
  "sources": [{"id": "datasheet", "kind": "technical_datasheet", "ref": "/raw/Escudo 25EW.pdf"}]
}
```

# Datasheet
## TECHNICAL DATASHEET

## MICROBIAL FUNGICIDE

Concentrated aqueous emulsion.

MODE OF ACTION: ESCUDO 25 EW acts by contact. The microorganisms compete with the fungus for space
and nutrients on the leaf and degrade its cell wall.

BENEFITS:

- Fits into integrated pest management.
- Approved for organic and conventional farming.
- Zero days to harvest.

HOW TO APPLY: check that the water pH is between 5.5 and 7.5. Shake the container, prepare a premix
in 5 liters of clean chlorine-free water and pour it into the half-full tank, with the agitation on.

RECOMMENDATIONS: apply in the cool hours. Do not apply 72 hours before or after bactericides and
chemical fungicides.

## USE RECOMMENDATIONS:

| Crop | Disease | Dose |
|---|---|---|
| Zucchini, Güicoy, Cucumber | Downy mildew (Pseudoperonospora cubensis), Powdery mildew (Erysiphe cichoracearum) | 1.25 L/ha in 250 liters of water. (0.9 L/Mz in 175 liters of water) |
| Watermelon, Melon | Downy mildew (Pseudoperonospora cubensis), Powdery mildew (Erysiphe cichoracearum) | 1.25 L/ha in 250 liters of water. (0.9 L/Mz in 175 liters of water) |
