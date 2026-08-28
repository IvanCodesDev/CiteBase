from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from citebase import cli
from citebase.vault import Vault


def _scenario(source_id: str) -> dict[str, object]:
    return {
        "proposals": {
            source_id: [
                {
                    "kind": "concept",
                    "name": "CLI Demo Card",
                    "summary": "一句话摘要。",
                    "body": "## 是什么\n\n正文。\n",
                    "claims": [
                        {
                            "text": "CLI 第一行。",
                            "spans": [
                                {"source": source_id, "loc": "extracted/text.md#L1-L1"}
                            ],
                        }
                    ],
                }
            ]
        }
    }


def test_cli_ingest_compile_review_roundtrip(
    mini_vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raw = tmp_path / "cli-notes.md"
    raw.write_text("CLI 第一行。\n", encoding="utf-8")
    vault_args = ["--vault", str(mini_vault)]

    assert cli.main(["ingest", str(raw), *vault_args]) == 0
    out = capsys.readouterr().out
    assert "ingest: src-cli-notes" in out

    scenario = tmp_path / "scenario.yaml"
    scenario.write_text(
        yaml.safe_dump(_scenario("src-cli-notes"), allow_unicode=True), encoding="utf-8"
    )
    assert (
        cli.main(
            ["compile", *vault_args, "--scripted", str(scenario), "--source", "src-cli-notes"]
        )
        == 0
    )
    out = capsys.readouterr().out
    match = re.search(r"待审 (card-[a-z0-9-]+)", out)
    assert match, out
    draft_id = match.group(1)

    assert cli.main(["review", "list", *vault_args]) == 0
    assert "pending" in capsys.readouterr().out

    assert cli.main(["review", "show", draft_id, *vault_args]) == 0
    assert "CLI Demo Card" in capsys.readouterr().out

    assert cli.main(["review", "approve", draft_id, "--by", "tester", *vault_args]) == 0
    capsys.readouterr()
    assert draft_id in Vault.load(mini_vault).cards

    # lint 全绿：编译入库的卡与手工卡遵守同一套治理
    assert cli.main(["lint", *vault_args]) == 0


def test_cli_review_reject_and_errors(
    mini_vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raw = tmp_path / "cli-notes.md"
    raw.write_text("CLI 第一行。\n", encoding="utf-8")
    vault_args = ["--vault", str(mini_vault)]
    assert cli.main(["ingest", str(raw), *vault_args]) == 0
    scenario = tmp_path / "scenario.yaml"
    scenario.write_text(
        yaml.safe_dump(_scenario("src-cli-notes"), allow_unicode=True), encoding="utf-8"
    )
    assert cli.main(["compile", *vault_args, "--scripted", str(scenario)]) == 0
    out = capsys.readouterr().out
    draft_id_match = re.search(r"待审 (card-[a-z0-9-]+)", out)
    assert draft_id_match
    draft_id = draft_id_match.group(1)

    assert (
        cli.main(["review", "reject", draft_id, "--reason", "测试驳回", *vault_args]) == 0
    )
    capsys.readouterr()
    assert cli.main(["review", "approve", draft_id, *vault_args]) == 1  # 已终态
    assert cli.main(["review", "show", "card-ghost", *vault_args]) == 1


def test_cli_compile_without_llm_config(
    mini_vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["compile", "--vault", str(mini_vault)]) == 1
    assert "跳过编译" in capsys.readouterr().out


def test_cli_ingest_outside_vault(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    raw = tmp_path / "notes.md"
    raw.write_text("x\n", encoding="utf-8")
    assert cli.main(["ingest", str(raw), "--vault", str(tmp_path)]) == 2
    assert "不是一个 vault" in capsys.readouterr().out
