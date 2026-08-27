"""回流编译器（M3）：聚类阈值、两道闸、审核入库、幂等与验收线。"""

from __future__ import annotations

from pathlib import Path

import pytest
from cardvault import lint as lint_mod
from cardvault.audit import read_audit
from cardvault.compiler.backflow import run_backflow
from cardvault.compiler.review import approve, load_queue
from cardvault.drift import run_drift
from cardvault.vault import Vault
from helpers import base_meta, make_claim, make_drift_vault, make_event, write_card, write_events

ALPHA = "card-concept-alpha"


def _vault_with_alpha(tmp_path: Path) -> Path:
    root, _ = make_drift_vault(tmp_path)
    write_card(root, base_meta(claims=[make_claim()]))
    return root


def _lint_errors(root: Path) -> list[str]:
    return [
        f"{f.rule} {f.message}"
        for f in lint_mod.lint_vault(Vault.load(root))
        if f.level == lint_mod.LEVEL_ERROR
    ]


def test_single_failure_stays_below_threshold(tmp_path: Path) -> None:
    root = _vault_with_alpha(tmp_path)
    write_events(root, [make_event(1, category="extrapolation", summary="外推背离")])

    report = run_backflow(root)

    assert report.events_total == 1
    assert report.new_sources == 1
    assert report.below_threshold == {"extrapolation": 1}
    assert report.pending == []


def test_cluster_reaches_threshold_and_survives_review(tmp_path: Path) -> None:
    root = _vault_with_alpha(tmp_path)
    write_events(
        root,
        [
            make_event(
                1,
                category="extrapolation",
                summary="含拐点 6 点序列外推方向性背离",
                root_cause="趋势假设不满足",
                cards=[ALPHA],
            ),
            make_event(
                2,
                category="Extrapolation",  # 大小写归一到同一聚类
                summary="外推区间超出样本支撑范围",
                cards=[ALPHA],
            ),
        ],
    )

    report = run_backflow(root)

    assert report.clusters == {"extrapolation": 2}
    assert len(report.pending) == 1
    assert report.machine_rejected == {}
    draft_id = report.pending[0]

    queue = load_queue(root)
    entry = next(e for e in queue if e.draft_id == draft_id)
    assert entry.status == "pending"  # 回流一律送审，绝不自动入库
    assert (root / "_review" / "drafts" / f"{draft_id}.md").is_file()
    assert read_audit(root)[-1]["action"] == "backflow_run"

    dest = approve(root, draft_id, actor="tester")
    assert dest.startswith("cards/pitfall/")

    vault = Vault.load(root)
    card = vault.cards[draft_id]
    assert card.meta.kind == "pitfall"
    assert len(card.meta.claims) == 2
    assert all(len(c.sources) == 1 for c in card.meta.claims)
    assert {ln.to for ln in card.meta.links} == {ALPHA}
    assert _lint_errors(root) == []  # 出处链绑定事件源，哈希全部可核

    # 入库后的库再跑 drift：事件源不可变，不得误报
    assert run_drift(root, apply=True).signals == []


def test_second_run_is_idempotent(tmp_path: Path) -> None:
    root = _vault_with_alpha(tmp_path)
    write_events(
        root,
        [
            make_event(1, category="extrapolation", summary="现象一"),
            make_event(2, category="extrapolation", summary="现象二"),
        ],
    )
    first = run_backflow(root)
    assert len(first.pending) == 1

    second = run_backflow(root)
    assert second.pending == []
    assert second.already_covered == {"extrapolation": first.pending[0]}
    assert second.new_sources == 0


def test_backflow_rejects_unknown_kind(tmp_path: Path) -> None:
    root = _vault_with_alpha(tmp_path)
    with pytest.raises(ValueError, match="不在启用 Pack"):
        run_backflow(root, kind="incident")


def test_m3_acceptance_50_events_yield_3_reviewed_cards(tmp_path: Path) -> None:
    """M3 验收线：50 条模拟事件 → ≥3 张陷阱卡草案 → 全部人工过审入库，lint 0 error。"""
    root = _vault_with_alpha(tmp_path)
    events = []
    n = 1
    for category in ("extrapolation", "data-leakage", "overfitting"):
        for _ in range(4):
            events.append(
                make_event(n, category=category, summary=f"{category} 失败现象 {n}", cards=[ALPHA])
            )
            n += 1
    while n <= 50:
        events.append(make_event(n, status="success", cards=[ALPHA]))
        n += 1
    write_events(root, events)

    report = run_backflow(root)

    assert report.events_total == 50
    assert report.new_sources == 50
    assert len(report.pending) >= 3

    for draft_id in report.pending:
        approve(root, draft_id, actor="tester")

    vault = Vault.load(root)
    pitfalls = [c for c in vault.cards.values() if c.meta.kind == "pitfall"]
    assert len(pitfalls) >= 3
    assert _lint_errors(root) == []
