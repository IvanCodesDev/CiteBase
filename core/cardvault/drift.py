"""失效信号总线（系统架构 §5）：漂移 + 时效两类信号（执行反例自 M3 起）。

统一消费规则：信号只把卡置为 suspect 并进复核队列，从不直接删除；suspect 卡
默认退出检索——宁可少说话，不说过期话；复核是人工 CLI 动词，机器不能自我平反。

双通道漂移：
- 通道 A（触发式）：逐源调用 changed_since(登记修订)；上游变更/无法判断 → 关联卡 suspect；
- 通道 B（哈希）：重算库内派生物 span 哈希；不一致（派生物被改/引用造假）→ 卡 suspect。
时效过期只产报告信号（检索侧已按 claim 过滤），续期/修订由复核决定。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from cardvault import frontmatter, spanhash
from cardvault import index as index_mod
from cardvault.adapters import DirSourceAdapter, FileSourceAdapter
from cardvault.audit import append_audit
from cardvault.evidence import evidence_source_changed
from cardvault.model import SourceMeta
from cardvault.ports import SourceAdapter
from cardvault.retrieve import claim_valid
from cardvault.vault import Vault


@dataclass
class DriftSignal:
    kind: str  # source_changed | source_unreachable | span_mismatch | claim_expired
    source: str = ""
    card_id: str = ""
    claim_id: str = ""
    detail: str = ""


@dataclass
class DriftReport:
    signals: list[DriftSignal] = field(default_factory=list)
    marked_suspect: list[str] = field(default_factory=list)  # 本次（或将要）置 suspect 的卡
    expired_claims: list[str] = field(default_factory=list)  # card#claim
    suspect_cards: int = 0
    total_cards: int = 0
    applied: bool = False

    @property
    def suspect_ratio(self) -> float:
        return self.suspect_cards / self.total_cards if self.total_cards else 0.0


def _adapter_for_source(meta: SourceMeta) -> SourceAdapter | None:
    if meta.adapter == "file":
        return FileSourceAdapter(Path(meta.uri))
    if meta.adapter == "dir":
        return DirSourceAdapter(Path(meta.uri))
    return None


def set_card_status(vault_root: Path, card_relpath: str, new_status: str) -> None:
    path = vault_root / card_relpath
    doc = frontmatter.load_file(path)
    doc.meta["status"] = new_status
    frontmatter.save_file(path, doc)


def refresh_index_if_present(vault_root: Path) -> None:
    """状态变更后同步落盘索引（仅当 _index/ 已存在，避免替用户做主）。"""
    if (vault_root / index_mod.INDEX_DIR).is_dir():
        vault = Vault.load(vault_root)
        index_mod.write(vault_root, index_mod.build(vault))


def scan(vault: Vault, *, now: datetime | None = None) -> DriftReport:
    """只扫描不落盘：产出信号与受影响卡清单。"""
    report = DriftReport()
    affected: dict[str, list[str]] = {}

    # 通道 A：上游修订
    for source in vault.sources.values():
        changed: bool | None
        if source.adapter == "evidence":
            # 事件不可变：以库内登记原件重算修订；缺失/被改按变更处理
            changed = evidence_source_changed(vault.root, source.id, source.revision)
        else:
            adapter = _adapter_for_source(source)
            if adapter is None:
                changed = None
            else:
                try:
                    changed = adapter.changed_since(source.revision)
                except FileNotFoundError:
                    changed = None
        if changed is False:
            continue
        kind = "source_changed" if changed else "source_unreachable"
        detail = (
            "上游内容与登记修订不一致"
            if changed
            else "无法判断上游是否变更（按已变更处理，宁可多审）"
        )
        report.signals.append(DriftSignal(kind=kind, source=source.id, detail=detail))
        for card in vault.cards.values():
            cites = any(
                span.source == source.id for c in card.meta.claims for span in c.sources
            )
            if cites:
                affected.setdefault(card.meta.id, []).append(f"{kind}:{source.id}")

    # 通道 B：库内派生物哈希
    for card in vault.cards.values():
        for claim in card.meta.claims:
            for span in claim.sources:
                try:
                    ok = spanhash.verify(vault, span)
                except spanhash.SpanError as e:
                    ok = False
                    detail = str(e)
                else:
                    detail = "span 哈希与派生物实际内容不一致（派生物被改或引用造假）"
                if not ok:
                    report.signals.append(
                        DriftSignal(
                            kind="span_mismatch",
                            source=span.source,
                            card_id=card.meta.id,
                            claim_id=claim.id,
                            detail=detail,
                        )
                    )
                    affected.setdefault(card.meta.id, []).append(
                        f"span_mismatch:{claim.id}"
                    )

    # 通道 C：时效过期（只报告；检索侧已按 claim 过滤）
    for card in vault.cards.values():
        for claim in card.meta.claims:
            if claim.status != "active" or claim.valid_until is None:
                continue
            entry = {
                "status": claim.status,
                "valid_from": claim.valid_from.isoformat() if claim.valid_from else None,
                "valid_until": claim.valid_until.isoformat(),
            }
            if not claim_valid(entry, now):
                ref = f"{card.meta.id}#{claim.id}"
                report.expired_claims.append(ref)
                report.signals.append(
                    DriftSignal(
                        kind="claim_expired",
                        card_id=card.meta.id,
                        claim_id=claim.id,
                        detail="valid_until 已到期；复核决定续期、修订或退役",
                    )
                )

    report.marked_suspect = sorted(
        card_id
        for card_id in affected
        if vault.cards[card_id].meta.status == "active"
    )
    report.total_cards = len(vault.cards)
    report.suspect_cards = sum(
        1 for c in vault.cards.values() if c.meta.status == "suspect"
    )
    return report


def run_drift(
    vault_root: Path,
    *,
    apply: bool = True,
    now: datetime | None = None,
    actor: str = "vault-drift",
) -> DriftReport:
    vault = Vault.load(vault_root)
    report = scan(vault, now=now or datetime.now(UTC))
    if apply and report.marked_suspect:
        for card_id in report.marked_suspect:
            card = vault.cards[card_id]
            set_card_status(vault_root, card.path, "suspect")
            reasons = sorted(
                {
                    f"{s.kind}:{s.source or s.claim_id}"
                    for s in report.signals
                    if s.card_id == card_id or (s.kind.startswith("source") and any(
                        span.source == s.source
                        for c in card.meta.claims
                        for span in c.sources
                    ))
                }
            )
            append_audit(
                vault_root,
                "drift_signal",
                actor,
                {"card_id": card_id, "new_status": "suspect", "reasons": reasons},
            )
        report.suspect_cards += len(report.marked_suspect)
        refresh_index_if_present(vault_root)
        report.applied = True
    return report
