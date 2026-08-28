"""人工审核队列（_review/）。

queue.yaml 台账 + drafts/ 待审 + rejected/ 留证 + history.yaml 抽样历史。
治理动词只在 CLI 暴露；每次晋升/驳回都写 _audit/（append-only）。
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from citebase import frontmatter
from citebase import index as index_mod
from citebase.audit import append_audit
from citebase.compiler.drafts import DRAFTS_RELDIR, REJECTED_RELDIR
from citebase.model import ReviewSettings
from citebase.vault import Vault

REVIEW_DIR = "_review"
QUEUE_FILE = "queue.yaml"
HISTORY_FILE = "history.yaml"


@dataclass
class QueueEntry:
    draft_id: str
    run_id: str
    source: str
    status: str  # pending | machine_rejected | approved | rejected | auto_approved
    kind: str = ""
    name: str = ""
    merge_into: str | None = None
    contradiction: bool = False
    rules: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    dropped_links: list[str] = field(default_factory=list)
    promoted_to: str = ""
    reason: str = ""
    decided_by: str = ""
    decided_at: str = ""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def queue_path(vault_root: Path) -> Path:
    return vault_root / REVIEW_DIR / QUEUE_FILE


def draft_file(vault_root: Path, draft_id: str) -> Path:
    return vault_root / DRAFTS_RELDIR / f"{draft_id}.md"


def rejected_file(vault_root: Path, draft_id: str) -> Path:
    return vault_root / REJECTED_RELDIR / f"{draft_id}.md"


def load_queue(vault_root: Path) -> list[QueueEntry]:
    path = queue_path(vault_root)
    if not path.is_file():
        return []
    raw: list[dict[str, Any]] = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [QueueEntry(**item) for item in raw]


def save_queue(vault_root: Path, entries: list[QueueEntry]) -> None:
    path = queue_path(vault_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump([asdict(e) for e in entries], sort_keys=False, allow_unicode=True),
        encoding="utf-8",
        newline="\n",
    )


def get_entry(entries: list[QueueEntry], draft_id: str) -> QueueEntry:
    for entry in entries:
        if entry.draft_id == draft_id:
            return entry
    raise KeyError(f"队列中不存在草案：{draft_id}")


def rebuild_index(vault_root: Path) -> None:
    vault = Vault.load(vault_root)
    index_mod.write(vault_root, index_mod.build(vault))


# ---------- 抽样历史（自适应抽查率，compile-pipeline §3） ----------


def history_path(vault_root: Path) -> Path:
    return vault_root / REVIEW_DIR / HISTORY_FILE


def load_history(vault_root: Path) -> dict[str, list[dict[str, Any]]]:
    path = history_path(vault_root)
    if not path.is_file():
        return {}
    data: dict[str, list[dict[str, Any]]] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data


def save_history(vault_root: Path, history: dict[str, list[dict[str, Any]]]) -> None:
    path = history_path(vault_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(history, sort_keys=True, allow_unicode=True),
        encoding="utf-8",
        newline="\n",
    )


def start_batch(
    vault_root: Path,
    source: str,
    run_id: str,
    *,
    sent_review: int,
    auto_approved: int,
    machine_rejected: int,
) -> None:
    history = load_history(vault_root)
    history.setdefault(source, []).append(
        {
            "run_id": run_id,
            "sent_review": sent_review,
            "auto_approved": auto_approved,
            "machine_rejected": machine_rejected,
            "approved": 0,
            "rejected": 0,
        }
    )
    save_history(vault_root, history)


def record_review_outcome(vault_root: Path, source: str, run_id: str, *, approved: bool) -> None:
    history = load_history(vault_root)
    for batch in history.get(source, []):
        if batch.get("run_id") == run_id:
            batch["approved" if approved else "rejected"] = (
                int(batch.get("approved" if approved else "rejected", 0)) + 1
            )
            break
    save_history(vault_root, history)


def review_rate(batches: list[dict[str, Any]], settings: ReviewSettings) -> float:
    """新源 100%；连续「已完成且通过率 ≥ good」的批次沿阶梯降档；任一批总驳回率超限回 100%。

    批次完成 = 送审数已全部有人工结论。总驳回率 =（机器拒 + 人工驳）/ 批内全部草案。
    """
    completed: list[dict[str, Any]] = []
    for batch in batches:
        reviewed = int(batch.get("approved", 0)) + int(batch.get("rejected", 0))
        if int(batch.get("sent_review", 0)) > 0 and reviewed >= int(batch.get("sent_review", 0)):
            completed.append(batch)
    if not completed:
        return settings.rates[0]

    for batch in completed:
        total = (
            int(batch.get("machine_rejected", 0))
            + int(batch.get("auto_approved", 0))
            + int(batch.get("approved", 0))
            + int(batch.get("rejected", 0))
        )
        rejected = int(batch.get("machine_rejected", 0)) + int(batch.get("rejected", 0))
        if total > 0 and rejected / total > settings.bad_reject_rate:
            return settings.rates[0]

    streak = 0
    for batch in reversed(completed):
        reviewed = int(batch.get("approved", 0)) + int(batch.get("rejected", 0))
        pass_rate = int(batch.get("approved", 0)) / reviewed if reviewed else 0.0
        if pass_rate >= settings.good_pass_rate:
            streak += 1
        else:
            break
    # 设计：连续两批达标才允许离开 100%；此后每多一批再降一档。
    level = max(0, streak - 1)
    return settings.rates[min(level, len(settings.rates) - 1)]


def sample_size(rate: float, total: int) -> int:
    if total <= 0:
        return 0
    return min(total, math.ceil(rate * total))


# ---------- 晋升与驳回 ----------


def _merge_meta(
    target_meta: dict[str, Any], draft_meta: dict[str, Any]
) -> dict[str, Any]:
    """并卡语义（M1）：摘要/论断/正文取草案，别名/标签/链接并集，version+1，id 不动。"""
    merged = dict(target_meta)
    merged["summary"] = draft_meta.get("summary", target_meta.get("summary"))
    merged["claims"] = draft_meta.get("claims", [])
    alias_pool = [
        *(target_meta.get("aliases") or []),
        *(draft_meta.get("aliases") or []),
        str(draft_meta.get("name", "")),
    ]
    merged_aliases = [a for a in dict.fromkeys(alias_pool) if a and a != target_meta.get("name")]
    if merged_aliases:
        merged["aliases"] = merged_aliases
    tag_pool = [*(target_meta.get("tags") or []), *(draft_meta.get("tags") or [])]
    if tag_pool:
        merged["tags"] = list(dict.fromkeys(tag_pool))
    link_pool = [*(target_meta.get("links") or []), *(draft_meta.get("links") or [])]
    if link_pool:
        seen: set[tuple[str, str]] = set()
        links = []
        for ln in link_pool:
            key = (str(ln.get("predicate")), str(ln.get("to")))
            if key not in seen:
                seen.add(key)
                links.append(ln)
        merged["links"] = links
    merged["version"] = int(target_meta.get("version", 1)) + 1
    return merged


def promote_draft(
    vault_root: Path, draft_id: str, *, merge_into: str | None = None, actor: str
) -> str:
    """草案离开 _review/drafts/ 进入 cards/（或并入既有卡）。返回落点相对路径。"""
    src = draft_file(vault_root, draft_id)
    if not src.is_file():
        raise FileNotFoundError(f"待审草案文件不存在：{src}")
    doc = frontmatter.load_file(src)

    if merge_into:
        vault = Vault.load(vault_root)
        target = vault.cards.get(merge_into)
        if target is None:
            raise KeyError(f"并卡目标不存在：{merge_into}")
        target_path = vault_root / target.path
        target_doc = frontmatter.load_file(target_path)
        merged = _merge_meta(target_doc.meta, doc.meta)
        frontmatter.save_file(target_path, frontmatter.Document(meta=merged, body=doc.body))
        src.unlink()
        dest_rel = target.path
    else:
        kind = str(doc.meta.get("kind", "unknown"))
        slug = draft_id.removeprefix(f"card-{kind}-") or draft_id
        dest = vault_root / "cards" / kind / f"{slug}.md"
        if dest.exists():
            raise FileExistsError(f"目标文件已存在，拒绝覆盖：{dest}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        frontmatter.save_file(dest, frontmatter.Document(meta=doc.meta, body=doc.body))
        src.unlink()
        dest_rel = dest.relative_to(vault_root).as_posix()

    rebuild_index(vault_root)
    append_audit(
        vault_root,
        "promote",
        actor,
        {"draft_id": draft_id, "dest": dest_rel, "merge_into": merge_into},
    )
    return dest_rel


def approve(
    vault_root: Path,
    draft_id: str,
    *,
    merge_into: str | None = None,
    force_new: bool = False,
    actor: str = "human",
) -> str:
    entries = load_queue(vault_root)
    entry = get_entry(entries, draft_id)
    if entry.status != "pending":
        raise ValueError(f"草案 {draft_id} 不在待审状态（当前：{entry.status}）")
    if entry.merge_into and merge_into is None and not force_new:
        raise ValueError(
            f"草案与既有卡 {entry.merge_into} 撞名：用 --merge-into {entry.merge_into} 并卡，"
            "或 --force-new 确认另立新卡"
        )
    dest_rel = promote_draft(vault_root, draft_id, merge_into=merge_into, actor=actor)
    entry.status = "approved"
    entry.promoted_to = dest_rel
    entry.decided_by = actor
    entry.decided_at = _now()
    save_queue(vault_root, entries)
    record_review_outcome(vault_root, entry.source, entry.run_id, approved=True)
    return dest_rel


def reject(vault_root: Path, draft_id: str, *, reason: str, actor: str = "human") -> None:
    entries = load_queue(vault_root)
    entry = get_entry(entries, draft_id)
    if entry.status != "pending":
        raise ValueError(f"草案 {draft_id} 不在待审状态（当前：{entry.status}）")
    src = draft_file(vault_root, draft_id)
    dest = rejected_file(vault_root, draft_id)
    if src.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        src.replace(dest)
    entry.status = "rejected"
    entry.reason = reason
    entry.decided_by = actor
    entry.decided_at = _now()
    save_queue(vault_root, entries)
    record_review_outcome(vault_root, entry.source, entry.run_id, approved=False)
    append_audit(
        vault_root, "reject", actor, {"draft_id": draft_id, "reason": reason}
    )
