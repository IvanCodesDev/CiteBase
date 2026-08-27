"""性能基线（M4）：小规模冒烟——合成、双后端计时、红线出口（10k 全量走 CLI/nightly）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from cardvault import cli
from cardvault.bench import build_queries, run_bench, synth_vault


def test_synth_vault_is_deterministic() -> None:
    a = synth_vault(20, seed=3)
    b = synth_vault(20, seed=3)
    assert sorted(a.cards) == sorted(b.cards)
    first = next(iter(sorted(a.cards)))
    assert a.cards[first].meta.name == b.cards[first].meta.name
    assert build_queries(20, 10, seed=3) == build_queries(20, 10, seed=3)


def test_run_bench_smoke(tmp_path: Path) -> None:
    report = run_bench(cards=60, queries=15, seed=1, workdir=tmp_path)

    assert report.cards == 60
    assert {r.backend for r in report.results} == {"memory", "sqlite"}
    for result in report.results:
        assert result.queries == 15
        assert 0 <= result.p50_ms <= result.p95_ms <= result.max_ms


def test_bench_cli_redline(capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        cli.main(["bench", "--cards", "40", "--queries", "10", "--max-p95", "5000"]) == 0
    )
    out = capsys.readouterr().out
    assert "memory" in out and "sqlite" in out

    assert (
        cli.main(["bench", "--cards", "40", "--queries", "10", "--max-p95", "0.0001"])
        == 1
    )
    assert "超过红线" in capsys.readouterr().out
