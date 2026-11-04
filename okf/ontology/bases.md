---
type: ontology
schema: wiki/ontology/v1
axis: bases
label: "Dose bases"
generated: { by: claude-code/claude-opus-5, at: 2026-08-27T07:05:54Z }
---

What the dose is measured against. Without a basis, a number says nothing: 1.5 L is a dose per
hectare or a whole drum of mix depending on what it is read against.

There are two families and they are not alike. Products applied to the crop dose by surface.
Adjuvants dose by spray volume, proportional to the mix and not the land, because what they do is
modify the water.

**The dose is filed in hectares.** Each datasheet gives the same dose twice, in hectares and in
manzanas, so choosing one loses nothing and keeping both lets them diverge in the next edition. `mz`
stays in the vocabulary anyway, so that whoever asks in manzanas resolves.

The spray-volume ones are not converted. The datasheet says "per drum" and that is how it is filed:
it is how the applicator really measures, with the drum in front of them.

The spray mix is not always water. Mixvane gives four doses and the fourth is per liter of oil, for
oily emulsions. It hangs from the same family because it behaves the same, proportional to the mix
and not the land, and reading it as if it were water gives the right dose against the wrong liquid.

| id | label | parent | alias | note |
|---|---|---|---|---|
| surface | Surface |  | area | our grouping |
| ha | Hectare | surface | hectare, hectares, has | the dose is filed here |
| mz | Manzana | surface | manzana, manzanas | 1 mz is about 0.70 ha. The datasheets round the conversion |
| spray-volume | Spray volume |  | spray mix, water volume, mix water | our grouping |
| liter-of-water | Liter of water | spray-volume | l of water, per liter of water |  |
| hundred-liters-of-water | 100 liters of water | spray-volume | every 100 liters of water, 100 l of water |  |
| drum | Drum | spray-volume | 200 liter drum, per drum | a drum is 200 liters in the Wetvane datasheet |
| liter-of-oil | Liter of oil | spray-volume | l of oil, per liter of oil | only Mixvane, for emulsions with oil |
