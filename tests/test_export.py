"""导出器（M4）：JSON 快照确定性、站点产物、可见性过滤与许可证警示。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cardvault import cli
from cardvault.exporters import build_snapshot, export_json, export_site
from cardvault.vault import Vault
from helpers import base_meta, make_claim, make_drift_vault, write_card


def _setup(tmp_path: Path) -> Path:
    """两张卡：alpha（active，引 unknown 许可证源）+ beta（suspect，默认导出应排除）。"""
    root, _ = make_drift_vault(tmp_path)
    meta = root / "sources" / "src-notes" / "meta.yaml"
    meta.write_text(
        meta.read_text(encoding="utf-8") + "license: unknown\n", encoding="utf-8"
    )
    write_card(
        root,
        base_meta(
            aliases=["alpha"],
            claims=[make_claim()],
            links=[{"predicate": "related_to", "to": "card-concept-beta"}],
        ),
        body="## 是什么\n\n**加粗**与 `代码`。\n\n- 列表项\n\n```text\n代码块\n```\n",
    )
    write_card(root, base_meta("card-concept-beta", name="Beta", status="suspect"))
    return root


def test_snapshot_visibility_and_license_warnings(tmp_path: Path) -> None:
    root = _setup(tmp_path)
    vault = Vault.load(root)

    snapshot = build_snapshot(vault)
    assert [c["id"] for c in snapshot["cards"]] == ["card-concept-alpha"]
    assert snapshot["stats"]["cards"] == 1
    assert snapshot["license_warnings"] == [
        {"source": "src-notes", "license": "unknown", "cited_spans": 1}
    ]

    full = build_snapshot(vault, include_hidden=True)
    assert [c["id"] for c in full["cards"]] == ["card-concept-alpha", "card-concept-beta"]


def test_export_json_is_deterministic(tmp_path: Path) -> None:
    root = _setup(tmp_path)
    vault = Vault.load(root)
    a, b = tmp_path / "a.json", tmp_path / "b.json"

    export_json(vault, a)
    export_json(vault, b)

    assert a.read_bytes() == b.read_bytes()
    payload = json.loads(a.read_text(encoding="utf-8"))
    assert payload["schema"] == "cardvault-snapshot/0.1"


def test_export_site_writes_pages(tmp_path: Path) -> None:
    root = _setup(tmp_path)
    out = tmp_path / "site"

    report = export_site(Vault.load(root), out)

    assert report.cards == 1
    assert set(report.files) == {
        "style.css",
        "index.html",
        "cards/card-concept-alpha.html",
    }
    index_html = (out / "index.html").read_text(encoding="utf-8")
    assert "Alpha" in index_html
    assert "license=unknown" in index_html or "许可证警示" in index_html
    card_html = (out / "cards" / "card-concept-alpha.html").read_text(encoding="utf-8")
    assert "<strong>加粗</strong>" in card_html
    assert "<code>代码</code>" in card_html
    assert "<li>列表项</li>" in card_html
    assert "<pre>代码块</pre>" in card_html
    assert "src-notes" in card_html  # 出处是一等内容
    assert "Beta" in card_html  # 关联仍列出
    assert "未随站点导出" in card_html  # 隐藏卡不出死链接
    assert 'href="card-concept-beta.html"' not in card_html


def test_export_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _setup(tmp_path)

    out_json = tmp_path / "snapshot.json"
    assert cli.main(["export", "json", "--out", str(out_json), "--vault", str(root)]) == 0
    out = capsys.readouterr().out
    assert "export json" in out
    assert "许可证警示" in out
    assert out_json.is_file()

    out_site = tmp_path / "site"
    assert cli.main(["export", "site", "--out", str(out_site), "--vault", str(root)]) == 0
    assert "export site" in capsys.readouterr().out
    assert (out_site / "index.html").is_file()
