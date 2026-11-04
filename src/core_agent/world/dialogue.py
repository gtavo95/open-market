"""The turn's envelope: how the conversation enters the request and how it is taken apart afterwards.

`wrap` builds the first message of the Log with what was spoken in front and the current
question, and `customer_words` and `conversation` take it apart. It lives apart from
the roles because two sides that do not import each other read it: the agent,
which seeds it in `turn`, and the sale's gates
(`question_judge.py`), which look for the customer's words where they always are, without
importing the whole agent for that.

The history goes in as it comes: nothing is trimmed. Long answers arrive already
summarized (`world/recap.py`), because a two-thousand-letter answer per turn
is paid at every step of the loop; until Sep 25, 2026 they were cut at
500 letters, and what was left out did not exist for the writer or for the
judge. The `Q:` lines, the customer's, always go verbatim: the gates come
from there.
"""

from __future__ import annotations

from catalejo.core import Log

SPOKEN = "[what we have talked about in this session]"

NOW = "[the current question]"

CUT = "\n\nTo answer this:"

HUMAN = "[human-advisor]: "
"""How an answer in the history starts when a person on the team wrote it and not the agent.

the host puts it there since Sep 28, 2026: what the human advisor wrote
while the agent was off comes in on its first turn afterwards, as `answer`, with this
prefix. A turn may come with an empty `question` (the advisor wrote first) or an empty `answer`
(the customer's last message went unanswered), and the `question` may bring several messages on separate lines.
"""

SOLD = "[a sale closed here: everything above is already sold]"
"""The line that separates in the envelope a closed sale from what follows (`wrap(closed=)`).

The host puts it there when the host reports that the sale closed (the operator marked it or the payment was
confirmed): the order, the gates and the form read only what is below (`since_sale`), and the
writer all of it, to answer "when does what I paid for arrive?". Since Oct 8, 2026.
"""

History = tuple[tuple[str, str], ...]
"""What was spoken: pairs (customer's question, answer served), from oldest to newest."""


def wrap(question: str, history: History, text: str = "", closed: int | None = None) -> str:
    """The current question with what was spoken in front, and `text` behind, in the shape `customer_words()` takes apart.

    With no history it is the bare question plus `text`. With history, the
    `SPOKEN` block with one `Q:` line per previous question and its answer, and
    `NOW` with this turn's. It is the wrapping of `request`, pulled out into a
    function because the orchestrator seeds the same envelope with an empty `text`: the
    sale's gates read the customer's words from here, and have to
    find them where they always are. With `closed`, the index in `history` of the last turn of
    a closed sale, the `SOLD` line goes behind that turn.
    """
    if not history:
        return question + text
    turns = [f"Q: {p}\nA: {r}" for p, r in history]
    if closed is not None and 0 <= closed < len(history):
        turns.insert(closed + 1, SOLD)
    previous = "\n\n".join(turns)
    return f"{SPOKEN}\n{previous}\n\n{NOW}\n{question}{text}"


def customer_words(log: Log) -> str:
    """The customer's words in this session, taken from the request.

    `request` puts the history and the current question in `said[0]`, the only
    message `window` does not trim, and the CONTRACT behind. This takes it apart: the
    `Q:` lines of the spoken block and what follows `NOW`, up to `CUT`. The
    sale's gates look at this and not at all of `said`, because a model that
    asks "whitefly, worm, mites?" cannot close `pest` by itself.

    It is also the key with which `QuestionJudge` memoizes a turn's judgment:
    the host computes it on the envelope it is about to seed, and the gates
    recompute it from the Log, and since it is the same function it comes out the same.

    A question of several lines goes in whole (since Sep 28,
    2026: the host joins that way the messages the customer sent while a person
    was attending them); before, only the first one counted. Its leak,
    stated: a model answer with a line starting with `Q: ` would count
    as the customer's. It is a floor, like all the gates.
    """
    now, history = conversation(log)
    return "\n".join([*(p for p, _ in history if p), now])


def by_human(history: History) -> bool:
    """Whether any answer in the history was written by a person on the team (`HUMAN`)."""
    return any(r.startswith(HUMAN) for _, r in history)


def conversation(log: Log) -> tuple[str, History]:
    """The current question and the history, taken apart from the envelope. It is the way back from `wrap`.

    With the answers as they went in, summarized if they were long. It is the gates'
    emergency path: when nobody gave them the whole history up
    front (another host, a test), they take it from here and judge with what there is.
    It reads line by line, because an answer may bring empty lines
    inside and splitting by paragraph would break it.
    """
    if not log.said:
        return "", ()
    head = log.said[0].text.split(CUT, 1)[0]
    if not head.startswith(SPOKEN):
        return head, ()
    spoken_block, _, now = head.partition(f"\n{NOW}\n")
    pairs: list[list[str]] = []
    field = 0
    for line in spoken_block.splitlines()[1:]:
        if line == SOLD:
            field = -1
            continue
        if line.startswith("Q: "):
            pairs.append([line[3:], ""])
            field = 0
        elif line.startswith("A: ") and pairs:
            pairs[-1][1] = line[3:]
            field = 1
        elif pairs and field >= 0:
            pairs[-1][field] += "\n" + line
    return now, tuple((p.strip(), r.strip()) for p, r in pairs)


def sold_before(log: Log) -> int:
    """How many turns of the history belong to an already closed sale: those above `SOLD`, or zero."""
    if not log.said:
        return 0
    head = log.said[0].text.split(CUT, 1)[0]
    if not head.startswith(SPOKEN):
        return 0
    block = head.partition(f"\n{NOW}\n")[0]
    if f"\n{SOLD}\n" not in f"{block}\n":
        return 0
    return sum(1 for line in block.split(SOLD)[0].splitlines() if line.startswith("Q: "))


def since_sale(log: Log) -> tuple[str, History]:
    """`conversation` without the turns of an already closed sale: what the order, the gates and the form read."""
    now, history = conversation(log)
    return now, history[sold_before(log) :]
