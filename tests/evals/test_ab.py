"""The A/B statistics against values computed separately: the Fisher p and the Wilson interval with a small n."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from evals.ab import CEILING, SPENT, Cut, allowed, better, fisher, group, plan, power, reach, spent, threshold, verdict, wilson, watch


@pytest.mark.parametrize(
    ("ka", "na", "kb", "nb", "p"),
    [(0, 3, 3, 3, 0.1), (1, 3, 3, 3, 0.4), (0, 6, 6, 6, 0.002), (1, 6, 6, 6, 0.015), (2, 6, 6, 6, 0.061), (3, 6, 3, 6, 1.0)],
)
def test_fisher(ka: int, na: int, kb: int, nb: int, p: float) -> None:
    assert fisher(ka, na, kb, nb) == pytest.approx(p, abs=5e-4)
    assert fisher(kb, nb, ka, na) == pytest.approx(p, abs=5e-4)


@pytest.mark.parametrize(("k", "n", "lo", "hi"), [(3, 3, 0.44, 1.0), (2, 3, 0.21, 0.94), (6, 6, 0.61, 1.0), (0, 6, 0.0, 0.39)])
def test_wilson(k: int, n: int, lo: float, hi: float) -> None:
    got = wilson(k, n)
    assert got[0] == pytest.approx(lo, abs=0.005)
    assert got[1] == pytest.approx(hi, abs=0.005)


def rows(k: int, n: int) -> list[dict[str, object]]:
    return [{"case": "x", "met": 1.0 if i < k else 0.0} for i in range(n)] + [{"case": "x", "lost": True, "met": 1.0}]


def test_verdict() -> None:
    assert verdict(rows(0, 3), rows(3, 3)).endswith("inconclusive")
    assert verdict(rows(0, 6), rows(6, 6)).endswith("B better")
    assert verdict(rows(6, 6), rows(0, 6)).endswith("B worse")
    assert verdict([], rows(3, 3)) == "·"


@pytest.mark.parametrize(("ka", "na", "kb", "nb", "p"), [(0, 3, 3, 3, 0.986), (2, 3, 3, 3, 0.786), (1, 6, 6, 6, 0.998), (3, 6, 3, 6, 0.5)])
def test_better(ka: int, na: int, kb: int, nb: int, p: float) -> None:
    assert better(ka, na, kb, nb) == pytest.approx(p, abs=0.002)


def test_group() -> None:
    assert [group(3, 3), group(0, 3), group(2, 3)] == ["always", "never", "sometimes"]


@pytest.mark.parametrize(("n", "low", "high"), [(3, 0.0, 0.0), (6, 0.44, 0.06), (10, 0.84, 0.30), (25, 1.0, 0.83)])
def test_power(n: int, low: float, high: float) -> None:
    assert power(0.2, 0.9, n) == pytest.approx(low, abs=0.01)
    assert power(0.5, 0.9, n) == pytest.approx(high, abs=0.01)


def test_reach() -> None:
    assert "no result" in reach(3)
    assert "84%" in reach(10)


def test_threshold() -> None:
    assert threshold(None) is None
    assert threshold("9/10") == (9, 10)
    with pytest.raises(SystemExit):
        threshold("11/10")
    assert verdict(rows(0, 10), rows(9, 10), (9, 10)).endswith("threshold 9/10: passes")
    assert verdict(rows(0, 10), rows(8, 10), (9, 10)).endswith("threshold 9/10: does not pass")


class TestAllowed:
    """3.6-04: the same ceiling as agro (3.6-01). No run goes over USD 1, with any flag."""

    def test_without_flags_the_cutoff_is_the_cap(self) -> None:
        assert allowed(0.05, []) == 0.10
        with pytest.raises(SystemExit, match="--yes"):
            allowed(0.60, [])

    def test_yes_raises_the_cutoff_to_1_and_no_further(self) -> None:
        assert allowed(0.60, ["--yes"]) == CEILING == 1.0
        with pytest.raises(SystemExit, match="ceiling"):
            allowed(1.20, ["--yes"])

    def test_nothing_goes_over_1(self) -> None:
        """Until 3.6-04 `--yes` in demo ran any estimate, with no ceiling."""
        for flags in (["--cap=2"], ["--cap=2", "--yes"]):
            with pytest.raises(SystemExit, match="ceiling"):
                allowed(0.10, flags)

    def test_lower_cap(self) -> None:
        assert allowed(0.10, ["--cap=0.2"]) == 0.2


class TestPlan:
    def test_n_comes_from_repeats(self) -> None:
        assert plan(["case"], []) == 1
        assert plan(["case", "--repeats=10"], ["--lever=x"]) == 10

    def test_lever_with_small_n_does_not_run(self) -> None:
        with pytest.raises(SystemExit, match="smoke"):
            plan(["case", "--repeats=3"], ["--lever=x"])


class TestWatch:
    """3.6-04: the run that passes the cutoff kills itself, without waiting for the sides to finish."""

    async def test_passing_the_cutoff_kills_both_sides(self, tmp_path: Path) -> None:
        logs = [tmp_path / "A.txt", tmp_path / "B.txt"]
        logs[0].write_text(f"{SPENT}0.40000\n{SPENT}0.70000\n")
        logs[1].write_text(f"{SPENT}0.35000\n")
        procs = [await asyncio.create_subprocess_exec(sys.executable, "-c", "import time; time.sleep(30)") for _ in logs]

        with pytest.raises(Cut) as e:
            await asyncio.wait_for(watch(procs, logs, CEILING, every=0.01), 5)
        assert e.value.spent == pytest.approx(1.05) and all(p.returncode is not None for p in procs)

    async def test_not_passing_returns_the_spend(self, tmp_path: Path) -> None:
        log = tmp_path / "A.txt"
        log.write_text(f"corpus: ...\n{SPENT}0.01000\n")
        proc = await asyncio.create_subprocess_exec(sys.executable, "-c", "pass")
        assert await watch([proc], [log], CEILING, every=0.01) == pytest.approx(0.01)
        assert spent(tmp_path / "missing.txt") == 0.0
