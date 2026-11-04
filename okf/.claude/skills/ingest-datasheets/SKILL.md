---
name: ingest-datasheets
description: Converts datasheet PDFs into OKF bundle pages with ingest.sh. Use when someone leaves PDFs in raw/, asks to convert or update datasheets, warns that a PDF changed, or asks what is left to ingest.
---

# Ingesting datasheets

Takes a datasheet PDF to a page in `products/` that the OKF reader can open.

The conversion is already written in `ingest.sh`; read its header with `./ingest.sh --help` instead
of reconstructing what it does. This document is the judgment the script cannot have: which PDF goes
in, what to do with what comes out, and when the run is finished.

**The invariant**: `products/*.md` is human curation and `ingest.sh` never overwrites it. When a PDF
changes and the page already exists, the script converts the new text to `raw/md/` and warns. Respect
that: when a curated page is rewritten, a person's work is lost without a trace.

## Steps

### 1. Separate what is a product from what is not

The PDFs sit loose in `raw/`. Open the list and look at the names one by one.

A full catalog, a company presentation, a price list or a corporate document **are not a product**.
If they go in, they end up as product pages the bot will recommend as if they were one.

Move them to `raw/non-products/`. The `ingest.sh` glob is not recursive, so they stay stored there
and out of the way. Ask before moving any that is doubtful.

It is done when every PDF in `raw/` is the datasheet of a sellable product.

### 2. See what is going to happen

```
./ingest.sh --status
```

It reports without writing anything. Read the whole output and tell the person what is going to
happen: how many are new, how many changed, how many stay the same.

A PDF marked **changed** deserves a line of its own: its page already exists and will end up out of
date.

### 3. Convert

```
./ingest.sh
```

It takes about 20 seconds per PDF, so 40 datasheets are 15 minutes. Run it in the background and say
how long it will take before starting.

It is done when the script prints its summary.

### 4. Verify

```
./verify.sh
```

Zero **ERROR** is the condition for moving on. A page with an error disappears from the catalog
silently: the file exists, the product does not.

The **pending** lines are normal here. A freshly generated page has no tags, no prices and no
agronomic profile, because none of that is in a datasheet. `curate-page` takes care of that.

If something gives an ERROR, `FORMAT.md` has the exact format the reader expects.

### 5. Close the run

Report three things:

- how many new pages there are and what they are called
- which pages ended up out of date, if any, with the diff command the script printed
- the pending count `verify.sh` gave

`ingest.sh` has already written the entry in `log.md` and regenerated `products/index.md`.

## A PDF changed

The warning comes out again on every run until someone resolves it. That is on purpose: a warning
that turns itself off is not a warning.

1. `diff raw/md/<slug>.prev.md raw/md/<slug>.md` to see what the manufacturer changed.
2. Carry that change by hand to `products/<slug>.md`, keeping what was curated.
3. `./ingest.sh --accept` to seal the hashes and turn off the warning.

Do step 3 only after step 2. Accepting without looking leaves the page lying with the old version
and with no sign that it stayed that way.

## When docling is missing

`ingest.sh` stops if it does not find it. Install it with `uv tool install docling`. It is the only
thing needed besides bash.
