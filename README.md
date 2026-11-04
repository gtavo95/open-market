# open-market

A sales advisor for farm inputs that runs on Muse Wonder through the Meta Model API. A farmer
describes a pest on chat, in writing, in a voice note or with a photo; the advisor finds the right product in the
distributor's catalog, gives the dose from the datasheet, cites its source, builds the priced order
and takes it to payment. When no datasheet covers the problem, it says so and hands off to an
agronomist instead of inventing a product or a dose.

Built for the Meta Global AI Developer Hackathon, theme "Build for Your World". The catalog in
`okf/` belongs to a fictional Guatemalan distributor, Agroinsumos Ceiba.

Try it: https://open-market-28985494187.europe-west1.run.app

## What was built for the hackathon

The project reuses earlier work by the same author. The advisor is based on an agent that runs in
production, by way of a Spanish demo, and `catalejo`, the agent library in `vendor/`, predates the
event.

Done during the hackathon:

- Translated the advisor, prompts, catalog, eval cases, docs and `catalejo` to English.
- Added the Muse adapter (`catalejo/llm/muse.py`, inside the vendored wheel) and moved the agent
  onto the Meta Model API.
- Measured four Muse configurations with the eval suite and picked the default from the results
  below.
- Added photo and voice input: Muse Wonder reads the attachment and the turn goes on as text
  (`src/host/perception.py`, `src/core_agent/prompts/perception.py`).
- Added the public chat page and its route (`src/web/index.html`, `src/routes/chat.py`) and deployed
  it on Cloud Run (`scripts/deploy.sh`).

## Photo and voice

The Meta Model API takes images and audio in the same `/responses` call as text, so Wonder does both
readings at low effort. A photo becomes a description that says how sure it is, and a voice note
becomes a transcript. That text is the customer's turn, so the searcher, the judge and the citation
check run unchanged, and the page shows what was seen or heard so the customer can catch a misreading.
The photo prompt forbids naming a product: only a datasheet can do that.

Measured through `/chat` on Nov 3, 2026, 3 runs per case, read by hand. Photos are Wikimedia Commons
images; voice notes are macOS text-to-speech, and the noisy one has Gaussian noise and a tone added.

| Case | What happened |
|---|---|
| Photo, powdery mildew on squash | 2 of 3 recommended Escudo with the datasheet dose; 1 asked for the crop |
| Photo, coffee leaf rust (not in the catalog) | No product in 3 of 3: 1 escalated, 2 asked to confirm |
| Photo, thrips damage on hydrangea | Read as hydrangea, thrips or aphids unclear; no product in 3 of 3, 2 escalated |
| Photo, a tractor | No product in 2 of 2, asked what the problem is; 1 run failed reading the photo |
| Voice, clean, English | Exact transcript and Silverstrike in 3 of 3 |
| Voice, heavy noise, English | Heard right in 1 of 3; the 2 misheard ones escalated, with no product |
| Voice, Spanish | Exact transcript, answered in Spanish with Silverstrike in 2 of 2; 1 run failed reading the note |

No run recommended a wrong product. A misreading ended in a question or an agronomist. The 2 failed
readings, a timeout and an empty answer, led to the retries now in `perception.py`, which have not
been measured at this scale. A turn with a photo took 48 to 81 s and one with a voice note 36 to 63 s.
Not measured yet: real farmers' voices, and recordings made in a browser.

## Why Muse Wonder

Model and effort were picked with the eval suite in `evals/`: the 6 turns of the launch script,
3 runs each, 18 turns per configuration, on Nov 3, 2026. "Correct" means the answer cites the expected
source; "criterion" is a TypeSafe judge reading the answer against the case.

| Configuration | Correct | Criterion | Order right | Seconds per turn |
|---|---|---|---|---|
| `muse-wonder-1.0`, medium (default) | 16/18 | 18/18 | 6/9 | 45 |
| `muse-wonder-1.0`, low | 16/18 | 17/18 | 6/9 | 39 |
| `muse-spark-1.3-contributor`, low | 9/18 | 17/18 | 3/9 | 44 |
| `muse-spark-1.3-contributor`, medium | 8/18 | 18/18 | 3/9 | 112 |

