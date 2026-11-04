"""The earlier answers in the envelope: the long one summarized, the short one whole, none cut."""

from __future__ import annotations

from catalejo.core import Conversation, Message, Role
from catalejo.llm import Reply

from core_agent.world.dialogue import HUMAN, conversation, customer_words, wrap
from core_agent.world.recap import LONG, SUMMARY, Recaps
from catalejo.core import Log

ACCOUNTS = "You can transfer to Agroinsumos Ceiba. " + "Banco Demo 000-000001-1. " * 20 + "Do you prefer a link or a transfer?"


class Summarizer:
    """The model that summarizes in the tests: it counts how many times it was called."""

    model = "summary"

    def __init__(self, *, down: bool = False) -> None:
        self.calls: list[Conversation] = []
        self._down = down

    async def complete(self, conv: Conversation) -> Reply:
        self.calls.append(conv)
        if self._down:
            raise RuntimeError("the model did not answer")
        return Reply(Message(Role.ASSISTANT, "Gave the Ceiba accounts.\nAsked: Do you prefer a link or a transfer?"), spent=5)


def test_the_envelope_does_not_cut_the_answer() -> None:
    """Until Sep 25, 2026 it was `r[:500]`: the accounts and the closing question were left out."""
    _, history = conversation(Log(said=(Message(Role.USER, wrap("it would be a transfer", (("how do I pay?", ACCOUNTS),))),)))

    assert history == (("how do I pay?", ACCOUNTS),)


async def test_the_long_one_goes_in_summarized_and_the_short_one_whole() -> None:
    model = Summarizer()
    recaps = Recaps(model)
    short = "Reapvane comes in a 1 L container at Q275. How many liters would you like?"
    assert len(ACCOUNTS) >= LONG > len(short)

    out = await recaps((("how much is the Reapvane?", short), ("how do I pay?", ACCOUNTS)))

    assert out[0] == ("how much is the Reapvane?", short)
    assert out[1][0] == "how do I pay?"
    assert out[1][1].startswith(SUMMARY) and "Asked: Do you prefer a link or a transfer?" in out[1][1]
    assert len(model.calls) == 1 and recaps.spent == 5


async def test_each_answer_is_summarized_once() -> None:
    model = Summarizer()
    recaps = Recaps(model)
    history = (("how do I pay?", ACCOUNTS),)

    await recaps(history)
    await recaps((*history, ("it would be a transfer", "Noted.")))

    assert len(model.calls) == 1


async def test_if_the_model_fails_it_goes_in_whole() -> None:
    recaps = Recaps(Summarizer(down=True))

    out = await recaps((("how do I pay?", ACCOUNTS),))

    assert out == (("how do I pay?", ACCOUNTS),) and recaps.errors == 1


async def test_a_person_s_answer_is_summarized_and_keeps_who_wrote_it() -> None:
    out = await Recaps(Summarizer())((("how do I pay?", HUMAN + ACCOUNTS),))

    assert out[0][1].startswith(HUMAN + SUMMARY)


def test_the_customer_s_joined_messages_count_whole_and_the_empty_turn_does_not_break() -> None:
    """The host, Sep 28, 2026: what the customer sent while a person attended them comes in lines, and a turn can come with one side empty."""
    history = (("", HUMAN + "Hello, can I help you?"), ("hello\nI want 2 liters of Reapvane", HUMAN + "Done."), ("and the shipping?", ""))
    seen = Log(said=(Message(Role.USER, wrap("thanks", history)),))

    assert conversation(seen) == ("thanks", history)
    assert customer_words(seen) == "hello\nI want 2 liters of Reapvane\nand the shipping?\nthanks"
