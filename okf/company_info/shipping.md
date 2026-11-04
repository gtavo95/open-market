---
type: company-info
title: "Shipping"
description: "Cost, time and coverage of shipping inside and outside Guatemala."
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-09T12:00:00-06:00 }
---

# Shipping

## Guatemala

Orders go out by courier.

- Cost: Q40
- Free shipping when the invoice is over Q1,200. When the order pays for shipping, the customer is
  told this cutoff: it is how to avoid paying it
- Delivery: 3 to 5 business days

**The Q40 is charged only once for purchases within the same 24-hour interval.**

When it has to be charged, the customer pays the Q40 in cash to the courier on receiving the order.
It is never included in the payment link or the bank transfer.

**When shipping is free it is not mentioned.**

## Outside Guatemala

Shipments to other countries are coordinated one by one with an administrator, who defines the
logistics and the cost. Without that consultation no prices or estimated times are given.

# Rules

```json
{
  "schema": "company/shipping/v1",
  "country": "guatemala",
  "carrier": "courier",
  "cost": { "amount": 40, "currency": "GTQ" },
  "free": {
    "amount": 1200,
    "currency": "GTQ",
    "comparison": "strictly_greater",
    "measured_on": "invoice",
    "one_invoice_is_enough": true
  },
  "single_charge_hours": 24,
  "paid": "cash to the courier, on receiving the order",
  "never_in": ["link", "transfer"],
  "if_free": "do not mention shipping",
  "if_charged": "state the cost and that it is free when an invoice passes the cutoff",
  "delivery_business_days": { "min": 3, "max": 5 },
  "outside_guatemala": { "rate": null, "action": "escalate to an administrator" }
}
```
