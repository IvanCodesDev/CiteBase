"""检索性能基线（M4）：合成 N 卡 → memory 与 sqlite 双后端跑同一查询集 → P50/P95。

验收线（roadmap M4）：10k 卡 search P95 < 200ms。合成语料确定性生成（seed 固定），
基线可复算；查询集混合三跳（精确别名 / BM25 / 未命中），贴近真实漏斗分布。
"""

from __future__ import annotations

import random
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from citebase import index as index_mod
from citebase import retrieve
from citebase.backends.sqlite import SqliteIndexBackend, write_sqlite
from citebase.model import Card, CardMeta, VaultConfig
from citebase.vault import Vault

_WORDS = [
    "缓存", "失效", "重试", "队列", "索引", "幂等", "回滚", "分片", "一致", "哈希",
    "降级", "熔断", "限流", "预热", "穿透", "雪崩", "抖动", "漂移", "采样", "聚类",
    "校验", "出处", "论断", "漏斗", "邻域", "时效", "复核", "裁决", "证据", "回流",
    "贡献", "缺口", "快照", "站点", "联邦", "依赖", "锁定", "审计", "台账", "闸门",
]
_KINDS = ("concept", "method", "pitfall")


@dataclass
class BackendBench:
    backend: str
    queries: int
    p50_ms: float
    p95_ms: float
    max_ms: float
    setup_ms: float  # memory：整库重建；sqlite：打开缓存

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "queries": self.queries,
            "p50_ms": round(self.p50_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "setup_ms": round(self.setup_ms, 2),
        }


@dataclass
class BenchReport:
    cards: int
    build_index_ms: float
    write_sqlite_ms: float
    results: list[BackendBench]

    def to_dict(self) -> dict[str, Any]:
        return {
            "cards": self.cards,
            "build_index_ms": round(self.build_index_ms, 2),
            "write_sqlite_ms": round(self.write_sqlite_ms, 2),
            "results": [r.to_dict() for r in self.results],
        }


def synth_vault(cards: int, *, seed: int = 0) -> Vault:
    """确定性合成 vault（只为检索基线；不落盘、不参与 lint）。"""
    rng = random.Random(seed)
    vault = Vault(root=Path("."), config=VaultConfig(name=f"bench-{cards}"))
    for i in range(cards):
        words = rng.sample(_WORDS, k=6)
        kind = _KINDS[i % len(_KINDS)]
        card_id = f"card-{kind}-syn-{i:05d}"
        meta = CardMeta(
            id=card_id,
            kind=kind,
            name=f"合成{words[0]}{words[1]} {i:05d}",
            summary=f"{words[2]}与{words[3]}的合成摘要，第 {i} 张。",
            aliases=[f"syn-{i:05d}", f"{words[0]}{words[1]}{i % 100:02d}"],
            tags=[words[4]],
        )
        vault.cards[card_id] = Card(
            meta=meta, body="", path=f"cards/{kind}/syn-{i:05d}.md"
        )
    return vault


def build_queries(cards: int, queries: int, *, seed: int = 0) -> list[str]:
    """三跳混合查询集：40% 精确别名、40% BM25 词组、20% 未命中。"""
    rng = random.Random(seed + 1)
    out: list[str] = []
    for i in range(queries):
        bucket = i % 5
        if bucket in (0, 1):
            out.append(f"syn-{rng.randrange(cards):05d}")
        elif bucket in (2, 3):
            out.append(" ".join(rng.sample(_WORDS, k=2)))
        else:
            out.append(f"不存在的主题{rng.randrange(10_000)}")
    return out


def _measure(idx: Any, queries: list[str]) -> tuple[float, float, float]:
    timings: list[float] = []
    for query in queries[:3]:  # 预热（JIT 化的字典/连接路径）
        retrieve.search(idx, query)
    for query in queries:
        start = time.perf_counter()
        retrieve.search(idx, query)
        timings.append((time.perf_counter() - start) * 1000)
    timings.sort()
    p50 = statistics.median(timings)
    p95 = timings[max(0, int(len(timings) * 0.95) - 1)]
    return p50, p95, timings[-1]


def run_bench(
    *, cards: int = 10_000, queries: int = 200, seed: int = 0, workdir: Path
) -> BenchReport:
    vault = synth_vault(cards, seed=seed)

    start = time.perf_counter()
    idx = index_mod.build(vault)
    build_ms = (time.perf_counter() - start) * 1000

    start = time.perf_counter()
    sqlite_path = write_sqlite(workdir, idx)
    sqlite_ms = (time.perf_counter() - start) * 1000

    query_set = build_queries(cards, queries, seed=seed)

    results: list[BackendBench] = []
    p50, p95, worst = _measure(idx, query_set)
    results.append(
        BackendBench("memory", len(query_set), p50, p95, worst, setup_ms=build_ms)
    )

    start = time.perf_counter()
    backend = SqliteIndexBackend(sqlite_path)
    open_ms = (time.perf_counter() - start) * 1000
    p50, p95, worst = _measure(backend, query_set)
    results.append(
        BackendBench("sqlite", len(query_set), p50, p95, worst, setup_ms=open_ms)
    )
    backend.close()

    return BenchReport(
        cards=cards,
        build_index_ms=build_ms,
        write_sqlite_ms=sqlite_ms,
        results=results,
    )
