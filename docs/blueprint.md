# Blueprint: from agro to other agents

On September 28, 2026 we decided that the next agents (a clinic, a
restaurant) come out of agro. The repo is not copied: three layers are separated and each
vertical contributes only the top one. This document says what goes in each layer, what
has to be untied in agro today to get there, and in what order. Nothing has been
extracted yet: this is the plan, not the build.

## The three layers

```
catalejo            the primitives: Cell, Log and its channels, orchestrate, planner, drive
   ↑
advisor kit         the roles, the envelope, the judge, the effects, the escalation,
                    the HTTP/A2A host and the evals harness, with generic prompts
   ↑
vertical            a Domain: the plan, the questions, the effects, the reasons,
                    the bundle parser, its own prompts, the extra cells
   ↑
okf bundle          the customer's content, in its own repo
```

**catalejo does not change.** It is the algebra and does not know what a sale is or that
TypeSafe exists. If the kit went in there, the library would start carrying domain and
would lose what makes it stable.

**The kit is a separate library, on top of catalejo.** It is the opinionated
composition that today is `src/core_agent/` plus `src/host/`: a searcher with a REPL
over the catalog, a writer with the bundle's voice, and at the edge of the turn
the sale, the effects and the escalation, with the state traveling with the client.

**The vertical configures and composes; it does not fork.** Copies have already hurt
twice: `v3/catalejo`, and `core_agent/`, which was a copy of
`catalejo/examples/agro/asesor/` until Sep 22, 2026. A copy diverges and the
fixes do not come back.

## What goes in the kit

What no longer knows anything about agro, or almost nothing:

| Piece | Today in agro | What it does |
|---|---|---|
| The shape of the turn | `core_agent/agent.py` | `orchestrate([searcher], writer, before=[…], after=[…])`, `turn`, `provider` |
| The envelope | `world/dialogue.py` | `wrap`, `customer_words`, `conversation` |
| The recaps | `world/recap.py` | the long answers of the history go in summarized |
| The judge | `world/typesafe.py`, the mechanics of `world/question_judge.py` | per-turn memory, compaction, noul and choice, thresholds |
| The Log facts | `world/facts.py` | `answer_of`, `saw_file` (the concrete paths belong to the domain) |
| The index description | `world/fields.py` | `describe` builds the text from the records; the notes belong to the domain |
| The searcher | `roles/searcher.py` | REPL with `grep`/`read`, checklist, `SOURCE:` |
| The writer | `roles/writer.py` | the request, the reports, the messages split with `---` |
| The sale | `roles/sale.py` | the voiceless `planner` over `course`, `ask_next`, `sale_line` |
| The effects | `roles/effects.py` | `Intent`, resolvers, `host_sim`, the "proposes, does not execute" rule |
| The escalation | `roles/human_handoff.py` | judgment on the input and the answer, reason as a choice |
| The alerts | `roles/alerts.py` | compacted state, what was already said, turn flags |
| The host | `host/`, `routes/`, `lifespan/`, `auth.py` | `course` and `effects` as ops that travel with the client, REST, A2A |
| The evals | `evals/` | suite, A/B, criterion, logbook; the cases live in the bundle |

The kit's default prompts bring only the generic part: cite with `SOURCE:`, do not
invent what the catalog does not say, one question per turn, how to read the
reports. The voice and the business rules go in the vertical.

## What goes in the Domain

Today it is spread across modules of the package. In the blueprint it is a single object
that `build` receives:

```python
@dataclass(frozen=True)
class Domain:
    bundle: Path                        # the okf bundle
    folders: tuple[str, ...]            # which folders the searcher reads
    index: Callable[[Path], list[dict]] # the REPL index (`products()` in agro)
    index_notes: dict[str, str]         # what the data does not say (`PRODUCT_NOTES`)
    schema: str                         # what the catalog is, for the searcher
    session: Plan                       # the conversation plan (`SESSION`)
    asks: dict[str, str]                # what the customer is asked at each leaf (`ASKS`)
    questions: dict[str, dict]          # what the judge asks about the customer (`SALE_QUESTIONS`, `LABEL_GATES`)
    reply_questions: dict[str, dict]    # what it asks about the answer (`REPLY_QUESTIONS`)
    log_facts: Registry                 # Log facts that close leaves (`LOG_FACTS`)
    effects: dict[str, Intent]          # what the advisor can propose (`EFFECT_RULES`)
    handoff_reasons: dict[str, str]     # the CRM reasons, inbound and outbound
    alerts: dict[str, dict]             # flags for the writer (`ALERT_ASKS`)
    writer: str                         # the writer's contract, on top of the generic one
    compact: str                        # the compaction request
    order: OrderBook | None = None      # the cart, if the vertical sells with a cart
```

