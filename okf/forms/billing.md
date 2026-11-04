---
type: reference
title: "Billing details"
description: "The fields the agro advisor notes down to invoice and deliver an order, with their label, their type and whether they are required."
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-08T00:00:00-06:00 }
---

The form the advisor fills in while selling: the invoice and delivery data, and how they pay. It is
read by `core_agent/world/form.py`; the host draws it as the "Billing details" card with
`form_schema`. The order does not go here: it is its own card, and its prices come from the
datasheets.

Each field is noted in the customer's words and carried from turn to turn: only what the customer
gives or corrects changes. The advisor asks for the first required field missing, in the `order`
order. The order is ready to charge when all the required fields are in.

- `legal_name`: who the invoice is made out to, if it is a company or not the person receiving.
- `nit`: the NIT with its hyphen if it has one ("1234567-8"), or "CF" if they said final consumer
  or that they have no NIT.
- `recipient`: the name of the person receiving the order. "I'll receive it" is the name of whoever
  is speaking.
- `phone`: the phone of the person receiving.
- `email`: the email to send the invoice to, if they gave it. It is not asked for: it is optional.
- `address`: the full delivery address, with the municipality and the department if they said them.
- `payment_method`: how they pay, one of the house's two ways (`company_info/payments.md`). The form
  model does not note it: it comes from the judge's `payment_method` label.

# Fields

```json
{
  "fields": [
    {"id": "legal_name", "label": "Legal name", "type": "text", "required": false, "order": 1},
    {"id": "nit", "label": "NIT", "type": "text", "required": true, "order": 2},
    {"id": "recipient", "label": "Recipient", "type": "text", "required": true, "order": 3},
    {"id": "phone", "label": "Recipient's phone", "type": "tel", "required": true, "order": 4},
    {"id": "email", "label": "Email", "type": "email", "required": false, "order": 5},
    {"id": "address", "label": "Delivery address", "type": "textarea", "required": true, "order": 6},
    {"id": "payment_method", "label": "Payment method", "type": "select", "required": true, "order": 7, "options": ["link", "transfer"]}
  ]
}
```
