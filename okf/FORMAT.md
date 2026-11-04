---
type: reference
title: "The format of a page"
description: "Frontmatter, sections and tables the OKF reader expects in a product page."
generated: { by: claude-code/claude-opus-5, at: 2026-08-27T06:32:01Z }
---

# The format of a page

Reference for the OKF document the `wiki` module reads. It holds for any bundle forked from this one.

A malformed page does not break anything loudly: the reader discards it as a `PageError` and moves
on with the rest. The file exists, the product does not. That is why `verify.sh` separates **ERROR**
from **pending**: the first erases a product from the catalog, the second is data that is not there
yet.

## Frontmatter

Opens and closes with `---` on its own line. Unknown keys are ignored, so adding your own is safe.

| key | what the reader does with it |
|---|---|
| `type` | the OKF SPEC asks for it; the reader discards it |
| `title` | the commercial name, the one people use to talk about the product |
| `tags` | the product's types, one per line with `- `. The tenant's CLOSED vocabulary |
| `certified_crops` | where it is certified, not where it works. CLOSED vocabulary. See below |
| `normalized_name` | the join key. See below, it is the one that hurts the most |
| `wiki_id` | stable identity of the page; survives the file being renamed |
| `org_id` | decorative in the file: the reader overwrites it with the tenant that opened it |
| `bucket_path` | `gs://` handle of the image or the datasheet, never a signed URL |
| `state` | empty or `current`, `out_of_stock`, `discontinued`, `withdrawn` |
| `alternatives` | in a product no longer sold, the paths of the current ones that take its place. See below |
| `reference_id` | which document the page came from |
| `sources` | where each piece of data on the page comes from. See below |
| `generated` | who produced the content and when. See below |
| `verified` | who confirmed it against its sources. Almost always absent, and that says something |

**`normalized_name` is lowercase, accents folded and spaces collapsed.** It is what `okf.NormName`
computes, and it has to come out exactly the same on both sides: if the page normalizes differently
from the search, the join does not fail, it returns empty. A product that exists and never shows up.

`ingest.sh` derives it from the PDF name, which is a guess. `Escudo 25EW.pdf` gives `escudo 25ew`,
but the commercial name is ESCUDO 25 EW and the right value is `escudo 25 ew`. Correcting it is part
of curating.

## Sections

The names are exact and they are these seven:

`# Summary` · `# Types` · `# Presentations` · `# Ingredients` · `# Equivalents` ·
`# Agronomy` · `# Datasheet`

A `# ` with any other name does not open a section: its content stays stuck to the previous section
and is lost from view. It is the easiest failure to commit editing by hand and the quietest.

**Inside `# Datasheet` the rule is inverted.** There the text is free and a reserved heading counts
as content, not as a new section. That is why `ingest.sh` lowers by one level the `# ` that come from
the PDF: so the datasheet reads as text even if the manufacturer titled a part "Presentations".

`# Datasheet` is the last one and nothing closes it: the PDF's text runs to the end of the file.
There was an eighth name, `# Citations`, which was the only one that cut it. It no longer exists:
provenance moved to the frontmatter.

### Presentations

```
| Size | Unit | Price | Price/unit | Currency |
|---|---|---|---|---|
| 1 | L | 300.00 |  | GTQ |
| 4 | L | 1,000.00 |  | GTQ |
```

The Price/unit column stays empty: it is re-derived from Price ÷ Size. So is the product's minimum
price. Writing them by hand creates a second copy of the rule that can diverge from the first.

A blank price cell is **no price**, not zero. A zero is a statement about price.

**`SAP Code` goes last and is optional.** It is the article's `ItemCode` in the company's SAP Business
One (`PT0089`), the one carried by the draft order the agent creates. Blank means that presentation
has no article in SAP or that which one is still unconfirmed; the draft then falls back to the
generic article. They are loaded by the host's SAP tooling (`match` proposes, a
person approves, `apply` writes) and can be corrected by hand. It goes at the end because the reader
looks columns up by name and none of the others contains "sap".

**Today it is better to omit the whole row than to leave the price blank.** The reader reads it
anyway, but `minPrices` takes that zero as the product's minimum and the page ends up saying "from
Q0.00". It is a bug in the `wiki` module (`internal/okf/normalize.go`: `priceMin` lacks the
`p.Price > 0` guard that `perUnitMin` does have). Once it is fixed, the blank row goes back to being
the right way to say "this size exists and has no price".

#### A product sold by the box

