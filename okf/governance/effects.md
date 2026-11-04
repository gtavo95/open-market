---
type: governance
schema: agro/governance/v1
domain: effects
label: "What the customer asked to be sent"
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-03T17:25:19Z }
---

The effects the advisor proposes and the host executes (`EFFECT_RULES` in `roles/effects.py`). Each
one goes out when the customer asked for it, not when it would be useful: the datasheet goes to
whoever asked for it. The account also requires `sale/wants-to-buy_tag`, and the link also
`sale/chargeable-order_tag`.

`effects/link_tag` and `sale/said-payment-method_tag` read the same label and are not the same fact:
"I'll pay by transfer" named a method and did not ask for a link.

| id | question | type | reads | threshold | action | crm_reason | same_fact |
|---|---|---|---|---|---|---|---|
| effects/datasheet_tag | asked_for_the_datasheet | noul | conversation | 0.8 | proposes:send_datasheet |  |  |
| effects/catalog_tag | asked_for_the_catalog | noul | conversation | 0.8 | proposes:send_catalog |  |  |
| effects/account_tag | payment_request=account | choice | conversation | 0.8 | proposes:send_payment_accounts |  |  |
| effects/link_tag | payment_method=link | choice | conversation | 0.8 | proposes:send_payment_link |  |  |
