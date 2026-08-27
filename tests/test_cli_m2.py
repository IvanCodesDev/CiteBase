"""M2 CLI：init 脚手架、drift → audit → 平反的完整验收流、resolve 错误路径。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cardvault import cli
from helpers import base_meta, make_claim, make_drift_vault, write_card

CARD_ID = "card-concept-alpha"


def _write_alpha(root: Path) -> None:
    write_card(root, base_meta(aliases=["alpha"], claims=[make_claim()]))


def test_init_scaffolds_lintable_vault(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "kv"

    assert cli.main(["init", str(target), "--name", "demo"]) == 0
    assert "CI 模板已生成" in capsys.readouterr().out

    assert (target / "vault.yaml").is_file()
    assert (target / "packs" / "generic" / "pack.yaml").is_file()
    assert (target / "evals" / "golden.yaml").is_file()
    ci = (target / ".github" / "workflows" / "vault-ci.yml").read_text(encoding="utf-8")
    assert "vault drift --report" in ci
    for sub in ("cards", "sources", "refs", "evidence"):
        assert (target / sub).is_dir()

    # 脚手架出的空 vault 必须直接 lint 通过
    assert cli.main(["lint", "--vault", str(target)]) == 0


def test_init_refuses_existing_vault(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "kv"
    assert cli.main(["init", str(target)]) == 0
    capsys.readouterr()

    assert cli.main(["init", str(target)]) == 1
    assert "已是一个 vault" in capsys.readouterr().out


def _search_hit(vault_root: Path, capsys: pytest.CaptureFixture[str]) -> bool:
    assert cli.main(["search", "alpha", "--vault", str(vault_root), "--json"]) == 0
    return bool(json.loads(capsys.readouterr().out)["hit"])


def test_m2_acceptance_drift_to_recovery(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """M2 验收线全流程：源变更 → drift 置 suspect → 退出检索 → 人工平反 → 恢复。"""
    root, upstream = make_drift_vault(tmp_path)
    _write_alpha(root)
    vault_args = ["--vault", str(root)]

    assert _search_hit(root, capsys) is True

    upstream.write_text("上游改写。\n", encoding="utf-8", newline="\n")
    assert cli.main(["drift", *vault_args]) == 0
    assert "source_changed" in capsys.readouterr().out

    assert _search_hit(root, capsys) is False

    assert cli.main(["audit", "list", *vault_args]) == 0
    assert CARD_ID in capsys.readouterr().out

    assert (
        cli.main(
            ["audit", "review", CARD_ID, "--outcome", "pass", "--by", "tester", *vault_args]
        )
        == 0
    )
    capsys.readouterr()

    assert _search_hit(root, capsys) is True


def test_drift_report_mode_warns_without_applying(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, upstream = make_drift_vault(tmp_path)
    _write_alpha(root)
    upstream.write_text("上游改写。\n", encoding="utf-8", newline="\n")

    assert cli.main(
        ["drift", "--report", "--warn-threshold", "0.05", "--vault", str(root)]
    ) == 0
    out = capsys.readouterr().out
    assert "仅报告" in out
    assert "警告" in out

    assert cli.main(["audit", "list", "--vault", str(root)]) == 0
    assert "复核队列为空" in capsys.readouterr().out


def test_audit_review_error_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, _ = make_drift_vault(tmp_path)
    _write_alpha(root)

    code = cli.main(
        ["audit", "review", CARD_ID, "--outcome", "pass", "--vault", str(root)]
    )
    assert code == 1
    assert "不在 suspect 状态" in capsys.readouterr().out


def test_resolve_cli_rejects_non_contradiction(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, _ = make_drift_vault(tmp_path)
    _write_alpha(root)

    code = cli.main(["resolve", CARD_ID, "--winner", "c1", "--vault", str(root)])
    assert code == 1
    assert "不是矛盾卡" in capsys.readouterr().out
