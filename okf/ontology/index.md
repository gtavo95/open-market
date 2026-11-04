# Ontology

The closed vocabularies the pages are curated with. One file per axis, and the file name is the axis
id. The reader skips this index.

Closing an axis has a price: while the file does not exist, that field is free text and nothing
fails. The day it exists, a page that writes a term outside the vocabulary drops out of the catalog.
That is why an axis is closed when someone has curated it, not all at once.

## The ones already here

| axis | concepts | where it came from |
|---|---|---|
| `countries` | 10 | the eight in `# Equivalents`, plus two grouping rows |
| `targets` | 54 | the dose tables, and the deficiencies five nutritionals say they correct |
| `target-types` | 6 | the classes those same tables name |
| `units` | 4 | liter, milliliter and kilogram, plus the gram, which Corrige brought |
| `bases` | 8 | hectare and manzana, plus the four ways of measuring the spray mix |
| `routes` | 6 | foliar, soil with its two forms, and the seedbed |
| `crops` | 116 | the spellings in the dose tables, plus `pastures` |
| `product-types` | 40 | the first line of each datasheet, where the manufacturer classifies itself |

Everything the datasheets name resolves: 8 of 8 countries, the 171 crop spellings filed in the pages,
and what the 38 agronomic profiles name, which is 40 targets, the 6 target classes, the 4 units, 5
bases and the 6 routes. What did not get in is left out on purpose and stated in the prose of its
leaf: two strings that are not crops, and four that are two crops the OCR glued into one cell and
that were split in two when curated.

The four dose axes (`units`, `bases`, `routes`, `target-types`) sat declared and unused from the
moment they were closed. Curating the agronomy is what put them to work, and it is also what moved
them: `targets` gained eleven concepts, `units` one and `bases` one. An axis nobody uses is never
wrong.

## The facets of product-types

`product-types` is not a hierarchy but five facets: `function`, `nature`, `role`, `registration` and
`suitability`. A page carries one tag per facet that applies to it and none is mandatory.

It is this way because the obvious agrochemical taxonomy does not classify this catalog. BIOMET 70 EW
is insecticide, microbial and approved for organic at the same time, and forcing it to choose which
of the three is "the" type loses the other two.

## The certified crops

`crops` is not the list of where a product works, it is the list of where it is **certified**.
Products work on any crop; the backing of the registration reaches as far as the datasheet does.

The page states the two facts separately: `crop_scope` in the agronomic profile, which is the
commercial truth, and `certified_crops` in the frontmatter with the datasheet's list, which is the
registration's. The certification is the same in all eight countries, so there is a single list per
product and it has no country dimension.

`certified_crops` is a field the `wiki` module does not have yet. Until it does, a page that writes
it carries it as an unknown frontmatter key, which the reader ignores without breaking.

All 38 pages already have it. 24 carry the list from their datasheet, 5 say `all_crops` because the
datasheet says "all crops", and 9 say `not_applicable`: adjuvants, traps, the rodenticide and the raw
material are not certified by crop. That is 653 terms in 171 distinct spellings, and all 171 resolve.

The two `not_applicable` are not the same. The one in `certified_crops` says "this product is not
certified by crop" and coexists with `crop_scope: all_crops`. The one in `crop_scope` says "this
profile does not talk about crops" and the module only accepts it in a non-agricultural profile,
which among the 38 pages is just one: Aquavane, which treats swimming pools.

`crop_scope: all_crops` is what the 37 agricultural pages say, whether they have a list or not,
because the product works on any crop and the list is the registration's. Until Sep 13, 2026 the 24
with a list said `listed_crops_only` and repeated the list in the profile's `crops`, contrary to what
this same leaf states above; that day they were aligned and `crops` left the profile.

## The growth rule

A concept gets in if a datasheet names it or a customer asked about it. Not from an agronomy manual.
Without that, "closed" is just a word.

The fine cut: if the term names a function someone asks for, it is a concept; if it is another way of
saying the same thing, it is an alias. "Rooter" and "fruit sizer" are concepts. "Vigor booster" and
"revitalizer" are ways of saying biostimulant.

What was decided to be left out stays written in the leaf of its axis, not here: why there is no
`bacteria` in `target-types`, why `injection` is not a route, why `cc` is an alias of `mL` and not a
concept.
