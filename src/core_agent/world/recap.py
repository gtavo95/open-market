"""The advisor's previous answers, summarized for the turn's envelope.

Until Sep 25, 2026 the envelope carried each previous answer
trimmed to 500 letters. What came after the cut did not exist for anyone:
the writer gave again the six accounts it had already given (prod capture
of Sep 25, todo 20), and the judge's compaction lost the question the
advisor closed with, which is what gives a "yes" its meaning. Now a long answer
goes in summarized and a short one goes in whole: nothing is trimmed.

One summary per answer, memoized by its text, so each answer is
paid once per process and not once per turn. If the model fails, the
answer goes in whole: longer, but losing nothing. One from a person on the
team is summarized the same and keeps its prefix (`HUMAN`), which is what says who wrote it.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict

from catalejo.core import Message, Role
from catalejo.llm import Provider

from ..prompts.recap import RECAP
from .dialogue import HUMAN, History

LONG = 500
"""From how many letters an answer goes in summarized. It is the old cut: what fit, goes in the same."""

SUMMARY = "(summary) "
"""How a summarized answer starts in the envelope, so whoever reads it knows it is not verbatim."""


class Recaps:
    """Summarizes the long answers of a history, with memory by text."""

    def __init__(self, model: Provider, keep: int = 512) -> None:
        self._model = model
        self._keep = keep
        self._memo: OrderedDict[str, str] = OrderedDict()
        self.spent = 0
        self.errors = 0

    async def __call__(self, history: History) -> History:
        """The same history, with each answer of `LONG` letters or more swapped for its summary."""
        replies = await asyncio.gather(*(self._one(r) for _, r in history))
        return tuple((q, r) for (q, _), r in zip(history, replies))

    async def _one(self, reply: str) -> str:
        if reply.startswith(HUMAN):
            return HUMAN + await self._one(reply[len(HUMAN):])
        if len(reply) < LONG:
            return reply
        if (done := self._memo.get(reply)) is not None:
            self._memo.move_to_end(reply)
            return done
        try:
            out = await self._model.complete((Message(Role.USER, RECAP + reply),))
        except Exception:
            self.errors += 1
            return reply
        self.spent += out.spent
        text = out.message.text.strip()
        if not text:
            self.errors += 1
            return reply
        summary = SUMMARY + text
        self._memo[reply] = summary
        while len(self._memo) > self._keep:
            self._memo.popitem(last=False)
        return summary