A trap or a roll is not sold by the liter: the price list brings color, dimensions and units per box.
For that there are three more columns, and the reader locates them by name, so pages that do not use
them keep reading the same.

```
| Size | Unit | Presentation | Base quantity | Base unit | Price | Price/unit | Currency |
|---|---|---|---|---|---|---|---|
| 100 | Yellow sheet 0.6 mt X 0.6 mt | box | 100 | sheet | 850.00 |  | GTQ |
| 12 | Yellow roll 0.10 mt X 50 mt | box | 12 | roll | 1,920.00 |  | GTQ |
```

`Size` is how many units the box holds, and that gives the per-unit that matters to a customer: Q8.50
the trap, not Q850 the bundle. `Unit` keeps the physical descriptor —color and measurements— which is
how the price list names it.

Two cautions about column order. `Size` goes **first**: the reader looks it up by name and the lookup
does not find it (it compares against a name with folded accents), so it falls back to position 0.
And `Price` goes **before** `Price/unit`, because it looks for the first column that contains "price"
and would otherwise keep the wrong one.

### Ingredients

`- Difenoconazol (25%)`, one per line. Without a percentage is fine too.

### Equivalents

Local name by country. A country with an empty name means it is not sold there.

### Certified crops

It goes in the frontmatter, not in the body, because it is not page prose but the key a catalog is
filtered by.

```yaml
certified_crops:
  - Bell Pepper
  - Jalapeño Pepper
  - Tomato
```

**A list of crops does not say where the product works, it says where it is certified.** Products
work on any crop; the registration's backing reaches as far as the datasheet reaches. They are two
different facts and the page says both: `crop_scope: all_crops` in the agronomic profile, which is
the commercial truth, and `certified_crops`, which is the registration's. Certification is the same
in all eight countries, so there is a single list per product and it has no country dimension.

There are two scalar values besides the list, with the same vocabulary `crop_scope` uses, so as not
to have two words for the same idea:

```yaml
certified_crops: all_crops       # the datasheet says "all crops"
certified_crops: not_applicable  # it is not a product certified by crop
```

`not_applicable` belongs to adjuvants, traps and raw material: they are not missing the list, it does
not apply to them. It is different from not having the key, which is a pending item.

**The term goes exactly as the datasheet writes it, not the id.** If the datasheet says "Bell
Pepper", that is what gets archived. The day `chile` splits into its varieties, that term re-resolves
by itself to the new concept; if the page had archived `chile`, the precision was already lost at
curation and no tool recovers it.

### Agronomy

