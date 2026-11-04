---
type: company-info
title: "Bank accounts"
description: "Which account an order's payment is transferred to."
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-09T12:00:00-06:00 }
---

<!-- Fictional accounts of the demo bundle. The banks and the numbers do not exist: nobody can
     transfer to a real person by mistake while watching the demo. -->

# Bank accounts

All are checking accounts in the name of Agroinsumos Ceiba, S.A.

## Agroinsumos Ceiba, S.A.

Quetzales (GTQ)

| Bank | Account number |
|---|---|
| Banco Demo | 000-000001-1 |
| Banco Ejemplo | 0000000002 |

Dollars (USD)

| Bank | Account number |
|---|---|
| Banco Demo | 000-000003-3 |

## Notifying the payment

The receipt is sent through the same channel where the order was placed, or to collections:

- cobros@ceiba.example
- +502 0000 0002

# Rules

```json
{
  "schema": "company/collection/v1",
  "default_beneficiary": "Agroinsumos Ceiba, S.A.",
  "exceptions": [],
  "accounts": [
    { "company": "Agroinsumos Ceiba, S.A.", "currency": "GTQ",
      "bank": "Banco Demo", "number": "000-000001-1" },
    { "company": "Agroinsumos Ceiba, S.A.", "currency": "GTQ",
      "bank": "Banco Ejemplo", "number": "0000000002" },
    { "company": "Agroinsumos Ceiba, S.A.", "currency": "USD",
      "bank": "Banco Demo", "number": "000-000003-3" }
  ],
  "payment_notice": {
    "channel": "the same one where the order was placed",
    "email": "cobros@ceiba.example",
    "phone": "+502 0000 0002"
  }
}
```
