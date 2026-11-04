"""What the memory searcher reads: its contract, behind the turn's question.

The cell, the REPL with `zoom` and `date`, and the view belong to catalejo (`memory_search`); the
wiring is in `agent.py`. Changing this text is changing what the model sees, and that is
measured: the `memory-*` probes in `evals/cases.tsv` (logbook todo #24).

`memory` in `MEMORY_SEARCHER` is the name of the REPL variable: catalejo fixes it
(`catalejo.rlm.memory.VAR`), so it stays Spanish in the English text.
"""

from __future__ import annotations

from catalejo.rlm import COMPACT

MEMORY_WHO = "memory"

MEMORY_SEARCHER = """`memory` holds this customer's history with the business, from conversations
before today's; whoever writes the reply already has today's. Your answer is whatever in that
history helps reply to this message: what they bought, which presentation and how much, for which
crop and pest, where they receive and in whose name, how they paid, and what was left pending. Each
fact with its date and the number of the message it comes from. If something changed (they moved,
they changed crops), the most recent one counts, and say that it changed. When the customer refers
to something from before ("same as last time"), open with `zoom` down to the message where it was
said and bring the exact fact, not the summary.

Do not recommend products or give doses or prices: those come from the catalog, and someone else
looks them up. If nothing in the history helps with this message, your answer is one line saying so."""
"""The memory searcher's contract. Not measured (Oct 5, 2026)."""

MEMORY_FOR_SEARCH = """What we know about this customer from earlier conversations, according to whoever read their
history:

{memory}

If today's message refers to something in there ("same as last time", "the usual"),
look up that product and that presentation in the catalog as if the customer had named them."""
"""What the catalog searcher reads from the `memory` report, after the question (`with_memory`).

Without this the catalog saw only "I want the same as last time", answered `SOURCE: none`
and the turn ended with no datasheet, no current price and no order: `memory-returning-customer`
failed 18 of 18 runs with luna and with Haiku (Oct 7, 2026).
"""

COMPACTOR = COMPACT.format(
    agent="a sales advisor that answers the customers of one agricultural supplies business over WhatsApp",
    kinds=(
        "customer (the customer's words), advisor (the advisor's replies), operator (a person of the "
        "business who stepped into the chat), system (a message the platform sent, like a campaign "
        "template)."
    ),
    person="the customer",
    example="customer: ...; advisor: ...; operator: ...",
)
"""The compactor's prompt (§4.4 of the spec, in `catalejo.rlm.compact`) with this business's specifics.

The kinds are the ones the host sends in `kind`. Not measured (Oct 5, 2026).
"""