A ` ```json ` block with the structured profile, just one. It is what makes it possible to answer
"what works for whitefly on tomato?" without depending on the datasheet saying it in those words,
and what puts the dose in three numbers instead of in a sentence that has to be reparsed every time.

```json
{
  "schema": "product/agronomy/v1",
  "is_biological": true,
  "application_domains": ["agriculture"],
  "crop_scope": "all_crops",
  "targets": [
    {
      "id": "whitefly",
      "name": "Whitefly",
      "kind": "insect",
      "aliases": ["Bemisia tabaci"],
      "source_refs": ["datasheet"]
    }
  ],
  "default_regimens": [
    {
      "id": "biweekly",
      "dose": {"min": 1.0, "max": 2.0, "unit": "l", "basis": "ha"},
      "route": "drench",
      "water_volume": {"min": 200, "unit": "l", "basis": "ha"},
      "frequency": "every 15 days",
      "max_applications": 4,
      "interval_days_min": 15,
      "interval_days_max": 15,
      "source_refs": ["datasheet"]
    }
  ],
  "safety": {
    "incompatibilities": ["strong alkaline reaction", "high calcium concentrations"]
  },
  "sources": [{"id": "datasheet", "kind": "technical_datasheet", "ref": "/raw/Sproutvane.pdf"}]
}
```

The profile is validated ON READ, and a rule that fails does not leave the page half done: the reader
discards it whole, with doses, prices and equivalents. Each rule corresponds to a way the profile
would lie if it passed:

- `application_domains` is `agriculture` or `aquaculture`, nothing else.
- `crop_scope` is `all_crops`, `listed_crops_only` or `not_applicable`. Declaring `all_crops` with a
  list of crops is rejected: the two together mean nothing. `listed_crops_only` requires the list in
  `crops`, and is for a product that really does not work outside it; today no page says so. And
  `not_applicable` belongs only to a NON-agricultural profile.
- A dose always carries `unit` and `basis`. A number with no unit or basis says nothing.
- An `override` either brings its own regimens or marks `excluded`, never both, and needs at least
  one selector: one without selectors applies to everything, which is the same as not being an
  override.
- Two overrides with the same selectors and the same priority are rejected. Nobody can say which one
  wins.

The full contract, with the fields this example does not use (`overrides`, re-entry and harvest
intervals), is in `internal/okf/agronomy.go` of the `wiki` module.

**The concept's id goes in the profile, not an alias.** `hectare` resolves to `ha` and `liter`
resolves to `l`, so writing them fails nowhere: it leaves a page written differently from the rest
and nobody finds out until someone compares two pages field by field. `crops`, `targets[].id`,
`targets[].kind`, `route` and each dose's `unit`/`basis` are checked against their axis and against
the exact id.

The registration list is written once, in the frontmatter's `certified_crops`, in the datasheet's
words, and resolves to ids through the crops leaf. The profile does not repeat it: it says
`all_crops`, because the product works on any crop, and crop ids appear only in the `overrides` where
the dose changes by crop. Until Sep 13, 2026 the 24 pages with a list said `listed_crops_only` and
copied the list into `crops`, which means the profile stated the opposite of what this document says
three screens up. A `listed_crops_only` profile does write `crops`, and there `verify.sh` requires it
to say the same as the frontmatter, because two copies of the same data nobody compares diverge at
the first correction.

A `source_refs` pointing to an id that is not in `sources` is a dangling citation, and a citation
that cannot be followed is worse than none: the dose looks audited. The module does not check it;
`verify.sh` does, and also that the profile's `ref` is one of the frontmatter's `resource` values.

#### What the contract cannot say yet

This is documented here because the data exists in the datasheet and has nowhere to go. Meanwhile it
lives in `safety.notes` or in the regimen's `notes`, which is text and cannot be queried.

- **"Zero days to harvest".** It is the sales argument of the fifteen microbials and of three other
  products. `preharvest_interval_days` is an integer with `omitempty`, so the zero disappears when
  serializing and ends up identical to not knowing the interval. The field cannot say "zero".
- **Two routes with the same dose.** Five datasheets say "foliar and soil route" and give a single
  number. `route` is a string and does not admit both, and splitting the regimen in two would invent
  two regimens where the datasheet gives one.
- **What is neither agriculture nor aquaculture.** Vetvane treats animals, Aquavane treats livestock
  bedding and the rodenticide is used in homes and industry. `application_domains` has two values and
  neither is that, so the use stays in a note.


## Where each piece of data comes from

It goes in the frontmatter, not in the body. It is what the OKF SPEC asks for in §5.1, and it replaces
the `# Citations` these pages had until the migration to v0.2.

```yaml
sources:
  - id: datasheet
    resource: "/raw/Sproutvane.pdf"
    title: "Manufacturer's datasheet"
  - id: pricelist
    resource: "/raw/prices/demo_precios_2026.pdf"
    title: "Price list 2024-2025"
    page: 3
```

`resource` is the only mandatory thing in an entry. It starts with `/`, which §6.2 reads as relative
to the bundle root. It points to `raw/`, which is outside git: §6.1 asks a consumer to tolerate a
broken link, and whoever curates does have the file.

`id` is the key a loose piece of data is attributed with. Here they are the three roles that exist,
`datasheet`, `pricelist` and `equivalents`, and they do not repeat within a page. §5.1 wants them
stable precisely because an agent rewrites these documents all the time, and a positional index
—`sources[0]`— changes meaning as soon as someone reorders the list.

`page` is our own key, not the SPEC's, which has nowhere to put a page number. It is stored separately
instead of going in the `title` because it is data, not a label: a curator wondering six months from
now where a price came from has to be able to get to the PDF **and to the sheet** without asking
anyone.

A page is built from several sources and that is why there is one entry per document. `ingest.sh`
only writes the datasheet's, the only one it knows. The `pricelist` and the `equivalents` are added
by whoever curates, in the same pass in which they load the price table.

## Who wrote this and who reviewed it

Two different keys and the difference is the whole point. `generated` says who **produced** the
content; `verified`, who **confirmed** it against its sources. §5.2 separates them because whoever
writes a page is rarely the one who audits it later.

```yaml
generated: { by: human:gustavo, at: 2026-08-26T23:47:46-06:00 }
verified: { by: human:gustavo, at: 2026-08-26T23:32:47-06:00 }
```

The actor follows §7: `human:<id>` a person, `process:<id>` an automated process,
`<producer>/<version>` an agent. The date is ISO 8601 with an explicit offset.

