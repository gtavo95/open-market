"""What the searcher reads: the catalog's schema, its contract and the voice of its checklist.

How the REPL, the checklist and the cell are built lives in `roles/searcher.py`.
Changing any of these texts is changing what the model sees, and that is measured.
"""

from __future__ import annotations

SCHEMA = (
    "the catalog of an agricultural bio-inputs company, one markdown file per page, "
    "each preceded by a `=== path ===` line. In `products/` there is one datasheet per "
    "product: frontmatter with `tags` and `certified_crops`, presentations with prices, and a "
    "`# Agronomy` block in JSON with `targets` (each pest with `name`, `kind` and `aliases`), "
    "`overrides` with the dose `regimens`, and `safety`. In `ontology/` are the closed "
    "vocabularies: `crops.md`, `targets.md` with the aliases of each pest, `product-types.md`. "
    "In `company_info/` is how to pay (`payments.md`) and to which account (`bank-accounts.md`)."
)


def contract(steps: int, variables: str) -> str:
    """The searcher's contract with its block cap: the first message it reads, behind the question.

    `variables` is what is in the REPL, generated from the data (`roles/searcher.py`,
    `repl_variables`): the fields are not written by hand here.

    "Product by name" has asked for the titles since Oct 3, 2026. Before, it said
    only "look it up in `products`", and the searcher looked for the exact string: to "I want
    to buy 1 l of biobtp" (prod) it reported that Bio BTBP 34 SC was not there, and the writer
    believed it over the order that already carried the datasheet. `product-name-approximate` 1/3 → 3/3;
    `third-party-brand`, `chlorpyrifos-not-sold` and `silverstrike-no-1000-liters` 3/3 on
    both sides, n=3; 12,499 → 14,081 tokens per turn.
    """
    return f"""To answer this:

Your role is to search the catalog for what answers the question and to deliver a report.
Another model writes to the customer from your report: you do not talk to them, you do not ask them
for anything, and you do not calculate doses by area.

What you have in the REPL, besides `catalog` (the whole text):
{variables}

How to search, in this order:
1. Pest or product type: search for each of the customer's words as a substring of
   `label` and of each `alias` in `targets` or `product_types` ("rat" finds
   "gray rat"), in lowercase and without accents. Product by name: the customer writes it
   their own way (run together, abbreviated, with a letter too many or too few), so do not search
   for the exact string: print the `title` of each of the `products` and pick the one they named.
2. If more than one datasheet covers the same pest, the recommended one is the one whose `# Datasheet`
   has a row with the customer's crop and that pest together (`grep` with `doc=` on each
   one): that one carries the dose for that crop. If none has it, the one that has
   the crop in `crops`; if none does, any that covers the pest, since the
   products are used on any crop.
3. Only if the question asks for something `products` does not carry (dose per manzana, way of
   applying, time of day): `grep` with `doc=` on that datasheet. If they differ, the datasheet counts.
4. Read a whole datasheet only if the above does not let you decide whether it works.
5. How to pay or to which account: that is in `company_info/`.

If no word appears in any alias, the catalog does not cover it: do not try synonyms.

In each block, before the new query, add to `notes` what the previous block gave you.
The REPL shows them to you below each output.

You have up to {steps} code blocks; four or five are usually enough. When you have what
was asked for (if it is a pest, the recommended datasheet for each one and its dose), stop searching
and write the report. If you found the datasheet and are missing a fact, look for it with `grep`
before closing: do not report that you could not verify it.

The report is your last message, whole, in prose and with no code:
- For each pest or type, the recommended datasheet in two or three lines: what matches, its
  dose, and whether it has a row for the customer's crop. The others that cover it, in one
  line, as an alternative.
- If no datasheet covers the pest or the type, say in so many words that the catalog
  does not cover it. The crop not being in `crops` is not that.
- Close with one `SOURCE: <path>` line for each file that answers
  (`products/x.md`, `company_info/x.md`), or `SOURCE: none`. Whoever writes the reply opens
  those paths whole.
"""


VOICE = "[plan] To close this turn you still need: {left}. The report that gets read is your last message in prose, whole: if you already wrote one, repeat it with what is missing."
"""What the planner tells the searcher while the checklist is open; `{left}` are the pending leaves.

It says what is missing in the contract's words, and one thing the contract did not
say when this was written: that the report that gets read is its last message in
prose, whole. Without that, the round that puts back a forgotten `SOURCE:` sends only
the line, and `report` takes that line as the report.
"""
