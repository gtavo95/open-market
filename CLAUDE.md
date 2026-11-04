# open-market: behavior is fixed with data, not with code

What the agent understands and decides is said by a model reading text: the judge's questions
(`prompts/judge.py`), the writer's lines (`prompts/writer.py`) and the okf bundle
(`voice.md`, the datasheets, `company_info/`). When the agent gets it wrong, the fix is to change
that text and measure it. It is not fixed with an `if`.

## The test, before writing an `if`, a regex or a word list

Does this line decide **what the customer meant** or **what the agent does with that**? If so,
it does not go in code: it goes in a judge question, a writer line or the bundle.

Forbidden:
- Overriding, silencing or forcing what the judge read based on something else: the plan state, the turn,
  the product. Example discarded on Oct 1, 2026: turning off `ambiguous_order` when `pest` was already
  closed. The fix was telling the judge that a piece of data the advisor asked for is not ambiguous.
- Reading the customer's message with regex, `in`, `.lower()` or word lists to decide something
  ("if they say thanks…", "if they name a gallon…").
- Special cases by product, pest, customer or prod conversation.
- Business rules in Python that the bundle can state: prices, shipping, what is sold and what is not.

Allowed, because it moves data and does not interpret:
- Reading formats a machine writes: okf frontmatter and tables, the host's
  `[SYSTEM: … ad …]` marker, `[human-advisor]:`, `SOURCE:`, the judge's JSON.
- Arithmetic on numbers already decided: subtotals, the total, the Q1,500 cutoff.
- Wiring: the judge's output to a line by threshold (`THRESHOLD`), the sale plan and which
  leaf comes next, the effects the host executes.
- Observable facts of the `Log`: it opened a datasheet, it proposed an effect. Not what they mean.

When in doubt, it is data. If there truly is no other way, ask the user before
writing it, with the reason; a `logbook/todo.md` entry proposing it is not permission.

## How it gets fixed

1. Read what happened: the conversation, the searcher's report and what the judge read (the case of the
   turn, the nouls with their number). That is where you see which text was misread.
2. Change the exact word: a judge criterion or example, a writer line, a
   `voice.md` rule. The bundle is edited in `okf/` and checked with `okf/verify.sh`.
3. Measure it cheaply: the judge alone, on saved messages and some that must not change (under
   USD 0.01); then a probe in `evals/cases.tsv` with `python -m evals.ab`, with the cost
   stated beforehand.
4. The number goes in the docstring of the question or line you changed, and in `logbook.tsv`.

## Debt paid

On Oct 1, 2026 `world/order.py` stopped interpreting the order. The datasheet for each name and the
presentation are chosen by the judge (`product_question`, `presentation_question`) with the datasheets and the
`# Presentations` rows as options; the code only takes the title or the label as is, or
the only one there is. Before, they were a string similarity (`SequenceMatcher`) and a chat
units dictionary, with an `if` per case. If a choice comes out wrong, the question is fixed; code does
not go back in.
