---
type: product
title: "Silverstrike 45 EW"
tags:
  - insecticide
  - entomopathogen
  - organic-approved
  - ipm-approved
certified_crops:
  - Onion
  - Green Onion
  - Bell Pepper
  - Jalapeño Pepper
  - Tomato
  - Potato
  - Strawberry
  - Avocado
  - Melon
  - Watermelon
org_id: demo
normalized_name: silverstrike 45 ew
wiki_id: "silverstrike 45 ew"
bucket_path: ""
state: current
reference_id: "Silverstrike 45EW.pdf"
generated:
  - { by: claude-code/claude-opus-5-5, at: 2026-10-09T12:00:00-06:00 }
sources:
  - id: datasheet
    resource: "/raw/Silverstrike 45EW.pdf"
    title: "Manufacturer's datasheet"
  - id: pricelist
    resource: "/raw/prices/demo_precios_2026.pdf"
    title: "Price list 2026"
---

<!-- Fictional product of the demo bundle. There is no PDF in raw/: the datasheet below is handwritten. -->

# Summary
Contact and ingestion microbial insecticide against thrips, with Metarhizium anisopliae, Beauveria
bassiana and Saccharopolyspora spinosa. Registered against Thrips tabaci and Frankliniella
occidentalis on onion, pepper, tomato, potato, strawberry, avocado and cucurbits. Zero days to harvest
and approved for organic farming. Thrips is recognized by little elongated bugs 1 to 2 mm long on the
underside of the leaf and in the flowers, and by the silver spots with little black dots it leaves
on the leaf.

# Presentations
| Size | Unit | Price | Price/unit | Currency | SAP Code |
|---|---|---|---|---|---|
| 1 | L | 235.00 |  | GTQ |  |
| 20 | L | 4,600.00 |  | GTQ |  |

# Ingredients
- Metarhizium anisopliae (12.00% m/v)
- Beauveria bassiana (8.00% m/v)
- Saccharopolyspora spinosa (25.00% m/v)

# Equivalents
| Country | Name |
|---|---|
| Guatemala | SILVERSTRIKE 45 EW |
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
      "id": "thrips-tabaci",
      "name": "Thrips",
      "kind": "insect",
      "aliases": ["Thrips tabaci"],
      "source_refs": ["datasheet"]
    },
    {
      "id": "frankliniella-occidentalis",
      "name": "Thrips",
      "kind": "insect",
      "aliases": ["Frankliniella occidentalis"],
      "source_refs": ["datasheet"]
    }
  ],
  "overrides": [
    {
      "id": "onion-thrips",
      "match": {"target_ids": ["thrips-tabaci"]},
      "regimens": [
        {
          "id": "onion-thrips",
          "dose": {"min": 1.2, "unit": "l", "basis": "ha"},
          "route": "foliar",
          "water_volume": {"min": 200, "unit": "l", "basis": "ha"},
          "source_refs": ["datasheet"]
        }
      ],
      "source_refs": ["datasheet"]
    },
    {
      "id": "western-flower-thrips",
      "match": {"target_ids": ["frankliniella-occidentalis"]},
      "regimens": [
        {
          "id": "western-flower-thrips",
          "dose": {"min": 1.0, "max": 1.8, "unit": "l", "basis": "ha"},
          "route": "foliar",
          "water_volume": {"min": 200, "unit": "l", "basis": "ha"},
          "source_refs": ["datasheet"]
        }
      ],
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
  "sources": [{"id": "datasheet", "kind": "technical_datasheet", "ref": "/raw/Silverstrike 45EW.pdf"}]
}
```

# Datasheet
## TECHNICAL DATASHEET

## MICROBIAL INSECTICIDE

Concentrated aqueous emulsion.

MODE OF ACTION: SILVERSTRIKE 45 EW acts by contact and ingestion on insects of the order Thysanoptera.
The microorganisms germinate on the insect, degrade its cuticle and colonize it until it stops
feeding.

BENEFITS:

- Fits into integrated pest management.
- Approved for organic and conventional farming.
- Zero days to harvest.

HOW TO RECOGNIZE THRIPS: elongated and very small insects (1 to 2 mm), yellowish, brown or black, that
hide on the underside of the leaf, in the shoots and inside the flowers. They scrape the tissue and
suck the sap: the leaf is left with silver or bronze spots and little black dots (excrement). With a
heavy attack the leaves curl and dry from the edge, and flowers and fruit come out deformed or with
silver scars. To confirm it, shake a shoot over a sheet of white paper.

HOW TO APPLY: check that the water pH is between 5.5 and 7.5. Shake the container, prepare a premix
in 5 liters of clean chlorine-free water and pour it into the half-full tank, with the agitation on.

RECOMMENDATIONS: apply in the cool hours, from 5:00 to 9:00 and from 16:00 on. Do not apply 72 hours
before or after bactericides and fungicides.

## USE RECOMMENDATIONS:

| Crop | Pest | Dose |
|---|---|---|
| Onion, Green Onion | Thrips (Thrips tabaci) | 1.2 L/ha in 200 liters of water. (0.8 L/Mz in 140 liters of water) |
| Bell Pepper, Jalapeño Pepper, Tomato, Potato | Thrips (Frankliniella occidentalis) | 1.0 - 1.8 L/ha in 200 liters of water. (0.7 - 1.3 L/Mz in 140 liters of water) |
| Strawberry, Avocado | Thrips (Frankliniella occidentalis) | 1.0 - 1.8 L/ha in 200 liters of water. (0.7 - 1.3 L/Mz in 140 liters of water) |
| Melon, Watermelon | Thrips (Frankliniella occidentalis) | 1.0 - 1.8 L/ha in 200 liters of water. (0.7 - 1.3 L/Mz in 140 liters of water) |
