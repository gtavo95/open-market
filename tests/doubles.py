"""The test doubles of the gates: a scripted judge and a model that compacts without thinking.

The gates of the sale are judgments (`core_agent/world/question_judge.py`): the model compacts what
the customer said and TypeSafe reads it. Neither of the two enters a test. Here
the judge answers by keywords over the state, high if the word is there and
low if not, and the compactor returns the conversation as it is in a JSON. With
that a sale test asserts the same as before ("whitefly" closes
`pest`, "two liters" closes `quantity`) with no network and without the result
depending on a model.

The keywords belong to the double and nobody else: in the agent there are no lists.

A single one for the host tests (`tests/host/`) and the agent tests (`tests/core_agent/`):
until Sep 22, 2026 they were two copies, `dobles.py` and `doubles.py`,
because the agent lived in catalejo. A new gate is taught here.
"""

from __future__ import annotations

import json
from typing import Any

from catalejo.core import Conversation, Message, Role
from core_agent.world import typesafe
from core_agent.world.question_judge import QuestionJudge
from core_agent.prompts.judge import CART_PROMPT, COMPACT, FORM_PROMPT, SAID_PROMPT
from catalejo.llm import Reply

WORDS: dict[str, tuple[str, ...]] = {
    "has_search_terms": ("whitefly", "fly", "thrips", "larvane", "fungvane", "leafcutter ant", "insecticide", "borer", "worm"),
    "said_quantity": ("two liters", "three liters", "gallon", "container", "jug"),
    "wants_to_buy": ("i want it", "how do i pay", "want to buy"),
    "said_billing_data": ("nit",),
    "gives_billing_data": ("nit", "address to"),
    "asks_for_order_summary": ("what do i have",),
    "asks_to_start_over": ("delete it", "start over"),
    "asked_for_the_datasheet": ("the datasheet", "the sheet", "the pdf"),
    "asked_for_the_catalog": ("i want the catalog", "your catalog", "product list"),
    "recommended_a_product": ("recommend", "certified", "l/ha"),
    "hands_off_to_a_person": ("i'll escalate", "pass you to"),
    "did_not_give_what_was_asked": ("is not in the datasheet", "not listed", "we do not have"),
    "asks_for_the_unsolvable": ("arrived damaged",),
}
"""Which word of the state, or of the advisor's answer, makes the scripted judge say yes to each gate."""

LABEL_WORDS: dict[str, tuple[str, ...]] = {
    "account": ("the account", "account number"),
}
"""The options of a label that are not recognised by their name: "account" is in the compaction prompt."""

HIGH = 0.95
LOW = 0.05

INVOICE = {"nit": "1234567-8", "recipient": "Rodrigo Pérez", "phone": "5555-0101", "address": "zona 5, Quetzaltenango"}
"""The changes `Echo` answers to the form request when the last message names the NIT: everything but the legal name."""

FORM_HEAD = FORM_PROMPT.split("{fields}")[0].replace("{{", "{").replace("}}", "}")
"""How the built form request starts: up to the list of fields."""