The voice keeps coming from the bundle's `voice.md` and the eval cases from its
`evals/` folder, as they do today.

## What the engine does not have yet

**Live data.** Agro reads a static catalog. A clinic needs the
schedule; a restaurant, the stock and whether the kitchen is open. There are two paths,
and the first is simpler:

1. The host injects into the searcher's REPL a variable built on that turn,
   as `products` is today. The searcher queries it just like the catalog.
2. A `query_*` effect that the host executes and whose result comes back seeded
   in the next turn. It costs a round-trip turn.

**The cart belongs to agro.** `world/order.py` reads the `# Presentations` table of
each datasheet, has its `UNITS` table and charges in quetzales. A restaurant reuses it
almost whole (the presentation becomes portion and modifiers); a
clinic does not use it. That is why it is optional in the `Domain`.

## Two examples

**Clinic**

- Plan: reason → specialty or service → professional and location → time slot →
  patient data (ID, insurance) → confirmation.
- Effects: `send_preparation` (a document, along the datasheet path),
  `book_slot` (the host against the schedule), `send_payment_link` (the copay).
- A medical emergency is an alert with immediate escalation, not one more CRM
  reason. The writer's contract forbids diagnosing.
- No cart. The schedule comes in live.

**Restaurant**

- Plan: dishes and modifiers → mode (delivery, pickup or reservation) →
  address or time → payment → confirmation.
- Effects: `send_menu` (the `send_catalog` path), `send_payment_link`,
  `create_order` (the host against the POS).
- Alert: allergens.
- With a cart. The stock and the hours come in live.

## How a vertical is customized

1. **Configure.** The `Domain` and the bundle are enough for most.
2. **Compose.** Each role is a `Cell`, so a vertical with something of its own
   writes its `build` with the kit's pieces and adds its own:

   ```python
   def build(model, judge):
       return orchestrate(
           [search_catalog(CLINIC, model), check_schedule(model)],
           write_reply(CLINIC, model),
           before=[*kit.before(CLINIC, judge), urgency(judge)],
           after=kit.after(CLINIC, judge),
       )
   ```

3. **Change the kit.** If a vertical needs a kit piece to behave
   differently inside, the change goes to the kit, with a new version. Never to a
   copy.

## Versions and shared prompts

A change to the writer's generic contract touches all the verticals, and
each one has its suite in its bundle. That is why each vertical pins the kit
version, as agro pins catalejo in `vendor/`, and moves up when a small A/B with its
probes passes. The kit is not measured against everyone's suite at once.

The deploy starts with one service per vertical, each with its pinned version.
A single multi-tenant service is possible later (the host no longer keeps
state), but it requires all the verticals to be on the same version.

## What has to be untied in agro

1. `QuestionJudge` imports the question tables from `prompts/judge.py` at
   module level; it has to receive them.
2. `sale_line` knows leaves by id (`find_step(sale, "product")`); the
   `Domain` has to say which is the "I already found what to offer" leaf.
3. `host/effects.py` repeats `NEEDS_ARGS` by hand; it has to read it from the core.
4. `BUNDLE` is resolved on import with `DEMO_BUNDLE`, and `FOLDERS` is fixed;
   they have to come from the `Domain`.
5. `LOG_FACTS` names `products/` and `company_info/payments.md`; the paths belong
   to the domain, `saw_file` belongs to the kit.
6. The judge depends on TypeSafe. It is a decision and not a coupling, but it goes into
   the cost of each vertical.

## The order

1. **The `Domain` inside agro, without changing behavior.** `build(model,
   domain, …)` receives what today are module constants. It is validated with
   pytest and a small A/B with probes; the whole suite is not needed, because the
   request the model sees does not change.
2. **The clinic in the same repo**, in `verticals/clinic/`, with its okf
   bundle. What has to be touched in the engine for it to fit is the real seam of the
   kit. With a single case, what gets abstracted is a guess.
3. **With two verticals running, the kit moves out to its own wheel** and is
   vendored like catalejo. Agro becomes `verticals/agro/`.