This is a small sample: 3 runs do not separate low from medium on Wonder, and the default moves
between runs: after the last prompt changes it read 15/18 and then 17/18, with the criterion at 18/18
and orders at 6/9 both times. A known gap remains on
the turn that adds a second product: the internal cart reads 6 L of the first product for one turn,
and it is right again on the next turn.

## Quickstart

You need a Meta Model API key and a TypeSafe key, the judge behind the sale gates.

```bash
uv sync
cp .env.example .env         # fill MUSE_API_KEY and TYPESAFE_API_KEY
uv run --env-file .env cli.py    # chat with the advisor over stdin
```

Try: `I have 2 manzanas of tomato with silver spots on the leaves and little elongated bugs.`

---

The sales advisor written on catalejo, behind HTTP. The
model never sees the whole catalog: it queries it with code in a REPL, where
`grep` says which datasheets a term is in and `read` brings the whole datasheet, and where
it also has `products`, an already parsed index with one entry per datasheet
(certified crops, pests, doses with unit and base, `safety`). The API
returns the answer with the files each piece of data came from.

The agent goes in roles: a searcher that queries the catalog and brings a report
with the datasheets it cited, a writer that talks to the customer with the voice of
`okf/voice.md`, and outside the two, at the edge of the turn, the sale and the
effects. The sale is a plan (pest, product, recipe, quantity, doubts, method,
charge, data); the effects are what the advisor proposes someone do
(send them the datasheet, send them the account), because the advisor talks and sends
nothing. Both travel with the client on each request, because nothing is kept
here. Since Sep 20, 2026 the agent is built from catalejo's primitives
and without levers; until then it was a loop with `ORCHESTRATE`, `VISTA` and
the others.

The REPL workspace is built per turn and does not live in a pool: each request belongs to
another person, and a variable the model rebinds in one cannot change the
catalog for the next. `SLOTS` is still how many queries run at once.

## Run

```bash
uv sync                      # deps + catalejo from vendor/, in .venv
export MUSE_API_KEY=...
uv run uvicorn main:app --app-dir src --reload
```

```bash
just ci                      # before a PR: secret-scan and okf/verify.sh (see justfile)
uv run pytest                # no network; the host with a small bundle, the agent with okf/
uv run mypy
uv run cli.py --one          # a single question, with the searcher's transcript
uv run cli.py                # conversation over stdin (--verbose: what each role said)
uv run python -m evals         # the quality suite; the cases live in the bundle
```

## What is here

`src/` is the app code, what gets deployed. Outside it are the
configuration, `vendor/`, `scripts/`, `okf/`, `tests/` and the two development
tools, `cli.py` and `evals/`, which add `src/` to the path on startup.

- `main.py` builds the app and the advisor in the `lifespan`; `config.py` is the `.env`.
- `core_agent/` IS the agent, without HTTP. Until Sep 22, 2026 it was a copy of
  `catalejo/examples/agro/asesor/`; since then it lives and is edited here. Inside,
  `agent.py` is the wiring, `roles/` what each role says (searcher,
  writer, sale, effects, escalation) and `world/` the catalog, the TypeSafe judges, the
  turn envelope and the HTTP client. What the package exports in `__all__` is
  the contract with this host.
- `host/` is what the agent does not do because it is not its job: `catalog.py`
  points it at the service's catalog; `agent.py` is the host, which builds with
  `core_agent.build`, runs with `core_agent.turn` and translates the `Log` to an `Answer`;
  `sale.py` and `effects.py` are the two channels that travel with the client, with
  what is read from each. Until Sep 22, 2026 the two halves shared the
  `core_agent/` package, when the example was four loose files.
- `cli.py` and `evals/suite.py` are the agent's other two hosts: the terminal and the
  quality suite. The eval captures go to `evals/runs/`, out of git.