`generated` accepts the §5.2 list just like `verified`, and it is needed as soon as a document has two
producers. The 38 product pages were written by a person and classified by an agent afterward:

```yaml
generated:
  - { by: human:gustavo, at: 2026-08-26T23:47:46-06:00 }
  - { by: claude-code/claude-opus-5, at: 2026-08-27T07:51:08Z }
```

Squashing the two into one makes the frontmatter state something that did not happen, in the only key
anyone looks at to know whether a page was written by a machine or a person.

**`generated` is mandatory here even though the SPEC treats it as optional**, and it is the only
frontmatter key that answers the question that orders this repo: was this page written by a machine
or a person? While it says `process:ingest.sh`, it is the raw skeleton and nobody looked at the OCR.
When curation ends it is changed to `human:<id>` with the day's date, and from then on the file
belongs to a person. That used to live in an HTML comment no consumer reads.

**`verified` is almost never there, and its absence is the data.** §5.3 derives three tiers: without
the key the page is *unverified*, with an actor that is not `human:` it is *machine-confirmed*, and
with one that is, it is *human-reviewed*. They are derived on read, not stored: a tier written by hand
goes stale and lies.

Today only five `company_info/` pages have it. The 38 product pages do not, and it is not an
oversight: their `# Datasheet` is unreviewed OCR, the tags are empty and the agronomy is missing.
Sealing them would claim someone compared them with the datasheet, which is exactly what has not
happened yet. `contact.md` does not have it either, because its own comment warns that three sources
give three different addresses.

### Sealing a page by hand

Add the line to the frontmatter and that is it: it is markdown, there is no command or registry to
update. The tier comes out by itself, because it is derived from this key.

```yaml
verified: { by: human:ana, at: 2026-08-27T09:00:00-06:00 }
```

The date is that of the review, not of the day the line is written. If there are several, use the
list form, and §5.2 obliges consumers to treat the loose map above as a list of one, so both forms
read the same:

```yaml
verified:
  - { by: human:ana, at: 2026-08-27T09:00:00-06:00 }
  - { by: process:price-audit, at: 2026-08-27T02:00:00Z }
```

`verify.sh` checks that `by` and `at` are there and that the actor follows §7. It is a check that
exists for a concrete reason: a misspelled actor breaks nothing. The page reads the same, nobody finds
out, and it stays unverified forever because the `human:` prefix is the only thing a consumer looks at
to classify trust.

The pre-commit hook does not count as a verifier. `verify.sh` confirms the page can be opened, not
that it tells the truth, and those are different things: a perfectly readable page can have the wrong
price.

## The company_info/ pages

Shipping, payments, hours, location: whatever is not a product. They live in `company_info/`, sibling
of `products/`, and the product reader only walks `products/`, so a policy is never confused with a
product.

**They carry a minimal frontmatter:** `type: company-info`, `title`, `description`, `sources` and
`generated`. The SPEC asks for parseable frontmatter and a non-empty `type` on every `.md` that is not
a reserved name, and being prose does not exempt them. Without `type`, a consumer that routes by type
has nothing to separate a policy from a product with, and the whole bundle stops conforming because
of six files.

Their sources used to live in an HTML comment at the very top. Now they are in `sources`, same as in
a product page, and the comment was left with only what reasons: which source rules when two
contradict each other, and what is left to resolve.

The file name is still the stable key. It is looked up tolerantly —"Shipping", "shipping" and
"shipping.md" all land on the same file— so it has to be the word people name the topic with, not a
code.

`index.md` is reserved just as in `products/`: it is a listing and the reader skips it.

One file per question someone really asks. Putting hours inside contact saves a file and makes "what
time are you open?" land nowhere.

## The ontology/ leaves

The closed vocabularies: the countries, the control targets, the units. One file per axis, sibling of
`products/`, and **the file name is the axis id**.

They exist because per-page review is not enough. A page is validated against itself and nothing else,
so nothing stops one from writing "R. Dominicana", another "Rep. Dominicana", and the two staying two
countries forever.

```
---
type: ontology
schema: wiki/ontology/v1
axis: countries
label: "Countries"
generated: { by: human:gustavo, at: 2026-08-27T07:05:54Z }
---

The prose before the table says what the axis is for and what was decided to leave out. It is kept:
a vocabulary that does not say what it refers to gets curated badly.

| id | label | parent | alias | note |
|---|---|---|---|---|
| central-america | Central America |  | ca |  |
| guatemala | Guatemala | central-america | gt |  |
```

