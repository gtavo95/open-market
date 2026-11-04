# Governance

The rules with which the agro advisor decides something by reading text: each question to the judge
(a `noul` or a `choice` from TypeSafe) and each code gate that closes the same thing. One file per
domain, and the file name is the domain id. The reader skips this index.

It exists for the same reason as `ontology/`: two rules that decide the same fact diverge, and
nothing says so. On Oct 2, 2026 the guardian (`needs_a_person`, now split into three) stopped
escalating a discontinued product because the writer started saying "we don't carry X" instead of
"discontinued". The turn's case already knew it was `discontinued`, before the writer wrote, but
that rule and the guardian's lived in two places without knowing about each other.

## The table

| column | what it says |
|---|---|
| `id` | `domain/rule_tag`, stable. The `_tag` says it is a governed tag, a rule of this table, and not another judge key. It is what goes in `Answer.rules` |
| `question` | the key the judge answers, or the code gate. `label=a,b` is the sum of those options of a `choice` |
| `type` | `noul`, `choice` or `code` |
| `reads` | what it sees: `conversation`, `cart`, `report`, `answer`, `log` or `plan` |
| `threshold` | from what p it fires; `argmax` if the highest option wins; empty in `code` |
| `action` | what happens when it fires: `closes:<step>`, `proposes:<effect>`, `takeover`, `handoff`, `line:<table>`, `cart_line:<field>` |
| `crm_reason` | the key of the handoff reason it sends, if it sends one |
| `same_fact` | if it decides a fact another rule already decides, the id of that other one; several, separated by commas |

The one above is an explanatory table and that is why this index is not a domain: in a domain leaf
the only table is the rules table, as in `ontology/`.

## One fact, one rule

When two rules decide the same fact, the second declares it in `same_fact` pointing at the first,
and the first points at nobody. Declaring it does not fix it: it leaves it written down so anyone can
see what is left over.

`verify.sh` fails when two rules share the `question` or the `crm_reason` and neither declares the
other, when `same_fact` points at an id that does not exist or at a rule that in turn points at
another, and when the id prefix is not the file's domain or the id does not end in `_tag`. It cannot
see more than that: that a guardian question repeats the turn's case is not in any column that can
be compared, and a person declares it, just like an alias in the ontology.

## The domains

| domain | rules | what it decides |
|---|---|---|
| `sale` | 15 | what the customer has already said about the purchase, the order and the billing form |
| `effects` | 4 | what the customer asked to be sent |
| `escalation.inbound` | 6 | what the business does not do, before the writer writes |
| `alerts` | 1 | what the writer has to know about the message |
| `case` | 4 | what the searcher found |
| `escalation.outbound` | 5 | what the answer already written said |

Declared repetitions: `said_quantity`, which keeps being answered for the old plans;
`case/discontinued_tag`, which sends the same reason as `case/not-covered_tag`; and two guardian
questions, which are the net under `case` and `escalation.inbound` (see `escalation.outbound.md`).
