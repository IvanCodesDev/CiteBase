"""失效信号总线（M2）：双通道漂移 + 时效过期 → suspect → 退出检索。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from cardvault import index as index_mod
from cardvault import retrieve
from cardvault.audit import read_audit
from cardvault.drift import run_drift, scan
from cardvault.vault import Vault
from helpers import base_meta, make_claim, make_drift_vault, write_card

CARD_ID = "card-concept-alpha"


def _write_alpha(root: Path, **overrides: object) -> None:
    meta = base_meta(aliases=["alpha"], claims=[make_claim()])
    meta.update(overrides)
    write_card(root, meta)


def _status(root: Path) -> str:
    return Vault.load(root).cards[CARD_ID].meta.status


def test_clean_vault_produces_no_signals(tmp_path: Path) -> None:
    root, _ = make_drift_vault(tmp_path)
    _write_alpha(root)

    report = run_drift(root, apply=True)

    assert report.signals == []
    assert report.marked_suspect == []
    assert report.applied is False
    assert _status(root) == "active"


def test_source_change_marks_citing_card_suspect(tmp_path: Path) -> None:
    root, upstream = make_drift_vault(tmp_path)
    _write_alpha(root)
    upstream.write_text("上游内容已经变了。\n", encoding="utf-8", newline="\n")

    report = run_drift(root, apply=True)

    assert {s.kind for s in report.signals} == {"source_changed"}
    assert report.marked_suspect == [CARD_ID]
    assert report.applied is True
    assert _status(root) == "suspect"
    last = read_audit(root)[-1]
    assert last["action"] == "drift_signal"
    assert last["card_id"] == CARD_ID


def test_suspect_card_exits_retrieval_until_included(tmp_path: Path) -> None:
    """M2 验收线：修改源后 suspect 正确标记并退出检索（include_suspect 才可见）。"""
    root, upstream = make_drift_vault(tmp_path)
    _write_alpha(root)
    idx = index_mod.build(Vault.load(root))
    assert retrieve.search(idx, "alpha").hit is True

    upstream.write_text("上游改写。\n", encoding="utf-8", newline="\n")
    run_drift(root, apply=True)

    idx = index_mod.build(Vault.load(root))
    assert retrieve.search(idx, "alpha").hit is False
    included = retrieve.search(idx, "alpha", include_suspect=True)
    assert included.hit is True
    assert included.hits[0].status == "suspect"


def test_report_mode_leaves_vault_untouched(tmp_path: Path) -> None:
    root, upstream = make_drift_vault(tmp_path)
    _write_alpha(root)
    upstream.write_text("上游改写。\n", encoding="utf-8", newline="\n")

    report = run_drift(root, apply=False)

    assert report.marked_suspect == [CARD_ID]
    assert report.applied is False
    assert _status(root) == "active"
    assert read_audit(root) == []


def test_span_mismatch_marks_suspect(tmp_path: Path) -> None:
    root, _ = make_drift_vault(tmp_path)
    _write_alpha(root)
    derived = root / "sources" / "src-notes" / "extracted" / "text.md"
    derived.write_text("派生物被篡改。\n", encoding="utf-8", newline="\n")

    report = run_drift(root, apply=True)

    assert {s.kind for s in report.signals} == {"span_mismatch"}
    assert _status(root) == "suspect"


def test_unreachable_source_treated_as_changed(tmp_path: Path) -> None:
    root, upstream = make_drift_vault(tmp_path)
    _write_alpha(root)
    upstream.unlink()

    report = run_drift(root, apply=True)

    assert {s.kind for s in report.signals} == {"source_unreachable"}
    assert _status(root) == "suspect"


def test_expired_claim_reported_not_suspected(tmp_path: Path) -> None:
    """通道 C 只产报告信号：检索侧已按 claim 过滤，续期/退役交给复核。"""
    root, _ = make_drift_vault(tmp_path)
    _write_alpha(root, claims=[make_claim(valid_until="2020-01-01T00:00:00+00:00")])

    report = scan(Vault.load(root), now=datetime(2026, 1, 1, tzinfo=UTC))

    assert report.expired_claims == [f"{CARD_ID}#c1"]
    assert {s.kind for s in report.signals} == {"claim_expired"}
    assert report.marked_suspect == []


def test_expired_claim_via_run_drift_keeps_card_active(tmp_path: Path) -> None:
    """run_drift 走默认 now=datetime.now(UTC)：带时区时点不得让通道 C 崩溃。"""
    root, _ = make_drift_vault(tmp_path)
    _write_alpha(root, claims=[make_claim(valid_until="2020-01-01T00:00:00+00:00")])

    report = run_drift(root, apply=True)

    assert report.expired_claims == [f"{CARD_ID}#c1"]
    assert _status(root) == "active"
