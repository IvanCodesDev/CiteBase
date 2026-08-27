"""忠实度抽查（M3）：哈希通道机器判定、抽样可复算、红线出口、清单导出。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cardvault import cli, evalrun
from cardvault.vault import Vault
from helpers import EXAMPLE_ROOT, base_meta, make_claim, make_drift_vault, write_card


def _vault_with_claims(tmp_path: Path, n: int = 1) -> Path:
    root, _ = make_drift_vault(tmp_path)
    for i in range(1, n + 1):
        write_card(root, base_meta(f"card-concept-a{i}", name=f"A{i}", claims=[make_claim()]))
    return root


def test_clean_vault_is_fully_faithful(tmp_path: Path) -> None:
    root = _vault_with_claims(tmp_path)

    report = evalrun.run_faithfulness(Vault.load(root))

    assert (report.population, report.sampled) == (1, 1)
    assert report.unfaithful == []
    assert report.unfaithful_rate == 0.0
    entry = report.checklist[0]
    assert entry["ref"] == "card-concept-a1#c1"
    assert entry["spans"][0]["verified"] is True
    assert entry["spans"][0]["text"] == "第一行事实。"


def test_example_vault_passes_redline() -> None:
    report = evalrun.run_faithfulness(Vault.load(EXAMPLE_ROOT), sample=50, seed=1)
    assert report.sampled > 0
    assert report.unfaithful_rate == 0.0


def test_tampered_derivative_is_unfaithful(tmp_path: Path) -> None:
    root = _vault_with_claims(tmp_path)
    derived = root / "sources" / "src-notes" / "extracted" / "text.md"
    derived.write_text("被改写的第一行。\n", encoding="utf-8", newline="\n")

    report = evalrun.run_faithfulness(Vault.load(root))

    assert report.unfaithful_rate == 1.0
    assert report.unfaithful[0]["ref"] == "card-concept-a1#c1"
    assert "span 哈希失配" in report.unfaithful[0]["why"]


def test_sampling_is_seed_deterministic(tmp_path: Path) -> None:
    root = _vault_with_claims(tmp_path, n=6)
    vault = Vault.load(root)

    first = evalrun.run_faithfulness(vault, sample=3, seed=7)
    second = evalrun.run_faithfulness(vault, sample=3, seed=7)

    assert first.population == 6
    assert first.sampled == second.sampled == 3
    assert [c["ref"] for c in first.checklist] == [c["ref"] for c in second.checklist]


def test_cli_redline_and_export(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _vault_with_claims(tmp_path)
    export = tmp_path / "checklist.json"

    code = cli.main(
        ["eval", "--faithfulness", "--export", str(export), "--vault", str(root)]
    )
    assert code == 0
    assert "faithfulness" in capsys.readouterr().out
    payload = json.loads(export.read_text(encoding="utf-8"))
    assert payload["sampled"] == 1
    assert payload["checklist"][0]["claim"] == "第一行事实。"

    derived = root / "sources" / "src-notes" / "extracted" / "text.md"
    derived.write_text("被改写。\n", encoding="utf-8", newline="\n")
    code = cli.main(["eval", "--faithfulness", "--vault", str(root)])
    assert code == 1
    assert "超过不忠实率红线" in capsys.readouterr().out
