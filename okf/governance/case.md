---
type: governance
schema: agro/governance/v1
domain: case
label: "What the searcher found"
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-03T17:25:19Z }
---

What kind of turn this is, read from the last message and the searcher's report, without the
conversation (`TURN_CASES`). It is a `choice` and the highest option wins; `normal` has no line and
is not here. If the judge does not answer, the writer receives all four lines.

The case gives the writer a line (`CASE_LINES`), and since Oct 3, 2026 `not_covered`, `discontinued`
and `no_data` also escalate, with their reason (`CASE_HANDOFF` in agro). The escalation used to come
from the guardian, which read it afterwards in the answer, and a change of wording broke it even
when the case had been read correctly. None of them turns the advisor off. `discontinued` and
`not_covered` send the same reason: for the CRM it is the same fact, the customer was left without a
product.

| id | question | type | reads | threshold | action | crm_reason | same_fact |
|---|---|---|---|---|---|---|---|
| case/we-do-not-sell_tag | case=we_do_not_sell | choice | report | argmax | line:CASE_LINES |  |  |
| case/not-covered_tag | case=not_covered | choice | report | argmax | line:CASE_LINES, handoff | product_not_found |  |
| case/discontinued_tag | case=discontinued | choice | report | argmax | line:CASE_LINES, handoff | product_not_found | case/not-covered_tag |
| case/no-data_tag | case=no_data | choice | report | argmax | line:CASE_LINES, handoff | unverifiable_specification |  |
