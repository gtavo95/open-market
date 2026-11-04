---
type: governance
schema: agro/governance/v1
domain: escalation.inbound
label: "What the business does not do"
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-03T17:25:19Z }
---

What the customer brings and the advisor cannot solve no matter how well it answers: it is known
before the writer writes, so she says she is handing it to a person and the host turns the advisor
off (`HANDOFF_ASKED` in `roles/human_handoff.py`). With two above the threshold, the highest wins.

The threshold is the sale's and not the guardian's: at the entrance a false yes makes the writer
announce an escalation nobody needed. Discounts are not here because the house gives no discounts
and `voice.md` says so; nobody needs to be consulted.

| id | question | type | reads | threshold | action | crm_reason | same_fact |
|---|---|---|---|---|---|---|---|
| escalation.inbound/complaint_tag | brings_a_complaint | noul | conversation | 0.8 | takeover | quality_complaint |  |
| escalation.inbound/return_tag | asks_for_return | noul | conversation | 0.8 | takeover | warranty_return |  |
| escalation.inbound/their-order_tag | asks_about_their_order | noul | conversation | 0.8 | takeover | quote_not_found |  |
| escalation.inbound/invoice_tag | corrects_an_invoice | noul | conversation | 0.8 | takeover | billing_data |  |
| escalation.inbound/outside-guatemala_tag | shipping_outside_guatemala | noul | conversation | 0.8 | takeover | out_of_coverage |  |
| escalation.inbound/credit-or-check_tag | payment_method=credit,check | choice | conversation | 0.8 | takeover | card_payment |  |
