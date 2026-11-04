---
type: ontology
schema: wiki/ontology/v1
axis: units
label: "Dose units"
generated: { by: claude-code/claude-opus-5, at: 2026-08-27T07:05:54Z }
---

What the amount of product applied is measured in. There are four and all four come from the dose
tables: liter in 78 rows, kilogram in four, milliliter in the rest, and the gram in a single
datasheet.

The gram came in with the agronomy, not with the dose tables. Corrige doses by water hardness, from
0.05 to 3.00 g per liter, and it is the only datasheet in the catalog that weighs the product in
grams. Without this row its profile does not validate and the whole page falls out of the catalog:
nine doses, a three-concept axis and no warning why.

`cc` goes as an alias and not as a separate concept. A cubic centimeter and a milliliter are the same
measure; the datasheets use both spellings and separating them would make Filmvane and Mixvane seem
to dose differently when they dose the same.

This axis is the one for doses, not for the `Unit` column of `# Presentations`. Units do not go
there but physical descriptors, like the 0.6 x 0.6 meter yellow cloth of Stickvane, and that is another
vocabulary the day it needs closing.

The units of a datasheet's physical properties do not get in. `g/mol` and `g/cm3` appear in the
sodium molybdate, but they describe the substance, not how much is applied.

| id | label | parent | alias | note |
|---|---|---|---|---|
| l | L |  | liter, liters, litre, litres, lt, lts |  |
| ml | mL |  | milliliter, milliliters, cc, cubic centimeter | cc and mL are the same measure |
| kg | kg |  | kilogram, kilograms, kilo, kilos |  |
| g | g |  | gram, grams |  |
