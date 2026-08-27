"""评测：golden set（M0：命中率 / 首位命中率）与忠实度抽查（M3）。

golden.yaml 条目：``{q: 查询, expect: [卡 id, ...], expect_rank: 3}``；
hit = 任一期望卡进入 top-limit；first_hit = 排名第一即命中；
expect_rank 给出时额外校验「期望卡进入前 N」。

忠实度抽查（provenance-and-drift §2.1 双通道的落地）：哈希通道机器自动判定
（span 无法解析/哈希失配 = 论断与源脱钩）；语义通道产出「论断原文 + 源片段」
抽样清单交人工核对——语义忠实与否只能由人（或后续接入的 LLM 核对器）裁定，
机器不冒充。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from cardvault import spanhash
from cardvault.retrieve import search
from cardvault.vault import Vault


@dataclass
class GoldenCase:
    q: str
    expect: list[str]
    expect_rank: int | None = None


@dataclass
class EvalReport:
    total: int = 0
    hits: int = 0
    first_hits: int = 0
    rank_failures: int = 0
    misses: list[dict[str, Any]] = field(default_factory=list)

    @property
    def hit_rate(self) -> float:
        return self.hits / self.total if self.total else 0.0

    @property
    def first_hit_rate(self) -> float:
        return self.first_hits / self.total if self.total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "hits": self.hits,
            "first_hits": self.first_hits,
            "rank_failures": self.rank_failures,
            "hit_rate": round(self.hit_rate, 4),
            "first_hit_rate": round(self.first_hit_rate, 4),
            "misses": self.misses,
        }


def load_golden(path: Path) -> list[GoldenCase]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise ValueError("golden 文件必须是用例列表")
    cases = []
    for item in data:
        cases.append(
            GoldenCase(
                q=str(item["q"]),
                expect=[str(x) for x in item["expect"]],
                expect_rank=item.get("expect_rank"),
            )
        )
    return cases


def run(idx: dict[str, Any], cases: list[GoldenCase], limit: int = 10) -> EvalReport:
    report = EvalReport(total=len(cases))
    for case in cases:
        result = search(idx, case.q, limit=limit)
        ids = [h.id for h in result.hits]
        expected = set(case.expect)
        hit_positions = [i for i, cid in enumerate(ids) if cid in expected]
        if hit_positions:
            report.hits += 1
            if hit_positions[0] == 0:
                report.first_hits += 1
            rank = hit_positions[0] + 1
            if case.expect_rank is not None and rank > case.expect_rank:
                report.rank_failures += 1
                report.misses.append(
                    {
                        "q": case.q,
                        "why": f"命中但排名 {rank} 超出 expect_rank={case.expect_rank}",
                        "got": ids[:5],
                    }
                )
        else:
            report.misses.append({"q": case.q, "why": "top-limit 未命中", "got": ids[:5]})
    return report


# ---------- 忠实度抽查（M3） ----------


@dataclass
class FaithfulnessReport:
    population: int = 0  # 可抽样论断总数（active 卡的 active 论断）
    sampled: int = 0
    unfaithful: list[dict[str, Any]] = field(default_factory=list)  # 哈希通道自动判定
    checklist: list[dict[str, Any]] = field(default_factory=list)  # 语义通道人工核对清单

    @property
    def unfaithful_rate(self) -> float:
        return len(self.unfaithful) / self.sampled if self.sampled else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "population": self.population,
            "sampled": self.sampled,
            "unfaithful": self.unfaithful,
            "unfaithful_rate": round(self.unfaithful_rate, 4),
            "checklist": self.checklist,
        }


def run_faithfulness(
    vault: Vault, *, sample: int = 50, seed: int = 0
) -> FaithfulnessReport:
    """抽样核验论断与源片段的绑定：哈希失配/无法解析 = 机器可判的不忠实。

    抽样确定性由 seed 保证（榜单与红线可复算）；语义核对清单随报告导出。
    """
    population: list[tuple[str, str, Any]] = []
    for card_id in sorted(vault.cards):
        card = vault.cards[card_id]
        if card.meta.status != "active":
            continue
        for claim in card.meta.claims:
            if claim.status == "active":
                population.append((card_id, claim.id, claim))

    report = FaithfulnessReport(population=len(population))
    if not population:
        return report
    if len(population) > sample:
        rng = random.Random(seed)
        chosen = rng.sample(population, sample)
        chosen.sort(key=lambda item: (item[0], item[1]))
    else:
        chosen = population
    report.sampled = len(chosen)

    for card_id, claim_id, claim in chosen:
        ref = f"{card_id}#{claim_id}"
        spans_out: list[dict[str, Any]] = []
        problems: list[str] = []
        for span in claim.sources:
            try:
                resolved = spanhash.resolve(vault, span)
            except spanhash.SpanError as e:
                spans_out.append(
                    {"loc": f"{span.source}/{span.loc}", "text": None, "verified": False}
                )
                problems.append(str(e))
                continue
            verified = spanhash.sha256_text(resolved.text) == span.span_sha256
            spans_out.append(
                {"loc": f"{span.source}/{span.loc}", "text": resolved.text, "verified": verified}
            )
            if not verified:
                problems.append(f"span 哈希失配：{span.source}/{span.loc}")
        if problems:
            report.unfaithful.append({"ref": ref, "why": "; ".join(problems)})
        report.checklist.append(
            {"ref": ref, "claim": claim.text, "spans": spans_out}
        )
    return report