class ScriptedJudge(typesafe.Client):
    """Scripted TypeSafe: `HIGH` if any word of `WORDS` is in the state, `LOW` if not.

    A `choice` is answered apart: `label` overrides it with an option, and if not,
    it picks the first key of `criteria` named in the state and, if
    none is, the last one, which in the real tables is the unclassified
    one. The double knows no taxonomy.

    `fixed` overrides a gate with a number, to test the threshold. `down`
    makes every request raise, to test what happens with no judge.
    """

    def __init__(
        self, fixed: dict[str, float] | None = None, *, down: bool = False, label: str = ""
    ) -> None:
        self.asked: list[dict[str, Any]] = []
        self.calls = 0
        self.tokens = 0
        self.model = "scripted"
        self._fixed = fixed or {}
        self._down = down
        self._label = label

    async def ask(self, state: Any, questions: dict[str, Any]) -> typesafe.Response:
        self.asked.append({"state": state, "questions": questions})
        if self._down:
            raise typesafe.TypeSafeError("HTTP 503: no judge")
        self.calls += 1
        self.tokens += 100
        typesafe.charge(100)
        text = json.dumps(state, ensure_ascii=False).lower()
        answers: dict[str, Any] = {}
        for name, question in questions.items():
            if question.get("type") == "choice":
                chosen = self._choose(question, text)
                probabilities = {o: (HIGH if o == chosen else LOW / len(question["criteria"])) for o in question["criteria"]}
                answers[name] = {"type": "choice", "choice": chosen, "probabilities": probabilities}
                continue
            p = self._fixed.get(name)
            if p is None:
                p = HIGH if any(k in text for k in WORDS.get(name, ())) else LOW
            answers[name] = {"type": "noul", "noul": p}
        return typesafe.Response(answers=answers, tokens=100, model="scripted")

    def _choose(self, question: dict[str, Any], text: str) -> str:
        """The option overridden by `label`, or the first one named in the state, or the last one."""
        options = list(question["criteria"])
        if self._label:
            return self._label
        return str(next((o for o in options if any(k in text for k in LABEL_WORDS.get(o, (o,)))), options[-1]))

    async def aclose(self) -> None:
        pass


class Echo:
    """The model that compacts in the tests: it returns what it was told, in a JSON, without thinking.

    To the cart request, if what was said has a quantity word from `WORDS`,
    it answers a `cart` with a line of Reapvane (a title as it is, which does not go to the judge) with
    quantity, so that `order_with_quantities`
    closes `quantity` with the same thing that used to close `said_quantity`. To the form one,
    `INVOICE` as changes if the last message names the NIT, "Cobán" in `address` if it says
    "address to", and if not, no change.
    """

    model = "echo"

    def __init__(self, *, down: bool = False, spent: int = 7) -> None:
        self.conversations: list[Conversation] = []
        self._down = down
        self._spent = spent

    async def complete(self, conv: Conversation) -> Reply:
        self.conversations.append(conv)
        if self._down:
            raise RuntimeError("the model did not answer")
        text = conv[-1].text
        if text.startswith(SAID_PROMPT):
            return Reply(Message(Role.ASSISTANT, json.dumps({"already_said": [], "asks_again": []})), spent=self._spent)
        if text.startswith(FORM_HEAD):
            last = text.rsplit("Customer: ", 1)[-1].lower()
            changes = INVOICE if "nit" in last else {"address": "Cobán"} if "address to" in last else {}
            return Reply(Message(Role.ASSISTANT, json.dumps({"changes": changes}, ensure_ascii=False)), spent=self._spent)
        if text.startswith(CART_PROMPT):
            said = text.removeprefix(CART_PROMPT)
            rows = [{"product": "Reapvane", "presentation": None, "quantity": 2}]
            state: dict[str, Any] = {"cart": rows if any(k in said.lower() for k in WORDS["said_quantity"]) else []}
        else:
            state = {"said_raw": text.removeprefix(COMPACT)}
        return Reply(Message(Role.ASSISTANT, json.dumps(state, ensure_ascii=False)), spent=self._spent)

    async def aclose(self) -> None:
        pass


class Said(Echo):
    """The model that compacts with a fixed state: to test what the judge does with fields Echo does not write."""

    def __init__(self, state: dict[str, Any], *, spent: int = 7) -> None:
        super().__init__(spent=spent)
        self._state = state

    async def complete(self, conv: Conversation) -> Reply:
        self.conversations.append(conv)
        return Reply(Message(Role.ASSISTANT, json.dumps(self._state, ensure_ascii=False)), spent=self._spent)


def question_judge_with(
    fixed: dict[str, float] | None = None,
    *,
    down: bool = False,
    silent: bool = False,
    label: str = "",
    **kw: Any,
) -> QuestionJudge:
    """A scripted `QuestionJudge`: `down` with no judge, `silent` with no model to compact, `label` with the reason overridden."""
    return QuestionJudge(ScriptedJudge(fixed, down=down, label=label), Echo(down=silent), **kw)


__all__ = ["INVOICE", "HIGH", "LABEL_WORDS", "LOW", "WORDS", "Echo", "ScriptedJudge", "question_judge_with"]
