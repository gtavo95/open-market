---
type: governance
schema: agro/governance/v1
domain: sale
label: "What the customer said about the purchase"
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-03T17:25:19Z }
---

The gates that close the steps of the sale plan (`SESSION` in `roles/sale.py`) and the ones that
build the order. Each `closes:<step>` is the `done_when` of that leaf. They read the compacted
conversation and not the answer: what the advisor replied is judged by `escalation.outbound`.

`order_with_quantities` and `chargeable_order` are code over the cart (`ORDER_GATES`), and the
datasheet and presentation of each line are chosen by the judge among those in the bundle.
`said_quantity` is the yes or no from before the cart: it keeps being answered because the plans the
host saved before the change still close `quantity` with it.

`complete_invoice` is code over the billing form (`forms/billing.md`): all the required fields
filled in. It closes `data` since Oct 8, 2026; `said_billing_data` is the yes or no from before the
form, and it keeps being answered for the saved plans. The three that look only at the last message
belong to the form and the cart: `gives_billing_data` makes the model note what the customer gave or
corrected, `asks_for_order_summary` gives the writer the order and the data with what is missing,
and `asks_to_start_over` empties the order and the form and tells the host.

`sale_completed` is code and not the judge: the plan already says they decided, how they pay and
gave the data.

| id | question | type | reads | threshold | action | crm_reason | same_fact |
|---|---|---|---|---|---|---|---|
| sale/has-search-terms_tag | has_search_terms | noul | conversation | 0.8 | closes:pest |  |  |
| sale/opens-a-datasheet_tag | opens_a_datasheet | code | log |  | closes:recipe |  |  |
| sale/order-with-quantities_tag | order_with_quantities | code | cart |  | closes:quantity |  |  |
| sale/said-quantity_tag | said_quantity | noul | conversation | 0.8 | closes:quantity |  | sale/order-with-quantities_tag |
| sale/wants-to-buy_tag | wants_to_buy | noul | conversation | 0.8 | closes:decision |  |  |
| sale/said-payment-method_tag | payment_method=link,transfer | choice | conversation | 0.8 | closes:method |  |  |
| sale/complete-invoice_tag | complete_invoice | code | form |  | closes:data |  |  |
| sale/said-billing-data_tag | said_billing_data | noul | conversation | 0.8 | closes:data |  | sale/complete-invoice_tag |
| sale/gives-billing-data_tag | gives_billing_data | noul | conversation | 0.8 | fills:form |  |  |
| sale/asks-for-order-summary_tag | asks_for_order_summary | noul | conversation | 0.8 | line:SUMMARY_LINE |  |  |
| sale/asks-to-start-over_tag | asks_to_start_over | noul | conversation | 0.8 | restarts |  |  |
| sale/datasheet_tag | datasheet | choice | cart | argmax | cart_line:product |  |  |
| sale/presentation_tag | presentation | choice | cart | argmax | cart_line:presentation |  |  |
| sale/chargeable-order_tag | chargeable_order | code | cart |  | proposes:send_payment_link |  |  |
| sale/completed_tag | sale_completed | code | plan |  | takeover | sale_completed |  |