**A leaf carries a single table, the concept table, and it opens with its `| id |` header.** The
reader starts consuming rows at the first table it finds, so an explanatory table above the prose is
read as concepts with backticked ids. It does not fail: it adds garbage to the vocabulary and the
garbage becomes valid vocabulary. Whatever you want to explain above goes in prose.

`id` is the stable identity, what gets stored and compared. `label` is how it is shown. `alias` are
the other ways people write it, separated by commas. `parent` is the more general concept that
contains it, and empty means root.

**The parent is what makes the leaf more than a list of words.** A query for aphid reaches the three
species without anyone writing the rule, and a page that archived `Brevicoryne brassicae` is still
found.

It is trimmed SKOS: canonical id, alias and parent. It is not OWL and there is no reasoner, because
these vocabularies are CLOSED and an extra value is a curation error, not a case to infer.

### Closing an axis has a price

**An axis that does not exist demands nothing.** While `ontology/<axis>.md` is absent, that field is
free text and no page fails because of it. The day it exists, a page with a term outside the vocabulary
leaves the whole catalog, not just the axis: the reader discards it the same as a malformed one.

That is why an axis is closed when someone has curated it, not all at once. And that is why adding the
leaf is what makes the axis mandatory: there is no list of required axes somewhere else that can be
forgotten.

### What breaks the whole vocabulary

An alias pointing to two concepts, a repeated id, a nonexistent parent, a parent cycle. None of them
breaks only its own leaf: the reader does not build the ontology, and without an ontology **nothing is
validated and everything passes**. Validation turns itself off and no page looks broken.

The worst of the four is the duplicate alias, because it fails nowhere on its own: it makes
"cenicilla" sometimes one thing and sometimes another depending on the position the file was read in.

`verify.sh` checks all four, and when the vocabulary does not load it says so and skips the page
review instead of leaving the dashboard green.

### The growth rule

A concept goes in if a datasheet names it or a customer asked about it, not from a manual. A closed
vocabulary that grows without judgment stops being closed.

What was decided to leave out is written in the prose of its leaf. Six months from now the question
will be why it is not there, and the answer has to be where one looks.

`index.md` is reserved just as in `products/`: it is a listing and the reader skips it.

## A product that stops being sold

It is marked `state: discontinued`; the page stays. Deletion is logical because a withdrawn product
keeps being named in conversations, and the wiki has to be able to say what happened to it instead of
not finding it.

`state` is one of `current`, `out_of_stock`, `discontinued` or `withdrawn`, or empty, which means
nobody declared it. A fifth value breaks nothing on read and that is why `verify.sh` rejects it:
`discontinuated` gets stored like any string, and the rule below stops applying to it.

**A `discontinued` or `withdrawn` product carries no price table.** It is an ERROR, not pending. A
price on the page brings it back to the catalog through the back door, because whoever answers "how
much is it?" reads the table and not the frontmatter, and ends up quoting something that is not sold.

`out_of_stock` stays out of the rule on purpose. It will be back, and its price is the one it has when
it returns.

**What takes its place is declared, not deduced.** `alternatives` is the list of paths of the current
products that replace it, one per line with `- `, and `# Summary` says in one sentence which part of
what it did each one covers. Without that, "what can you give me instead of X?" gets answered by
crossing tags, and tags do not distinguish the replacement from the neighbor: Humus Total shares
`soil-conditioner` with Living Soil and the searcher offered it, when the ones that do what Humus did
are Nitrovane, Phosvane and Raíz Viva. A discontinued product without a replacement does not carry the
key, and the summary says so.

The rule also runs the other way: on a discontinued page, an empty `# Presentations` stops counting as
pending. It is not missing data, it is the decision not to load it. Without that, today's four
discontinued pages came out on the work list forever, and a list that never goes down stops being
read.

## The bundle, not the page

Three rules that do not belong to a page but to the whole repo, and that `verify.sh` has checked since
`company_info/` spent months without `type` with nothing saying so.

**Every `.md` that is not a reserved name needs frontmatter and a non-empty `type`.** Including
`README.md`, `FORMAT.md` and `CLAUDE.md`, which are inside the bundle tree and therefore are bundle
documents. They carry `type: reference`.

**The reserved names are `index.md` and `log.md`, and they carry no frontmatter.** The only exception
is the root `index.md`, which declares `okf_version: "0.2"` and is the only place where that key is
valid.

**The root `index.md` enumerates the bundle.** It is the first thing someone opens who arrives without
knowing what is here; empty it is useless. Each entry is `* [Title](path) - description`, and the
description comes from the `description` of the page it links to.
