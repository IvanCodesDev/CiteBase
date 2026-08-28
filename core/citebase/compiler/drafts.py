"""草案 → 卡片 frontmatter：id 分配、claim 重编号、span 哈希实算。

哈希由编译器对着真实派生物实算，绝不信任 LLM 报数；定位失败留占位哈希，
由机器闸以 L-PROV-2 结构性拒绝。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from citebase import security, spanhash
from citebase.ingest import slugify
from citebase.model import SourceSpan
from citebase.ports import DraftCard
from citebase.vault import Vault

PLACEHOLDER_SHA = "0" * 64

DRAFTS_RELDIR = "_review/drafts"
REJECTED_RELDIR = "_review/rejected"


@dataclass
class StagedDraft:
    """已分配 id、哈希已实算、等待机器闸的草案。"""

    draft_id: str
    meta: dict[str, Any]
    body: str
    source_id: str
    merge_into: str | None = None
    contradiction: bool = False
    dropped_links: list[str] = field(default_factory=list)

    @property
    def relpath(self) -> str:
        return f"{DRAFTS_RELDIR}/{self.draft_id}.md"


def assign_draft_id(kind: str, name: str, taken: set[str]) -> str:
    """card-<kind>-<slug>；撞已用 id（含历史队列，id 永不复用）时追加序号。"""
    base = f"card-{kind}-{slugify(name)}"
    candidate = base
    n = 2
    while candidate in taken:
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def resolve_span(vault: Vault, source: str, loc: str) -> tuple[str, str | None]:
    """返回 (实算哈希, 片段文本)；定位失败返回占位哈希与 None（由 L-PROV-2 拒绝）。"""
    span = SourceSpan(source=source, loc=loc, span_sha256=PLACEHOLDER_SHA)
    try:
        resolved = spanhash.resolve(vault, span)
    except spanhash.SpanError:
        return PLACEHOLDER_SHA, None
    return spanhash.sha256_text(resolved.text), resolved.text


def compute_span_sha(vault: Vault, source: str, loc: str) -> str:
    return resolve_span(vault, source, loc)[0]


def draft_to_meta(
    vault: Vault, draft: DraftCard, draft_id: str, *, status: str = "active"
) -> dict[str, Any]:
    """构造 frontmatter 字典。claim 一律重编号为 c1..cN（保证卡内唯一且格式合法）。

    同时执行编译期注入扫描（威胁模型 §2-①）：正文、论断文本与被引源区段任一命中
    即置 injection_risk 旗标，随检索返回体透传给宿主。
    """
    scan_targets: list[str] = [draft.body]
    claims: list[dict[str, Any]] = []
    for i, dc in enumerate(draft.claims, start=1):
        scan_targets.append(dc.text)
        sources = []
        for s in dc.spans:
            sha, text = resolve_span(vault, s.source, s.loc)
            if text is not None:
                scan_targets.append(text)
            sources.append({"source": s.source, "loc": s.loc, "span_sha256": sha})
        claim: dict[str, Any] = {"id": f"c{i}", "text": dc.text, "sources": sources}
        if status == "contested":
            claim["status"] = "contested"
        claims.append(claim)

    meta: dict[str, Any] = {
        "id": draft_id,
        "kind": draft.kind,
        "name": draft.name,
        "summary": draft.summary,
    }
    if draft.aliases:
        meta["aliases"] = list(dict.fromkeys(draft.aliases))
    if draft.tags:
        meta["tags"] = list(dict.fromkeys(draft.tags))
    if draft.links:
        meta["links"] = [{"predicate": ln.predicate, "to": ln.to} for ln in draft.links]
    meta["claims"] = claims
    meta["version"] = 1
    meta["status"] = status
    if any(security.scan_text(target) for target in scan_targets):
        meta["injection_risk"] = True
    meta["schema_version"] = "0.1"
    return meta
