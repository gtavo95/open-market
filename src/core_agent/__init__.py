"""agro, second version: the advisor built from the primitives, one step at a time.

Step 1: two roles and nothing else. A SEARCHER with a REPL over the catalog
(`drive`) that comes out through the boundary as a report, and a WRITER that reads the
reports with the datasheets open and talks to the customer in the bundle's voice.
`orchestrate` joins them.

Step 2, Sep 20, 2026: the SALE. A plan that lasts the
conversation (`SESSION`, in the `course` channel), a `planner` with no voice: `seed`
seeds it and `close_steps` closes it with the judge from `world/question_judge.py`: five
slots are closed by what the customer said, four by what the turn did.
It runs at the turn's boundary (`close_sale_steps`), before the roles and after. The
writer sees it as one line in its request (`sale_line`); the searcher runs
every turn. No levers: what is not here does not exist yet.

Step 3, the same day: the SEARCHER's checklist. A `planner` with a voice around
its `drive` (`planned`), in the `steps` channel and for one turn only: two leaves
that close on facts from the Log (it queried, it closed with `SOURCE:`), and with one open,
one more round with the voice saying what was missing. It is the first lever to measure
against the logbook: the turn without it is `SEARCH_ROUNDS = 1`.

Step 4, Sep 21, 2026: the EFFECTS. The advisor proposes what the
host does, sending the datasheet or the account, as moves in the `effects` channel
(`EFFECT_RULES`): `propose_effects` proposes on the way in with the same judge as the sale, the
writer reads it as one more line of its request (`effect_line`), `resolve`
completes on the way out the path of the datasheet it cited, and the host executes at the
boundary and seeds `done` or `reject` on the next turn, the way it seeds `course`.
Nothing is executed inside the turn.

Step 5, Sep 22, 2026: the ESCALATION. The advisor is the customer's trusted
source, and a turn that ends in "that is not in the datasheet" leaves
a conversation without an owner. At the end of the turn, with the answer already written, a
judgment on that answer says whether it left the customer without what they asked for, and a
`choice` of what it is, among the CRM's reasons (`HANDOFF_REASONS`): with that `propose_handoff`
proposes the `handoff` effect and the host opens the case to a person. What the
customer sees of the escalation is said by the host, which is the one that knows whether there is
someone on the other side.

    orchestrate([search_catalog], write_reply, before=[close_sale_steps, capture_effects], after=[close_sale_steps, fill_effect_args, human_handoff])

Step 6, the same day: the package. Until that day all of this was
`agro_v2.py`, 1,100 lines in one file, and the names were in Spanish. There are
three kinds of module and no other:

    agent.py           THE SHAPE: `build`, `turn`, `provider`. Only the wiring.
    prompts/           WHAT THE MODEL READS: one file per reader.
    roles/searcher.py  A ROLE: REPL, checklist, cell.
    roles/writer.py    A ROLE: request, the account REPL, cell.
    roles/sale.py      A ROLE: `SESSION`, the readings of the plan, cell.
    roles/effects.py   A ROLE: `EFFECT_RULES`, resolvers, cell, and the host's rule.
    roles/human_handoff.py A ROLE: when the turn passes to a person, and for what reason.
    world/catalog.py   THE WORLD: the bundle, what is read whole and what is parsed.
    world/question_judge.py     THE WORLD: the TypeSafe judges and the facts of the Log.
    world/dialogue.py  THE WORLD: the envelope the model and the judges share.
    world/recap.py     THE WORLD: the previous answers, summarized for the envelope.
    world/typesafe.py  THE WORLD: the TypeSafe HTTP client.

A role brings together the table that governs it, the judge that closes it and the
cell, in that order. What the model reads is kept apart, in `prompts/`, with one
file per reader: the searcher, the writer, the judge and the summarizer. Changing a
file in `prompts/` forces a measurement, and changing a role does not, unless it changes
what enters the request. `prompts/` imports nothing from the package, so it reads
on its own. No role imports another, except the writer, which reads the sale's line and
the effects' line because its request carries them.

What this package exports (`__all__`) is the contract with whoever hosts it:
the terminal (`cli.py`), the evals (`evals/suite.py`) and the server (`host/`). A name a
host needs that is not here is a decision, not an accident.

This package is the core: no `argv`, no `input()`, no HTTP. To converse,
`uv run cli.py`; for a single question with the searcher's
transcript, `uv run cli.py --one`.

The steps that follow, each one apart: charging with a cart (and `payment_link`
as an intent); measuring live the questions of the
escalation, which is the only thing here that went in without a number.
"""

from __future__ import annotations

import dotenv

dotenv.load_dotenv()

from .agent import build, provider, turn  # noqa: E402
from .roles.effects import EFFECT_RULES, effects_state, host_sim  # noqa: E402
from .roles.form import Forms  # noqa: E402
from .roles.human_handoff import HANDOFF, TAKEOVER  # noqa: E402
from .prompts.judge import HANDOFF_REASONS, TAKEN_OVER  # noqa: E402
from .prompts.writer import ASKS  # noqa: E402
from .roles.sale import SESSION, ask_next, nothing_to_search, sale_state  # noqa: E402
from .roles.writer import answer, messages  # noqa: E402
from .world.catalog import BUNDLE, FOLDERS, corpus, products, voice  # noqa: E402
from .world.question_judge import QuestionJudge  # noqa: E402
from .world.recap import Recaps  # noqa: E402

__all__ = [
    "ASKS",
    "BUNDLE",
    "FOLDERS",
    "QuestionJudge",
    "Recaps",
    "HANDOFF",
    "TAKEOVER",
    "TAKEN_OVER",
    "EFFECT_RULES",
    "HANDOFF_REASONS",
    "SESSION",
    "answer",
    "ask_next",
    "Forms",
    "build",
    "corpus",
    "effects_state",
    "host_sim",
    "messages",
    "nothing_to_search",
    "products",
    "provider",
    "sale_state",
    "turn",
    "voice",
]
