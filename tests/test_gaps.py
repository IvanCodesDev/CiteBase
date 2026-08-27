"""检索日志与缺口清单（M3）：CLI/MCP 双入口记录，log 未命中 + golden 未命中合并。"""

from __future__ import annotations

from pathlib import Path

import pytest
from cardvault import cli
from cardvault.mcp.server import search_impl
from cardvault.retrievelog import gap_report, read_log
from helpers import base_meta, make_claim, make_drift_vault, write_card


def _setup(tmp_path: Path) -> Path:
    root, _ = make_drift_vault(tmp_path)
    write_card(root, base_meta(aliases=["alpha"], claims=[make_claim()]))
    return root


def test_cli_search_logs_hits_and_misses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _setup(tmp_path)
    assert cli.main(["search", "alpha", "--vault", str(root)]) == 0
    assert cli.main(["search", "量子引力波色谱", "--vault", str(root)]) == 0
    assert cli.main(["search", "量子引力波色谱", "--vault", str(root)]) == 0
    capsys.readouterr()

    records = read_log(root)
    assert [r["hit"] for r in records] == [True, False, False]
    assert records[0]["first"] == "card-concept-alpha"
    assert {r["surface"] for r in records} == {"cli"}


def test_mcp_search_logs_with_surface(tmp_path: Path) -> None:
    root = _setup(tmp_path)
    search_impl(root, "量子引力波色谱")

    records = read_log(root)
    assert len(records) == 1
    assert records[0]["surface"] == "mcp"
    assert records[0]["hit"] is False


def test_gap_report_merges_log_and_golden(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _setup(tmp_path)
    for _ in range(2):
        assert cli.main(["search", "量子引力波色谱", "--vault", str(root)]) == 0
    assert cli.main(["search", "  量子引力波色谱 ", "--vault", str(root)]) == 0  # 归一合并
    assert cli.main(["search", "alpha", "--vault", str(root)]) == 0  # 命中不进缺口
    capsys.readouterr()

    gaps = gap_report(root, golden_misses=[{"q": "量子引力波色谱"}, {"q": "另一个缺口"}])

    assert gaps[0]["query"] == "量子引力波色谱"
    assert gaps[0]["count"] == 4
    assert gaps[0]["origins"] == ["golden", "log:cli"]
    assert gaps[1] == {"query": "另一个缺口", "count": 1, "origins": ["golden"]}

    assert gap_report(root, golden_misses=None, min_count=4) == []


def test_gaps_cli_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _setup(tmp_path)
    assert cli.main(["gaps", "--vault", str(root)]) == 0
    assert "无缺口记录" in capsys.readouterr().out

    assert cli.main(["search", "量子引力波色谱", "--vault", str(root)]) == 0
    capsys.readouterr()
    assert cli.main(["gaps", "--vault", str(root)]) == 0
    out = capsys.readouterr().out
    assert "知识缺口" in out
    assert "量子引力波色谱" in out
