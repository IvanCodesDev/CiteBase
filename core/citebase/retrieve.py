"""L3 检索漏斗：精确 → BM25 → 链接图邻域；无命中返回结构化降级信号。

漏斗顺序与无命中契约是协议语义（见 docs/architecture/retrieval-protocol.md），
加速后端替换不得改变本模块对外行为。检索默认过滤 suspect 卡与过期论断。

M4 起数据访问走 IndexBackend 端口：传 dict（``index.build()`` 产物）自动包装为
memory 后端；漏斗与打分只写这一份，后端只提供数据——对照测试保证逐分一致。
"""

from __future__ import annotations

import difflib
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from citebase import spanhash
from citebase.backends.memory import MemoryIndexBackend
from citebase.index import tokenize
from citebase.model import Card, Claim
from citebase.ports import IndexBackend
from citebase.vault import Vault

IndexLike = dict[str, Any] | IndexBackend

BM25_K1 = 1.5
BM25_B = 0.75

#: 检索默认不可见的卡片状态；contested（矛盾卡）可见但在结果中标注。
HIDDEN_STATUSES = ("suspect", "superseded", "retired")


def _as_backend(idx: IndexLike) -> IndexBackend:
    if isinstance(idx, dict):
        return MemoryIndexBackend(idx)
    return idx


@dataclass
class SearchHit:
    id: str
    name: str
    kind: str
    summary: str
    score: float
    jump: str  # exact | bm25 | graph
    status: str
    claim: str | None = None
    injection_risk: bool = False  # 威胁模型 §2-②：风险旗标随返回体透传

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "summary": self.summary,
            "score": round(self.score, 4),
            "jump": self.jump,
            "status": self.status,
            "claim": self.claim,
            "injection_risk": self.injection_risk,
        }


@dataclass
class SearchResult:
    hit: bool
    hits: list[SearchHit] = field(default_factory=list)
    tried: list[str] = field(default_factory=list)
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "hit": self.hit,
            "hits": [h.to_dict() for h in self.hits],
            "tried": self.tried,
            "suggestion": self.suggestion,
        }


