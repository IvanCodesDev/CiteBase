"""回流编译器（M3，compile-pipeline §5）：evidence 事件 → 陷阱卡草案 → 两道闸。

确定性特化管线（不调 LLM）：失败按 ``failure.category`` 聚类，达到阈值（默认 ≥2
次同类失败）才提卡——单次失败先记台账不成卡，防噪声；claims 逐事件绑定事件源
派生物的行（哈希由编译器实算）；**回流不豁免治理**：机器闸照跑，且回流草案
一律送审（不参与自适应抽样降档）——这是防「恶意 Agent 借回流投毒」的结构防线
（威胁模型 §2-③）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cardvault import __version__, frontmatter
from cardvault.audit import append_audit
from cardvault.compiler.compile_log import COMPILE_LOG_DIR, write_manifest
from cardvault.compiler.drafts import StagedDraft, assign_draft_id, draft_to_meta
from cardvault.compiler.pipeline import _machine_gate
from cardvault.compiler.review import QueueEntry, load_queue, rejected_file, save_queue
from cardvault.evidence import (
    LoadedEvent,
    claim_loc,
    load_events,
    register_event_source,
)
from cardvault.ports import DraftCard, DraftClaim, DraftLink, DraftSpan
from cardvault.vault import Vault

DEFAULT_MIN_CLUSTER = 2
DEFAULT_KIND = "pitfall"


@dataclass
class BackflowReport:
    run_id: str
    events_total: int = 0
    new_sources: int = 0
    invalid_lines: list[dict[str, Any]] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    uncategorized: int = 0  # 失败/部分失败但无 category，无法聚类
    clusters: dict[str, int] = field(default_factory=dict)  # category → 事件数
    below_threshold: dict[str, int] = field(default_factory=dict)
    already_covered: dict[str, str] = field(default_factory=dict)  # category → 卡/草案 id
    pending: list[str] = field(default_factory=list)
    machine_rejected: dict[str, list[str]] = field(default_factory=dict)
    injection_flagged: int = 0


def next_backflow_run_id(vault_root: Path, *, now: datetime | None = None) -> str:
    moment = now or datetime.now(UTC)
    date = moment.strftime("%Y-%m-%d")
    log_dir = vault_root / COMPILE_LOG_DIR
    n = 1
    while (log_dir / f"backflow-{date}-{n:03d}.yaml").exists():
        n += 1
    return f"backflow-{date}-{n:03d}"


def _cluster_failures(
    events: list[LoadedEvent], report: BackflowReport
) -> dict[str, list[LoadedEvent]]:
    """按规范化 category 聚类失败事件；无 category 的失败只计数不聚类。"""
    clusters: dict[str, list[LoadedEvent]] = {}
    display: dict[str, str] = {}
    for loaded in events:
        event = loaded.event
        if event.outcome.status not in ("failure", "partial"):
            continue
        category = event.failure.category if event.failure else None
        if not category:
            report.uncategorized += 1
            continue
        key = " ".join(category.split()).casefold()
        display.setdefault(key, category)
        clusters.setdefault(key, []).append(loaded)
    return {display[key]: group for key, group in clusters.items()}


def _existing_coverage(
    vault: Vault, queue_pending_names: dict[str, str], category: str, group: list[LoadedEvent]
) -> str | None:
    """该类失败是否已有卡/草案承接：按名称别名对齐，或已有卡引用了聚类内事件源。"""
    normalized = category.casefold()
    for card in vault.cards.values():
        names = {card.meta.name.casefold(), *(a.casefold() for a in card.meta.aliases)}
        if normalized in names:
            return card.meta.id
    event_ids = {loaded.event.event_id for loaded in group}
    for card in vault.cards.values():
        for claim in card.meta.claims:
            if any(span.source in event_ids for span in claim.sources):
                return card.meta.id
    return queue_pending_names.get(normalized)


def _claim_text(loaded: LoadedEvent, category: str) -> str:
    event = loaded.event
    if event.failure and event.failure.summary:
        return " ".join(event.failure.summary.split())
    ref = event.task_ref or event.event_id
    return f"任务 {ref} 出现「{category}」类失败"


def _draft_body(
    category: str, group: list[LoadedEvent], linked: list[str]
) -> str:
    phenomena = "\n".join(
        f"- {le.event.event_id}：{_claim_text(le, category)}" for le in group
    )
    hypotheses = [
        " ".join(le.event.failure.root_cause_hypothesis.split())
        for le in group
        if le.event.failure and le.event.failure.root_cause_hypothesis
    ]
    roots = (
        "\n".join(f"- {h}" for h in dict.fromkeys(hypotheses))
        if hypotheses
        else "待人工复核补充。"
    )
    systems = sorted({le.event.system.name for le in group})
    relations = "\n".join(f"- {card_id}" for card_id in linked) if linked else "无。"
    return (
        f"## 现象\n\n{phenomena}\n\n"
        f"## 根因\n\n{roots}\n\n"
        "## 规避\n\n待人工复核补充。\n\n"
        f"## 触发条件\n\n- 来源：{len(group)} 次「{category}」执行失败"
        f"（投递系统：{', '.join(systems)}）\n\n"
        f"## 关联\n\n{relations}\n"
    )


def run_backflow(
    vault_root: Path,
    *,
    min_cluster: int = DEFAULT_MIN_CLUSTER,
    kind: str = DEFAULT_KIND,
    actor: str | None = None,
) -> BackflowReport:
    vault = Vault.load(vault_root)
    if kind not in vault.enabled_kinds():
        raise ValueError(
            f"卡类 {kind} 不在启用 Pack 的词表内（当前：{sorted(vault.enabled_kinds())}）"
        )
    actor = actor or f"backflow@{__version__}"
    run_id = next_backflow_run_id(vault_root)
    report = BackflowReport(run_id=run_id)

    loaded_result = load_events(vault_root)
    report.events_total = len(loaded_result.events)
    report.invalid_lines = loaded_result.invalid
    report.duplicates = loaded_result.duplicates

    for loaded in loaded_result.events:
        if register_event_source(vault_root, loaded):
            report.new_sources += 1
    vault = Vault.load(vault_root)  # 事件源已登记，重载事实源

    clusters = _cluster_failures(loaded_result.events, report)
    queue = load_queue(vault_root)
    queue_pending_names = {
        entry.name.casefold(): entry.draft_id
        for entry in queue
        if entry.status == "pending" and entry.name
    }
    taken: set[str] = set(vault.cards) | {entry.draft_id for entry in queue}
    enabled_predicates = vault.enabled_predicates()

    staged: list[StagedDraft] = []
    for category in sorted(clusters):
        group = sorted(clusters[category], key=lambda le: (le.event.ts, le.event.event_id))
        report.clusters[category] = len(group)
        if len(group) < min_cluster:
            report.below_threshold[category] = len(group)
            continue
        covered = _existing_coverage(vault, queue_pending_names, category, group)
        if covered is not None:
            report.already_covered[category] = covered
            continue

        consulted = sorted(
            {
                card.card_id
                for le in group
                for card in le.event.cards_consulted
                if card.card_id in vault.cards
            }
        )
        links = (
            [DraftLink(predicate="related_to", to=card_id) for card_id in consulted]
            if "related_to" in enabled_predicates
            else []
        )
        claims = [
            DraftClaim(
                id=f"c{i}",
                text=_claim_text(le, category),
                spans=[DraftSpan(source=le.event.event_id, loc=claim_loc(le.event))],
            )
            for i, le in enumerate(group, start=1)
        ]
        draft = DraftCard(
            kind=kind,
            name=category,
            summary=f"{len(group)} 次「{category}」执行失败回流的经验，待人工复核。"[:80],
            body=_draft_body(category, group, consulted),
            claims=claims,
            links=links,
        )
        draft_id = assign_draft_id(kind, category, taken)
        taken.add(draft_id)
        staged.append(
            StagedDraft(
                draft_id=draft_id,
                meta=draft_to_meta(vault, draft, draft_id),
                body=draft.body,
                source_id=group[0].event.event_id,
            )
        )

    for sd in staged:
        path = vault_root / sd.relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        frontmatter.save_file(path, frontmatter.Document(meta=sd.meta, body=sd.body))

    rejected_map, warnings_map = _machine_gate(vault_root, staged)
    for sd in staged:
        if sd.meta.get("injection_risk") is True:
            report.injection_flagged += 1
        if sd.draft_id in rejected_map:
            findings = rejected_map[sd.draft_id]
            src = vault_root / sd.relpath
            dest = rejected_file(vault_root, sd.draft_id)
            dest.parent.mkdir(parents=True, exist_ok=True)
            src.replace(dest)
            queue.append(
                QueueEntry(
                    draft_id=sd.draft_id,
                    run_id=run_id,
                    source=sd.source_id,
                    status="machine_rejected",
                    kind=str(sd.meta.get("kind", "")),
                    name=str(sd.meta.get("name", "")),
                    rules=[rule for rule, _ in findings],
                    messages=[msg for _, msg in findings],
                )
            )
            report.machine_rejected[sd.draft_id] = [
                f"{rule}: {msg}" for rule, msg in findings
            ]
        else:
            # 回流草案一律送审：不参与自适应抽样，不自动入库
            queue.append(
                QueueEntry(
                    draft_id=sd.draft_id,
                    run_id=run_id,
                    source=sd.source_id,
                    status="pending",
                    kind=str(sd.meta.get("kind", "")),
                    name=str(sd.meta.get("name", "")),
                    warnings=warnings_map.get(sd.draft_id, []),
                )
            )
            report.pending.append(sd.draft_id)
    save_queue(vault_root, queue)

    manifest: dict[str, Any] = {
        "run_id": run_id,
        "inputs": {
            "events_total": report.events_total,
            "invalid_lines": len(report.invalid_lines),
            "duplicates": len(report.duplicates),
        },
        "model": {"provider": "backflow", "name": "deterministic", "min_cluster": min_cluster},
        "outputs": {
            "new_sources": report.new_sources,
            "clusters": report.clusters,
            "below_threshold": report.below_threshold,
            "already_covered": report.already_covered,
            "pending_review": len(report.pending),
            "machine_rejected": len(report.machine_rejected),
            "injection_flagged": report.injection_flagged,
            "uncategorized": report.uncategorized,
        },
    }
    write_manifest(vault_root, run_id, manifest)
    append_audit(
        vault_root,
        "backflow_run",
        actor,
        {"run_id": run_id, "outputs": manifest["outputs"]},
    )
    return report
