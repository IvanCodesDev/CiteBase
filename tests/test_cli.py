from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from cardvault import cli
from helpers import EXAMPLE_ROOT

VAULT = ["--vault", str(EXAMPLE_ROOT)]


def test_lint_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["lint", *VAULT]) == 0
    out = capsys.readouterr().out
    assert "0 error" in out


def test_index_write_then_check(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["index", *VAULT]) == 0
    assert cli.main(["index", *VAULT, "--check"]) == 0
    assert "一致" in capsys.readouterr().out


def test_search_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["search", "幂等性", *VAULT, "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["hit"] is True
    assert data["hits"][0]["id"] == "card-concept-idempotency"


def test_search_no_hit_prints_contract(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["search", "量子引力波色谱", *VAULT]) == 0
    out = capsys.readouterr().out
    assert "未命中" in out
    assert "建议" in out


def test_read_card(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["read", "card-method-bootstrap", *VAULT]) == 0
    out = capsys.readouterr().out
    assert "自助法" in out
    assert cli.main(["read", "card-ghost", *VAULT]) == 1


def test_follow(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["follow", "card-method-exponential-backoff", *VAULT]) == 0
    out = capsys.readouterr().out
    assert "card-pitfall-retry-storm" in out


def test_quote_verified(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["quote", "card-concept-idempotency#c1", *VAULT]) == 0
    out = capsys.readouterr().out
    assert "已验证" in out
    assert cli.main(["quote", "card-ghost#c1", *VAULT]) == 1


def test_stats_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["stats", *VAULT, "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["cards"] == 24
    assert data["sources"] == 3
    assert data["claims"] == 32
    assert data["load_errors"] == 0


def test_eval_meets_m0_redline(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["eval", *VAULT, "--min-hit", "0.8", "--min-first", "0.8"]) == 0
    assert "命中率" in capsys.readouterr().out


def test_hash_outputs_hex(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["hash", "src-eng-notes", "extracted/text.md#L4-L4", *VAULT]) == 0
    out = capsys.readouterr().out.strip()
    assert re.fullmatch(r"[a-f0-9]{64}", out)


def test_fix_hashes_reports_consistent(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["fix-hashes", *VAULT]) == 0
    out = capsys.readouterr().out
    assert "0 个不一致" in out


def test_missing_vault_exits_2(tmp_path: Path) -> None:
    assert cli.main(["lint", "--vault", str(tmp_path)]) == 2