def _naive(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def parse_as_of(text: str | None) -> datetime | None:
    if text is None or text == "":
        return None
    return _naive(datetime.fromisoformat(text))


def claim_valid(entry: dict[str, Any], as_of: datetime | None) -> bool:
    """catalog 里的 claim 条目在给定时点是否有效（as_of=None 表示按当前语义只过滤已过期）。

    as_of 允许带时区（drift 传 ``datetime.now(UTC)``），统一归一为 naive UTC 再比较。
    """
    if entry.get("status") != "active":
        return False
    moment = _naive(as_of) if as_of is not None else _naive(datetime.now(UTC))
    for key, after in (("valid_from", False), ("valid_until", True)):
        raw = entry.get(key)
        if raw is None:
            continue
        bound = _naive(datetime.fromisoformat(raw))
        if after and moment >= bound:
            return False
        if not after and moment < bound:
            return False
    return True


def _entry_visible(
    entry: dict[str, Any],
    include_suspect: bool,
    kind: str | None,
    tags: list[str] | None,
) -> bool:
    status = entry["status"]
    if status in HIDDEN_STATUSES and not (include_suspect and status == "suspect"):
        return False
    if kind is not None and entry["kind"] != kind:
        return False
    return not (tags and not set(tags) <= set(entry["tags"]))


def _first_claim(
    entry: dict[str, Any], query_tokens: list[str], as_of: datetime | None
) -> str | None:
    valid = [c for c in entry.get("claims", []) if claim_valid(c, as_of)]
    if not valid:
        return None
    if query_tokens:
        qset = set(query_tokens)
        for c in valid:
            if qset & set(tokenize(c["text"])):
                return str(c["text"])
    return str(valid[0]["text"])


def _make_hit(
    card_id: str,
    entry: dict[str, Any],
    score: float,
    jump: str,
    query_tokens: list[str],
    as_of: datetime | None,
) -> SearchHit:
    return SearchHit(
        id=card_id,
        name=entry["name"],
        kind=entry["kind"],
        summary=entry["summary"],
        score=score,
        jump=jump,
        status=entry["status"],
        claim=_first_claim(entry, query_tokens, as_of),
        injection_risk=bool(entry.get("injection_risk", False)),
    )


def search(
    idx: IndexLike,
    query: str,
    *,
    kind: str | None = None,
    tags: list[str] | None = None,
    as_of: datetime | None = None,
    limit: int = 10,
    include_suspect: bool = False,
) -> SearchResult:
    backend = _as_backend(idx)
    tried: list[str] = []
    query_tokens = tokenize(query)
    entry_cache: dict[str, dict[str, Any] | None] = {}

    def entry_of(card_id: str) -> dict[str, Any] | None:
        if card_id not in entry_cache:
            entry_cache[card_id] = backend.entry(card_id)
        return entry_cache[card_id]

    def visible_entry(card_id: str) -> dict[str, Any] | None:
        entry = entry_of(card_id)
        if entry is None or not _entry_visible(entry, include_suspect, kind, tags):
            return None
        return entry

    # 第一跳：名称 / 别名精确命中
    key = query.strip().casefold()
    tried.append(f"exact:{query.strip()}")
    exact: list[tuple[str, dict[str, Any]]] = []
    for cid in backend.alias_ids(key):
        entry = visible_entry(cid)
        if entry is not None:
            exact.append((cid, entry))
    if exact:
        hits = [
            _make_hit(cid, entry, 100.0, "exact", query_tokens, as_of)
            for cid, entry in exact[:limit]
        ]
        return SearchResult(hit=True, hits=hits, tried=tried)

    # 第二跳：BM25 关键词（名称/别名/标签/摘要/论断加权；打分只写这一份）
    tried.append("bm25:" + (" ".join(query_tokens) if query_tokens else "<no-tokens>"))
    n_docs, avgdl = backend.doc_stats()
    avgdl = avgdl or 1.0
    unique_tokens = sorted(set(query_tokens))
    postings_map = backend.postings(unique_tokens)
    doclen_cache: dict[str, int] = {}

    def doclen_of(card_id: str) -> int:
        if card_id not in doclen_cache:
            doclen_cache[card_id] = backend.doclen(card_id) or 1
        return doclen_cache[card_id]

    scores: dict[str, float] = {}
    for token in unique_tokens:
        postings = postings_map.get(token)
        if not postings:
            continue
        df = len(postings)
        idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
        for cid, tf in postings.items():
            dl = doclen_of(cid)
            denom = tf + BM25_K1 * (1 - BM25_B + BM25_B * dl / avgdl)
            scores[cid] = scores.get(cid, 0.0) + idf * (tf * (BM25_K1 + 1)) / denom
    ranked = sorted(
        (cid for cid in scores if visible_entry(cid) is not None),
        key=lambda c: (-scores[c], c),
    )[:limit]
    if ranked:
        hits = [
            _make_hit(cid, entry_cache[cid] or {}, scores[cid], "bm25", query_tokens, as_of)
            for cid in ranked
        ]
        return SearchResult(hit=True, hits=hits, tried=tried)

    # 第三跳：链接图邻域概念扩展（以近似别名为锚，返回其邻居）
    tried.append("graph:近似锚点邻域")
    alias_keys = backend.alias_keys()
    anchor_keys = difflib.get_close_matches(key, alias_keys, n=3, cutoff=0.6)
    neighbor_ids: list[str] = []
    for akey in anchor_keys:
        for anchor_id in backend.alias_ids(akey):
            edges = backend.links(anchor_id)
            neighbor_ids.extend(e["to"] for e in edges["out"])
            neighbor_ids.extend(e["from"] for e in edges["in"])
            neighbor_ids.append(anchor_id)
    seen: set[str] = set()
    graph_hits: list[tuple[str, dict[str, Any]]] = []
    for cid in neighbor_ids:
        if cid in seen:
            continue
        seen.add(cid)
        entry = visible_entry(cid)
        if entry is not None:
            graph_hits.append((cid, entry))
    if graph_hits:
        hits = [
            _make_hit(cid, entry, 0.5, "graph", query_tokens, as_of)
            for cid, entry in graph_hits[:limit]
        ]
        return SearchResult(hit=True, hits=hits, tried=tried)

    # 无命中契约：结构化降级信号，禁止静默回退到模型内化知识
    near = difflib.get_close_matches(key, alias_keys, n=1, cutoff=0.4)
    suggestion = "库内无相关卡片；该查询可作为建卡线索记录"
    if near:
        near_ids = backend.alias_ids(near[0])
        near_entry = entry_of(near_ids[0]) if near_ids else None
        if near_entry is not None:
            suggestion = f"库内未命中；最相近条目：{near_entry['name']}（{near_ids[0]}）"
    return SearchResult(hit=False, tried=tried, suggestion=suggestion)


# ---------- read / follow / quote ----------


def read_card(vault: Vault, card_id: str) -> Card | None:
    return vault.cards.get(card_id)


def follow(
    idx: IndexLike, card_id: str, predicate: str | None = None
) -> dict[str, list[dict[str, str]]] | None:
    backend = _as_backend(idx)
    if backend.entry(card_id) is None:
        return None
    edges = backend.links(card_id)

    def enrich(edge_list: list[dict[str, str]], key: str) -> list[dict[str, str]]:
        out = []
        for edge in edge_list:
            if predicate is not None and edge["predicate"] != predicate:
                continue
            other = edge[key]
            entry = backend.entry(other)
            out.append(
                {
                    "predicate": edge["predicate"],
                    "card": other,
                    "name": entry["name"] if entry else "<跨库或缺失>",
                    "summary": entry["summary"] if entry else "",
                }
            )
        return out

    return {
        "out": enrich(edges["out"], "to"),
        "in": enrich(edges["in"], "from"),
    }


@dataclass
class QuoteSpan:
    source: str
    loc: str
    text: str | None
    verified: bool
    uri: str
    license: str
    revision: str
    error: str | None = None


@dataclass
class QuoteResult:
    card_id: str
    card_name: str
    claim_id: str
    text: str
    status: str
    spans: list[QuoteSpan]
    injection_risk: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "card_id": self.card_id,
            "card_name": self.card_name,
            "claim_id": self.claim_id,
            "text": self.text,
            "status": self.status,
            "spans": [vars(s) for s in self.spans],
            "injection_risk": self.injection_risk,
        }


