---
name: curate-page
description: Completes a skeleton product page with tags, presentations, ingredients and an agronomic profile. Use when a page is empty or freshly generated, when someone asks to load prices or classify products, or when verify.sh reports pending items.
---

# Curating a page

`ingest.sh` leaves the datasheet text inside `# Datasheet` and the other sections empty. Curating is
filling them. It is where the page stops being a converted PDF and becomes a product that can be
searched, compared and quoted.

`FORMAT.md` has the exact format of each section. Read it before writing the first one.

## Every piece of data comes from the datasheet or from the person

This is the rule that orders everything else. A farm-inputs bot answers doses, re-entry intervals and
incompatibilities. Data invented here ends up on a real crop.

When something is not in the datasheet, there are two honest ways out: ask the person, or leave the
field out. The reader distinguishes "not declared" from "declared as zero", so omitting a field is a
valid and complete answer. A plausible dose deduced from another product of the same family is not.

Prices are **never** in a datasheet. They come from a price list or from the person.

## Steps

### 1. Read the whole datasheet

`# Datasheet` in the page, and `raw/md/<slug>.md` if you want the untrimmed text.

Note what you will be able to fill in and what not. A foliar fertilizer datasheet brings no control
targets; an insecticide one does.

It is done when you can say, for each empty section, whether the datasheet covers it or you need to
ask.

### 2. Fix the identity

`ingest.sh` derived `title`, `normalized_name` and `wiki_id` from the PDF file name, which is a guess.
`Escudo 25EW.pdf` came out as `escudo 25ew` when the commercial name is ESCUDO 25 EW and the right
value is `escudo 25 ew`.

Look for the commercial name in the body of the datasheet, which is where the manufacturer writes it
correctly. Correct `title`, and derive `normalized_name` from it: lowercase, accents folded, spaces
collapsed.

This comes first for a reason: `normalized_name` is the join key. When it is wrong, the product
exists and searching by name returns empty. It does not fail, it does not find.

### 3. Classify into tags

Tags come from `ontology/product-types.md`, which is a **closed** vocabulary: a value that is not
there takes the page out of the catalog.

If the axis does not exist yet, create the file first. An ontology leaf is frontmatter with
`type: ontology`, `schema: wiki/ontology/v1` and `axis: product-types`, plus a table of
`id | label | parent | alias | note`. The `parent` is what makes it useful: a query for "fungicide"
reaches "systemic fungicide" without repeating the row.

Propose the missing ids and confirm them with the person before adding them. A closed vocabulary
that grows without judgment stops being closed.

### 4. Ingredients

They come from the datasheet, almost always under "Composition" or "Guaranteed minimum content". One
ingredient per line with its percentage: `- Difenoconazol (25%)`.

### 5. Presentations

Ask. The datasheet does not have them.

You need size, unit, price and currency for each sellable package. Leave `Price/unit` empty: it is
re-derived. A blank price cell means no price, and it is preferable to a zero, which claims the
product is free.

If the person does not have the list at hand, leave the table with its header and move on. The page
works without prices; what does not work is a wrong price.

When the prices go in, their source goes in too. Add the pricelist entry to the frontmatter's
`sources`, with `id: pricelist`, the list's `resource` and the `page` you took them from. A price
without its sheet is a number nobody can audit in six months. `ingest.sh` only writes the datasheet
entry, so this one is yours to add.

### 6. Agronomic profile

The most expensive section and the one that pays the most: it is what turns "what works for whitefly
on tomato?" into a query answered with data instead of with text similarity.

The raw material is the datasheet's usage recommendations table. `FORMAT.md` has a complete example
and the rules validated on read.

Each dose carries its `source_refs` pointing to the `sources` entry it came from. That is what lets
the data be audited later, when nobody remembers where it came from.

### 7. Sign the page

Change `generated` from `process:ingest.sh` to `human:<id>` with the day's date, in ISO 8601 with an
offset:

```yaml
generated: { by: human:gustavo, at: 2026-08-27T10:15:00-06:00 }
```

It is what distinguishes a curated page from a skeleton, and it is the only thing in the frontmatter
that says so. While it still names ingest.sh, `verify.sh` reports it as pending curation however full
it is.

`verified` is something else and does not go here. It confirms the content against its sources, and
curating is not confirming: the `# Datasheet` is still OCR nobody compared with the PDF. It gets added
the day someone really audits the page, and then it carries the actor and date of that review, not
this one.

### 8. Summary

One or two lines: what the product is and what it is used for. It is the first thing a person sees
on the card.

### 9. Verify

```
./verify.sh products/<slug>.md
```

Zero ERROR, and the pending line now without the fields you filled in.

Close by saying what stayed pending and why: "prices missing, the person sends them on Monday" is a
finished result. "Agronomy missing" on its own is not.

## Curating many at once

`./verify.sh` with no arguments prints the dashboard of everything pending.

Go product by product, not field by field. Curating the tags of the 40 pages and then starting over
for the prices forces you to reread the 40 datasheets twice. Finishing a page end to end reads each
one once, and leaves usable products from day one instead of 40 half-done pages.

Group by family when you can: five insecticides from the same manufacturer share datasheet structure,
vocabulary and sometimes the dose table.
