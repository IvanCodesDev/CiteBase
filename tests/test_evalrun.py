from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from citebase import evalrun
from citebase import index as index_mod
from citebase.vault import Vault
from helpers import EXAMPLE_ROOT


@pytest.fixture(scope="module")
def idx() -> dict[str, Any]:
    return index_mod.build(Vault.load(EXAMPLE_ROOT))


def test_load_golden(tmp_path: Path) -> None:
    golden = tmp_path / "golden.yaml"
    golden.write_text(
        "- q: 幂等性\n  expect: [card-concept-idempotency]\n  expect_rank: 1\n",
        encoding="utf-8",
    )
    cases = evalrun.load_golden(golden)
    assert cases[0].q == "幂等性"
    assert cases[0].expect == ["card-concept-idempotency"]
    assert cases[0].expect_rank == 1


def test_load_golden_rejects_mapping(tmp_path: Path) -> None:
    golden = tmp_path / "golden.yaml"
    golden.write_text("q: 幂等性\n", encoding="utf-8")
    with pytest.raises(ValueError, match="列表"):
        evalrun.load_golden(golden)


def test_run_counts_hits_and_misses(idx: dict[str, Any]) -> None:
    cases = [
        evalrun.GoldenCase(q="幂等性", expect=["card-concept-idempotency"], expect_rank=1),
        evalrun.GoldenCase(q="量子引力波色谱", expect=["card-concept-idempotency"]),
    ]
    report = evalrun.run(idx, cases)
    assert report.total == 2
    assert report.hits == 1
    assert report.first_hits == 1
    assert report.hit_rate == 0.5
    assert len(report.misses) == 1
    assert report.misses[0]["q"] == "量子引力波色谱"


def test_run_counts_rank_failures(idx: dict[str, Any]) -> None:
    """「重试」的最强命中是重试风暴/指数退避；幂等性卡进得了 top-10 但到不了第 1。"""
    cases = [
        evalrun.GoldenCase(q="重试", expect=["card-concept-idempotency"], expect_rank=1),
    ]
    report = evalrun.run(idx, cases)
    assert report.hits == 1
    assert report.rank_failures == 1
    assert any("超出" in m["why"] for m in report.misses)


def test_report_to_dict_shape() -> None:
    report = evalrun.EvalReport(total=0)
    payload = report.to_dict()
    assert payload["total"] == 0
    assert payload["hit_rate"] == 0.0
    assert payload["misses"] == []
