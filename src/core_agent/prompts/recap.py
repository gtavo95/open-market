"""What the model that summarizes the advisor's earlier answers reads (`world/recap.py`)."""

from __future__ import annotations

RECAP = """This is an answer that the advisor of an agricultural catalog already sent a customer over
WhatsApp. Summarize it so that the same advisor, on the next turn, knows what it already said and does
not repeat it. In a few lines, with no greetings or embellishment and adding nothing that is not there:
- the products it named, with the presentations, prices, quantities and totals it gave;
- the doses it gave;
- what it said about payment, shipping and the invoice: the payment methods; if it gave account
  numbers, say so this way, "gave the account numbers of <company> at <banks>", without copying them;
  the shipping cost and lead time;
- what it asked the customer for.
What the answer does not say stays out: no "gave no dose" or "did not mention shipping".
If the answer ends with a question to the customer, copy it verbatim on the last line, like this:
"Asked: <the question>".
Reply with the summary only.

The answer:
"""
"""The summary request. Account numbers stay out because they are not repeated from memory: if the
customer asks for them again, they come from the datasheet. The final question goes in verbatim because
the judge's compaction needs it to read a "yes" (see `COMPACT`)."""
