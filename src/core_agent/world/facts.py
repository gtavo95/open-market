"""The facts of the turn: what is read from the Log without asking anyone.

`LOG_FACTS` are the four that close steps of the sale, and `facts(LOG_FACTS)`
turns them into a judge: 1.0 if the fact holds, 0.0 if not. They cost nothing, which is why
`judge` in `question_judge.py` puts them before the judge that goes to the network.
"""

from __future__ import annotations

from catalejo.core import Log, Predicate, Registry, Role
from catalejo.rlm import seen_paths


def answer_of(log: Log) -> str:
    """The last thing the assistant said in prose, or empty.

    In the `after` sale it is the answer the writer just wrote.
    In the `before` one there is no assistant in `said` (the history travels in the envelope),
    and empty means "this turn has not answered yet": it does not close and costs nothing.
    """
    for m in reversed(log.said):
        if m.role is Role.ASSISTANT and "```" not in m.text:
            return m.text.strip()
    return ""


def saw_file(prefix: str) -> Predicate:
    """Builds the gate "this file passed in front of the model's eyes".

    It is a floor and not a proof: if the file never appeared, the model could not
    have taken the data from there; that it appeared does not say it read or used it. The
    prefix picks the height: a folder asks for any file of that family, a
    whole file asks for that page.

    It looks at the user's turns in `said`, which is where the corpus reaches the
    model: the REPL outputs in the single-loop agent, the writer's request
    in the orchestrator. The parser is `seen_paths`, which lives next to the two
    formats and not here.
    """
    return lambda log: any(
        m.role is Role.USER and any(r.startswith(prefix) for r in seen_paths(m.text)) for m in log.said
    )


LOG_FACTS: Registry = {
    "queried_the_catalog": lambda log: log.reads > 0,
    "opens_a_datasheet": saw_file("products/"),
    "read_the_payment_methods": saw_file("company_info/payments.md"),
    "read_the_accounts": saw_file("company_info/bank-accounts.md"),
}
"""The four facts of the turn that close steps, and the rule for what can count as a fact.

They are deterministic and it is right that they are: "the model opened `products/`" is a
fact of the machine, not a reading of the customer. The gate is worth more than the
valve but it only looks at what is recorded in the Log, so it is written over facts
in the Log and never over what the Log would like to have. And it has to be as
specific as the claim the step upholds: the two for charging used to be
one, and querying the payment methods also closed the accounts step.

There is no citation gate (`evals` measures that) nor a "nothing failed" one, which would
be true at the first step, before it could fail.
"""
