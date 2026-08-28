"""知识贡献度度量（M3，provenance-and-drift §4）。

榜单可复算：同一份 ``evidence/*.jsonl`` 输入必然产出同一份榜单——这是「知识库
到底有没有用」的可测量回答。度量口径：

- 每张卡的成功率 = 引用该卡的事件中 outcome=success 的占比（partial 不计成功）；
- 基线 = 未引用该卡的事件成功率；lift = 成功率 − 基线；
- 贡献度持续为负（样本量达标且 lift < 0）的卡是复核候选：``--apply-negative``
  才落盘置 suspect（信号只置 suspect 并进复核队列，从不直接删除）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from citebase.audit import append_audit
from citebase.drift import refresh_index_if_present, set_card_status
from citebase.evidence import LoadedEvent, load_events
from citebase.vault import Vault

DEFAULT_MIN_EVENTS = 5


@dataclass
class CardContribution:
    card_id: str
    exists: bool  # 卡是否仍在库内（事件可能引用已退役或外部卡）
    consulted: int = 0
    success: int = 0
    failure: int = 0
    partial: int = 0

    success_rate: float = 0.0
    baseline_rate: float = 0.0
    lift: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "card_id": self.card_id,
            "exists": self.exists,
            "consulted": self.consulted,
            "success": self.success,
            "failure": self.failure,
            "partial": self.partial,
            "success_rate": round(self.success_rate, 4),
            "baseline_rate": round(self.baseline_rate, 4),
            "lift": round(self.lift, 4),
        }


@dataclass
class ContributionReport:
    events_total: int = 0
    overall_success_rate: float = 0.0
    cards: list[CardContribution] = field(default_factory=list)  # 按 lift 降序
    negative: list[str] = field(default_factory=list)  # 样本达标且 lift<0
    applied_suspect: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "events_total": self.events_total,
            "overall_success_rate": round(self.overall_success_rate, 4),
            "cards": [c.to_dict() for c in self.cards],
            "negative": self.negative,
            "applied_suspect": self.applied_suspect,
        }


def _success(loaded: LoadedEvent) -> bool:
    return loaded.event.outcome.status == "success"


def compute(
    vault: Vault,
    events: list[LoadedEvent],
    *,
    min_events: int = DEFAULT_MIN_EVENTS,
) -> ContributionReport:
    report = ContributionReport(events_total=len(events))
    if not events:
        return report
    total_success = sum(1 for le in events if _success(le))
    report.overall_success_rate = total_success / len(events)

    by_card: dict[str, CardContribution] = {}
    for loaded in events:
        consulted_ids = {c.card_id for c in loaded.event.cards_consulted}
        for card_id in consulted_ids:
            entry = by_card.setdefault(
                card_id,
                CardContribution(card_id=card_id, exists=card_id in vault.cards),
            )
            entry.consulted += 1
            status = loaded.event.outcome.status
            if status == "success":
                entry.success += 1
            elif status == "failure":
                entry.failure += 1
            else:
                entry.partial += 1

    for entry in by_card.values():
        entry.success_rate = entry.success / entry.consulted
        others = report.events_total - entry.consulted
        baseline_success = total_success - entry.success
        entry.baseline_rate = baseline_success / others if others else 0.0
        entry.lift = entry.success_rate - entry.baseline_rate

    report.cards = sorted(
        by_card.values(), key=lambda c: (-c.lift, -c.consulted, c.card_id)
    )
    report.negative = [
        c.card_id
        for c in report.cards
        if c.exists and c.consulted >= min_events and c.lift < 0
    ]
    return report


def run_contrib(
    vault_root: Path,
    *,
    min_events: int = DEFAULT_MIN_EVENTS,
    apply_negative: bool = False,
    actor: str = "vault-contrib",
) -> ContributionReport:
    vault = Vault.load(vault_root)
    events = load_events(vault_root).events
    report = compute(vault, events, min_events=min_events)
    if apply_negative and report.negative:
        for card_id in report.negative:
            card = vault.cards[card_id]
            if card.meta.status != "active":
                continue
            set_card_status(vault_root, card.path, "suspect")
            entry = next(c for c in report.cards if c.card_id == card_id)
            append_audit(
                vault_root,
                "contrib_signal",
                actor,
                {
                    "card_id": card_id,
                    "new_status": "suspect",
                    "lift": round(entry.lift, 4),
                    "consulted": entry.consulted,
                },
            )
            report.applied_suspect.append(card_id)
        if report.applied_suspect:
            refresh_index_if_present(vault_root)
    return report
