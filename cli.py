"""The advisor, wrapped: conversation over stdin, with history.

    uv run cli.py              # conversation over stdin, with history
    uv run cli.py --verbose    # also, what each role said
    uv run cli.py --one        # a single question, with the searcher's transcript

The `core_agent/` package is the core and knows nothing of `argv` or `input()`; this
file is the only command line entry on top of it. It acts as host for the
effects: what the turn proposes is "executed" by `host_sim` (it prints
`[effect] ...` and seeds the `done` or the `reject`), and the next turn starts
with those moves, as it starts with the sale's. It is the end-to-end
path without the server.

`--one` is the way to try the package without conversing: one turn, the
searcher's whole transcript and the state of the sale and the effects.
Until Sep 22, 2026 it was the `main()` of `agro_v2.py`.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from core_agent import QuestionJudge, build, effects_state, host_sim, provider, answer, sale_state, turn
from core_agent.world.dialogue import History
from catalejo.core import EffectOp, PlanOp, effects_of, project
from catalejo.rlm import Dossier


async def converse(*, verbose: bool = False) -> None:
    model = provider()
    question_judge = QuestionJudge.from_env(model)
    dossier = Dossier()
    agent = build(model, question_judge=question_judge, dossier=dossier)
    history: History = ()
    course: tuple[PlanOp, ...] = ()
    effects: tuple[EffectOp, ...] = ()
    try:
        questions = iter(lambda: input("> ").strip(), "")
        for question in questions:
            if not question:
                continue
            t0 = time.monotonic()
            out = await turn(agent, question, history, course, effects)
            if verbose:
                for t in dossier.drain():
                    for m in t.said:
                        print(
                            f"\n\033[1m[{t.who}/{m.role.value}]\033[0m {m.text.strip()[:2000]}"
                        )
                for m in out.said:
                    print(
                        f"\n\033[1m[writer/{m.role.value}]\033[0m {m.text.strip()[:2000]}"
                    )
            text = answer(out)
            print(f"\n{text}\n")
            by_role = "".join(f", {r.who} {r.spent:,}" for r in out.reports)
            fails = f", fails: {[f.reason for f in out.fails]}" if out.fails else ""
            print(
                f"\033[2m[{out.spent:,} tokens{by_role}, {time.monotonic() - t0:.1f} s{fails}]\033[0m"
            )
            history = (*history, (question, text))
            course = (*course, *out.course)
            done = host_sim(effects_of((*effects, *out.effects)))
            for op in done:
                print(f"\033[2m[effect] {op.id} {op.verb}: {op.note}\033[0m")
            effects = (*effects, *out.effects, *done)
            judge = f", judge {question_judge.calls} calls, USD {question_judge.cost:.4f}" if question_judge is not None else ", no judge"
            print(f"\033[2m[{sale_state(project(course))}; {effects_state(effects_of(effects))}{judge}]\033[0m")
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        if question_judge is not None:
            await question_judge.aclose()
        await model.aclose()


async def one() -> None:
    """A single question with the searcher's transcript, to try the package without conversing."""
    model = provider()
    question_judge = QuestionJudge.from_env(model)
    dossier = Dossier()
    agent = build(model, question_judge=question_judge, dossier=dossier)
    try:
        out = await turn(agent, input("> ").strip(), ())
        for t in dossier.drain():
            for m in t.said:
                print(f"\n[{t.who}/{m.role.value}] {m.text.strip()}")
        print(f"\n{answer(out)}\n")
        fails = f", fails: {[f.reason for f in out.fails]}" if out.fails else ""
        print(f"[{sale_state(project(out.course))}; {effects_state(effects_of(out.effects))}{fails}]")
    finally:
        if question_judge is not None:
            await question_judge.aclose()
        await model.aclose()


if __name__ == "__main__":
    argv = sys.argv[1:]
    asyncio.run(one() if "--one" in argv else converse(verbose="--verbose" in argv))
