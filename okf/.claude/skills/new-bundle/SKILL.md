---
name: new-bundle
description: Empties a forked bundle and leaves it ready for another company. Use when someone says they forked or cloned this repo, that they will build the wiki for another customer, or that they want to start from scratch with their own products.
---

# Starting a new bundle

A fork of this repo brings the previous company's products. Emptying it is the first step, and it
has to be done completely: a page that survives from the previous tenant shows up as a product of
the new catalog, price and all.

## Steps

### 1. Find out whose it is

Ask for the company name and the short identifier it will go by in the system (lowercase, no spaces:
`demo`, `ceiba`). It is the `org_id` of every page.

### 2. Empty it

```
rm -f products/*.md sources.tsv
rm -rf raw
printf '# Log\n' > log.md
```

`company_info/` and `ontology/` are a separate matter: ask before deleting them. The shipping and
payment terms do belong to the previous tenant, but an ontology of crops and pests works almost the
same for any company in the same line of business, and curating it again from scratch takes days.

It is done when `products/` is empty and `./verify.sh` reports zero pages.

### 3. Set the org_id

In `ingest.sh`, the line `ORG="${OKF_ORG:-demo}"`. Change the default to the identifier from step 1.

### 4. Rewrite the README

`README.md` describes the previous bundle. Replace it with the new company's: what it sells, where
the datasheets come from, who curates.

`CLAUDE.md` and `FORMAT.md` are not touched: they describe the format, which is the same for any
tenant.

### 5. Load the datasheets

Ask the person for the PDFs, leave them in `raw/` and continue with the ingest flow.

## What a fork takes along

What works as is in any bundle: `ingest.sh`, `verify.sh`, `FORMAT.md`, `CLAUDE.md`, the skills, and
the directory structure.

What belongs to the tenant and gets replaced: `products/`, `company_info/`, `sources.tsv`, `log.md`,
`raw/`, `README.md`, and the `org_id`.