def quote(vault: Vault, ref: str) -> QuoteResult | None:
    """ref 形如 ``card-method-bootstrap#c1``。返回论断原文 + 源精确片段 + 引用元数据。"""
    if "#" not in ref:
        return None
    card_id, claim_id = ref.split("#", 1)
    card = vault.cards.get(card_id)
    if card is None:
        return None
    claim: Claim | None = next((c for c in card.meta.claims if c.id == claim_id), None)
    if claim is None:
        return None
    spans: list[QuoteSpan] = []
    for span in claim.sources:
        src = vault.sources.get(span.source)
        uri = src.uri if src else "<源未登记>"
        license_ = src.license if src else "unknown"
        revision = src.revision if src else ""
        try:
            resolved = spanhash.resolve(vault, span)
            verified = spanhash.sha256_text(resolved.text) == span.span_sha256
            spans.append(
                QuoteSpan(
                    source=span.source,
                    loc=span.loc,
                    text=resolved.text,
                    verified=verified,
                    uri=uri,
                    license=license_,
                    revision=revision,
                )
            )
        except spanhash.SpanError as e:
            spans.append(
                QuoteSpan(
                    source=span.source,
                    loc=span.loc,
                    text=None,
                    verified=False,
                    uri=uri,
                    license=license_,
                    revision=revision,
                    error=str(e),
                )
            )
    return QuoteResult(
        card_id=card_id,
        card_name=card.meta.name,
        claim_id=claim_id,
        text=claim.text,
        status=claim.status,
        spans=spans,
        injection_risk=card.meta.injection_risk,
    )