- `routes/` are the endpoints: `queries` (REST), `a2a` and `health`.
- `tests/` repeats the folders of what it tests, and each test is named like the
  module it tests. `tests/host/` and `tests/test_routes.py` test the host with
  a two-datasheet bundle built by `conftest.py`, with catalejo's `ScriptedModel`
  as model and the doubles in `doubles.py` as judge and compactor.
  `tests/core_agent/` tests the agent (the contract, the index, the sale
  gates) on `okf/`, with the same doubles: a new gate is taught to them
  there, once. `tests/evals/` tests the suite's arithmetic.

## catalejo and the catalog

Both travel in the repo, so the image is a single artifact with nothing to mount.
For the catalog this is today's solution, not the final one: when it grows or is edited by
people who do not touch this repo, something else will be needed (a mounted bucket, or
serving it from the catalog's repo).

The catalog is `okf/`, the bundle of Agroinsumos Ceiba, a fictional company. It lives in this
repo and is edited here: the datasheets in `okf/products/`, the voice in `okf/voice.md`, and
`okf/verify.sh` checks the format before committing. `voice.md` is who serves: the
sales persona the writer takes as the first paragraph of its contract
(`core_agent/roles/writer.py`). It lives at the bundle root and not in `company_info/` on
purpose: it is not corpus, the searcher neither greps it nor cites it.

catalejo travels as a wheel in `vendor/`, without PyPI: `pyproject.toml` declares it in
`[tool.uv.sources]` and `uv.lock` keeps its sha256. When you change `../catalejo`
(the library's live tree), rebuild the wheel, leave a single one in `vendor/` with its commit in
`vendor/ORIGEN`, update
the path in `pyproject.toml` if the version changed and refresh the lock hash.
Only the library: the agent no longer comes from there. Without the lock refresh the
Dockerfile fails on `uv sync --locked`, which is on purpose: a wheel different from
what the lock says is not deployed silently.

## Deploy

`scripts/deploy.sh secrets` then `scripts/deploy.sh` put the demo on Cloud Run. It runs on one instance
because the chat sessions and the turn cap (`DEMO_TURNS`) live in the process.

The `Dockerfile` builds the app with the bundle in `okf/`. It needs `MUSE_API_KEY` and
`TYPESAFE_API_KEY` in the environment; `/health` says why the advisor did not start. `/queries` and
`/a2a` ask for a bearer token when `ISSUER` is configured (`src/auth.py`).

## Endpoints

- `GET /` — the chat page
- `POST /chat` — `{"session": "...", "text": "...", "image": "data:image/jpeg;base64,...", "audio": "<WAV in base64>"}`, no login, capped by `DEMO_TURNS`
- `POST /queries` — `{"question": "...", "history": [{"question": "...", "answer": "..."}], "sale": [...], "effects": [...]}`
- `GET /queries/catalog` — how many datasheets are loaded and how many slots are free
- `GET /health` — whether the process is alive and whether the advisor got built

## A2A

The same advisor, spoken to as an agent so that another agent can consult it.

- `GET /.well-known/agent-card.json` — the card (and `/.well-known/agent.json` for
  0.2 clients)
- `POST /a2a` — JSON-RPC 2.0, method `message/send`, blocking

The `result` is a Message with two parts: the answer text and a part of
`kind: "data"` with `kind: "agro_evidence"` inside, where `sources`,
`grounded`, `tokens` and `fails` travel. `contextId` and `taskId` are echoed without being regenerated.
When the answer is not grounded an event comes out in `result.metadata.guardrails`
in the shape the `platform-webapp` client already normalizes.

There is no `message/stream` or `tasks/get`: both need a task store this
service does not have, and they answer `-32004 UnsupportedOperationError`.

The previous turns are sent by the client, same as in REST: a part of
`kind: "data"` with `{"history": [{"question", "answer"}]}`, or
`params.metadata.history`. The sale and the effects travel in the same place,
`{"sale": <ops>}` and `{"effects": <ops>}`, where each `<ops>` is
`agro_evidence.sale.ops` and `agro_evidence.effects.ops` of the previous
answer as is (the whole block is valid too). A malformed op is `-32602`
with the index.

```bash
curl -s localhost:8000/a2a -H 'content-type: application/json' -d '{
  "jsonrpc":"2.0","id":1,"method":"message/send",
  "params":{"message":{"role":"user","messageId":"m1",
    "parts":[{"kind":"text","text":"what do I use for thrips on tomato?"}]}}}' | jq '.result.parts[0].text'
```

```bash
curl -s localhost:8000/queries -H 'content-type: application/json' \
  -d '{"question":"what do I use for thrips on tomato?"}' | jq
```

## The sale

The sale plan lasts the conversation and this service keeps nothing between
calls, so its moves travel with the client like the history. Each
answer brings `sale`:

- `ops`: the complete moves after the turn. It is the only thing to keep
  and send in the next request (`sale` in REST, `{"sale": ops}` in A2A), as
  is. They are opaque: there is no need to read or edit them.
- `state`: one line, "sale 3/8: next `quantity`".
- `stage` and `active`: the open root stage (`diagnosis`, `payment`, `billing`) and
  leaf; empty when the sale closed.
- `asks`: `{"id", "what"}`, what to ask the customer now (the pest, the
  area, whether they want it, how they pay, the invoice details), or `null` if what comes next
  is the advisor's work (reading the datasheet, giving the account) or nothing is left. The
  writer already asks it at the end of its answer; this is for whoever runs
  the conversation.
- `pending` and `closed_steps`: the plan's leaves, in order. `closed`: none is left
  open. `tree`: the drawn checklist, for logs and for eyes.

- `judgment`: what the gates saw this turn. `state` is the JSON the
  model wrote with the customer's words so far (it picks the fields
  itself: crop, pest, area, payment method, NIT...); `p` is the probability, per
  gate that was still open, that the customer has already said it
  (`has_search_terms`, `said_area`, `wants_to_buy`, `said_payment_method`,
  `said_billing_data`; the closed ones are not asked again); `error`
  says why there was no judgment, if there was none. `null` when the turn did not
  ask the judge anything. It is for reading why the sale asked what it asked; it is not
  sent back.

Each answer also brings `rules`, one entry per rule in the bundle's `governance/`
(the judge's questions and the code gates, with their id `domain/rule_tag`),
whether it fired or not: `{"id", "p", "threshold", "fired", "action"}`, and `option` on the
escalation reason. `sale/datasheet` and `sale/presentation` bring `lines`, the
judge's choice on each cart line with its p, and the rule's `p` is the
lowest. It brings what `judgment` does not: the case of the turn, the p's of the
answer (the guardian) and the order gates. `p` is `null` if the rule was not
asked this turn; with the case down, the four case lines come out with
`fired: true` and `p: null`, because the writer received them all. It is for auditing;
it is not sent back.

Without `sale` in the request it is the first turn: the plan is seeded and the gates
close with what the history says, so a client that never returns `ops`
loses only what the advisor closes (`charge`) and what the model adds.
Returning them costs one field and loses nothing.

The host side is written once, in `../clients/agro-client.py`: one
conversation per key (history, `plan_actions` and `effect_actions`, the `ops`
of the two channels) kept in Redis or in a file, 24 h like the
host's sessions, a `turn()` that sends what is kept and keeps what comes back, and
the sending of `effects.pending` with its `done`/`reject` (see "The
effects"). There the channel is the terminal: whoever plugs in WhatsApp replaces
`mandar_por_la_terminal` and nothing else. On Sep 20, 2026 this service had
for a few hours its own memory in Redis (`sesion`, `contextId`); it was removed
that same day because the conversation state belongs to the host, and a service
that also keeps it has two truths.

The gates the customer closes (what they are looking for, the area, whether they buy, how they pay,
the invoice details) are judgments and not patterns (`core_agent/world/question_judge.py`): once
per turn the model compacts the conversation into a JSON with the customer's
words, and TypeSafe answers, on that state, the questions of the
slots still open. It is catalejo's `close_steps` cell, at the edge
of the turn: on the way in it closes what the customer just said, on the way out
what the turn did (it queried, opened a datasheet, read the payment methods). A
gate closes with `p >= 0.8`; the searcher is skipped only with `pest` open
and `p < 0.2` that there is something to look for, and with `pest` closed it searches without
asking. Until Sep 18, 2026 they were regexes on the customer's words, and
"zompopo on the coffee" closed nothing: the searcher did not run and the writer
asked which pest it was (round 16). If TypeSafe does not answer, the sale does not
move that turn (`fails` brings `plan: the judge blew up: JudgeError`), the
searcher runs anyway and the answer is served; it resumes when it comes back. It costs
~1k TypeSafe tokens (USD 0.00004) and one short model call per turn.

## The effects

The advisor talks; it sends nothing. When the customer asks for a product's datasheet or
the bank account, the turn PROPOSES it as a move and whoever has the
WhatsApp executes it. This service does not have it either, so it acts as a leash: the
moves come in on the request (`effects`), go out accumulated the way the sale does, and
what is left to send comes out separately. Each answer brings `effects`:

- `ops`: the complete moves after the turn. Like the sale's: they are
  kept and returned as is on the next request.
- `pending`: what has to be sent WITH THIS MESSAGE. Each one brings `id`
  (`send_datasheet`, `send_payment_accounts`, `handoff`), `kind` (`document`,
  `bank_account`, `handoff`),
  `args` (for the datasheet, a `["path", "products/x.md"]` for each one the
  answer cited) and `executable`.
- `state`: one line with each effect and how it ended up, for logs.

Whoever sent it closes it on the next request, adding to `ops` a
`{"verb": "done", "id": ..., "note": "<the send reference>"}`, or a
`{"verb": "reject", "id": ..., "note": "<the reason>"}` if `executable` came
false (the answer cited no datasheet, so there is no PDF to send). A
client that returns neither breaks nothing: the effect stays
proposed and is not proposed or announced again. A client that does not return
`ops` does: the channel is the only thing that remembers the datasheet already went out, because
the judgment is about what the customer said in the whole conversation.

The writer knows about the send BEFORE writing, as it knows about the sale: it comes in
as one more line in its request ("with this message the system sends them the datasheet
of each SOURCE you cite"), and that is why the answer says it is attached instead of
transcribing it. The proposer is the same sale judge, with two more questions
in the same TypeSafe request (`asked_for_the_datasheet`, `asked_for_the_account`), never the
model: a catalog datasheet cannot ask for anything to be sent. The account
also requires `wants_to_buy`, so it does not go out to someone comparing
prices. Nothing executes inside the turn: a send there would fall outside
catalejo's laws (a retry would send it twice).

### The escalation

When the answer leaves the customer without what they asked for ("that is not in the
datasheet", "we do not carry it", "transfer only") or brings something the advisor does not
solve however well it answers (a complaint, a warranty, a discount), the
turn proposes a `handoff`: `{"id": "handoff", "kind": "handoff", "args":
[["origin", "requested_by_agent"], ["reason", "<reason>"]]}`. The reason is
a key of `core_agent.HANDOFF_REASONS`, the CRM reasons. It is judged on the answer
already written, with two questions that travel in the TypeSafe request the sale was already
making: it does not cost one more request or a model call.

It is routed by `kind`: a `handoff` is not sent over WhatsApp, it opens a case in the
CRM, and the `done` that comes back carries the case id. It is one per conversation: with
the `handoff` in `ops`, open or closed, no other is proposed. What the end
customer reads of the escalation is not written by the writer, which does not find out: it is decided
by whoever knows whether someone is on the other side and how long they take.

## What to look at in the answer

`answer` is the prose without the `SOURCE:` lines, which go in `sources`: what
the model writes at the foot is for this service, not for whoever reads the WhatsApp.

`grounded: false` means the model answered without having queried the
catalog: it is an opinion, not data, and an invented dose gets applied on a real
hectare. Empty `sources` says the same from another side. The exception
is `no_search_terms: true`: the conversation has not yet given a pest or product to
search with (the judgment in `sale.judgment` says so), the searcher did not run and the
answer is the question. It is not an opinion, and A2A does not send the
`guardrails` notice in that case.

`fails` with `cita: cited paths that do not exist: ...` means the model did
query, but closed with a `SOURCE:` that is not in the corpus and held it
after the notice. `grounded` stays true; the citation is what does not hold up.

`truncated: true` means the turn passed `TIMEOUT_S`: the loop cancelled the step that
overran and returned what there was, with `loop: time cap: N/N s` in `fails`,
signed by the role (`searcher/loop` is the searcher). Without prose,
that is a 504 in REST and a `-32603` in A2A, with that detail; with prose (the
writer wrote with the report half done) it comes out 200 with the mark, and `grounded`
says what it is worth. `seconds` is what the customer waited that turn. `turns`
counts the messages of the two roles.

`GET /queries/catalog` also brings `model`, the adapter's count since
the process started (`calls`, `attempts`, `seconds`, `slowest`), if the
provider keeps it (OpenAI does, Gemini does not). `attempts` above `calls`
are POSTs that did not come back with a body, and `slowest` near the httpx timeout
with extra attempts is the API hanging, not the model thinking.

## Config

Everything through `.env` (see `.env.example`). What gets touched: `PROVIDER` (`muse` by default,
`openai`, `gemini` or `anthropic`, with its key), `MODEL` and `THINKING` (empty means the ones in
`core_agent.provider`: muse-wonder-1.0 with medium; a name goes as is to the provider), `RETRIES`, `SLOTS`
(queries in parallel), `TIMEOUT_S` and `BUNDLE_DIR`. The agent's caps
(steps, window, the writer's REPL) are set by the `core_agent/` package as in
the CLI and are not configured here: what is not there does not exist yet. The timeout
per provider call too: 40 s (`core_agent.agent.TIMEOUT`, which
`lifespan.agent.CALL_TIMEOUT` reads), below the per-role cap, so that a hung call
retries instead of eating the role (in round 16 it happened four times in 60
turns with the 120 s default).

`TYPESAFE_API_KEY` is the one for the judge of the sale gates (see "The sale")
and it is required: without it the advisor does not start and `/health` says why. The
agent knows how to run without a judge (the sale warns on each turn because nobody
answers), but a server that starts that way serves a sale that never closes
anything. There is no fallback to a pattern. In prod it is a Secret Manager secret
mounted as env, like the provider's.

`TIMEOUT_S` (90) is the seconds a turn can last, and it goes inside the
loop as `deadline` and not as a `wait_for` outside: a request to the API that
hangs returns nothing to look at, and the `wait_for` that cut it also threw away
the good steps before. It has to stay below the 120 s with which
`knowledge` cuts `message/send` on the host side; with 180 the host gave up
before this service. The number comes from the `time` line of `evals/suite.py`
on the real bundle (round 15 of the logbook, Sep 17, 2026, this same config):
138 turns, p95 of 14 to 20 s, max 21 s, none cut. 90 is four times
the max; a cap below the p95 would cut good turns. The cap goes to each
role (each one has its loop), so it splits: 45 s to the searcher and 45 to the
writer, and the worst case of the turn is still 90.

`CONTAINER` (`core_agent.build(contained=True)`) runs the model's code in a
child process, one `spawn` per query; what the model sees does not change. On
since Sep 17, 2026 because of the time cap: when the loop cancels the step that
overran, with the child the half-done `exec` is killed and the slot comes back; in process the
thread keeps running with a workspace nobody looks at anymore. It is the only agent lever
left: `CITAS`, `ONTOLOGIA`, `NOTAS`, `DOS_PASOS`, `UNO_POR_PASO`,
`ORCHESTRATE`, `VISTA` and `VOZ` belonged to the one-loop agent and the current one has them
fixed at what was measured (ontology and notes on, two steps, the whole datasheet, the
bundle's voice, the sale as one line).

Two things from the CLI always go, with no variable. The bullet that says that without a pest or
product the answer is the question, in prose (the model did it with `print`
eleven times in a row): that turn comes out with `grounded: false`, which is true. And
`printed`: when the model writes the whole answer inside a `print`
with its `SOURCE:` (30 of 630 turns measured), that is the answer and not one more
turn.

There is no cache or state: each query is recomputed, and that is 14 to 45 thousand tokens and 10
to 31 seconds each, measured with the one-loop agent; the orchestrated one pays
around a quarter more. `PUBLIC_URL` is used only by the A2A card.
