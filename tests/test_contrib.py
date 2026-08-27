"""贡献度度量（M3）：口径精确、榜单可复算、负贡献只在显式指令下置 suspect。"""

from __future__ import annotations

from pathlib import Path

import pytest
from cardvault.audit import read_audit
from cardvault.contrib import run_contrib
from cardvault.vault import Vault
from helpers import base_meta, make_claim, make_drift_vault, make_event, write_card, write_events

ALPHA = "card-concept-alpha"


def _setup(tmp_path: Path) -> Path:
    """10 条事件：引用 alpha 的 6 条中 2 成功；未引用的 4 条中 3 成功。"""
    root, _ = make_drift_vault(tmp_path)
    write_card(root, base_meta(claims=[make_claim()]))
    events = [
        make_event(1, status="success", cards=[ALPHA]),
        make_event(2, status="success", cards=[ALPHA]),
        make_event(3, status="failure", cards=[ALPHA]),
        make_event(4, status="failure", cards=[ALPHA]),
        make_event(5, status="failure", cards=[ALPHA]),
        make_event(6, status="partial", cards=[ALPHA]),
        make_event(7, status="success"),
        make_event(8, status="success"),
        make_event(9, status="success"),
        make_event(10, status="failure"),
    ]
    write_events(root, events)
    return root


def test_contribution_rates_are_exact(tmp_path: Path) -> None:
    root = _setup(tmp_path)

    report = run_contrib(root, min_events=5)

    assert report.events_total == 10
    assert report.overall_success_rate == pytest.approx(5 / 10)
    entry = next(c for c in report.cards if c.card_id == ALPHA)
    assert (entry.consulted, entry.success, entry.failure, entry.partial) == (6, 2, 3, 1)
    assert entry.success_rate == pytest.approx(2 / 6)
    assert entry.baseline_rate == pytest.approx(3 / 4)
    assert entry.lift == pytest.approx(2 / 6 - 3 / 4)
    assert report.negative == [ALPHA]
    assert report.applied_suspect == []  # 默认只报告


def test_ranking_is_recomputable(tmp_path: Path) -> None:
    root = _setup(tmp_path)
    first = run_contrib(root, min_events=5).to_dict()
    second = run_contrib(root, min_events=5).to_dict()
    assert first == second


def test_min_events_guards_negative_list(tmp_path: Path) -> None:
    root = _setup(tmp_path)
    report = run_contrib(root, min_events=7)
    assert report.negative == []  # 样本量不足不进候选


def test_apply_negative_marks_suspect_with_audit(tmp_path: Path) -> None:
    root = _setup(tmp_path)

    report = run_contrib(root, min_events=5, apply_negative=True, actor="tester")

    assert report.applied_suspect == [ALPHA]
    assert Vault.load(root).cards[ALPHA].meta.status == "suspect"
    last = read_audit(root)[-1]
    assert (last["action"], last["actor"], last["card_id"]) == (
        "contrib_signal",
        "tester",
        ALPHA,
    )


def test_events_citing_unknown_cards_are_counted_but_flagged(tmp_path: Path) -> None:
    root, _ = make_drift_vault(tmp_path)
    write_events(root, [make_event(1, status="failure", cards=["card-method-ghost"])])

    report = run_contrib(root)

    entry = report.cards[0]
    assert entry.card_id == "card-method-ghost"
    assert entry.exists is False
    assert report.negative == []  # 不在库内的卡不进 suspect 候选
