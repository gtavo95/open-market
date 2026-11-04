---
type: governance
schema: agro/governance/v1
domain: escalation.outbound
label: "What the answer said"
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-03T17:25:19Z }
---

The questions about the answer already written (`REPLY_QUESTIONS`), with what the customer said
next to it. `recommended_a_product` closes the sale's `product` step and is here because it reads
the same thing as the guardian, in the same request.

The guardian is three questions, one per family, and it escalates if any of them passes 0.5. Until
Oct 3, 2026 it was a single one, `needs_a_person`, which mixed the three and repeated eight rules
without saying which. Now each one says what it repeats:

- `hands-off-to-a-person`: the writer says she is handing it to someone. It repeats nothing: it is
  what she promised, and if she promised it someone has to see it.
- `did-not-give-what-was-asked`: the advisor ran out of the data or the product. It is the net under
  `case`, which already escalates `not_covered`, `discontinued` and `no_data` before writing; it
  stays for when the case came out `normal` and the answer still did not have it.
- `asks-for-the-unsolvable`: the customer brings something the advisor does not solve. It is the
  net under `escalation.inbound`, with threshold 0.5 and not 0.8; the only thing it decides alone is
  the discount.

The reason is chosen by `escalation.outbound/reason_tag` among those that do not turn the advisor
off.

| id | question | type | reads | threshold | action | crm_reason | same_fact |
|---|---|---|---|---|---|---|---|
| escalation.outbound/recommended-a-product_tag | recommended_a_product | noul | answer | 0.8 | closes:product |  |  |
| escalation.outbound/hands-off-to-a-person_tag | hands_off_to_a_person | noul | answer | 0.5 | handoff |  |  |
| escalation.outbound/did-not-give-what-was-asked_tag | did_not_give_what_was_asked | noul | answer | 0.5 | handoff |  | case/not-covered_tag, case/no-data_tag |
| escalation.outbound/asks-for-the-unsolvable_tag | asks_for_the_unsolvable | noul | answer | 0.5 | handoff |  | escalation.inbound/complaint_tag, escalation.inbound/return_tag, escalation.inbound/their-order_tag, escalation.inbound/invoice_tag, escalation.inbound/credit-or-check_tag |
| escalation.outbound/reason_tag | escalation_reason | choice | answer | argmax | handoff |  |  |
