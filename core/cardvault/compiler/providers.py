"""脚本化 LlmProvider：确定性测试与离线演示用（LLM 不可用时的诚实替身）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from cardvault.ports import (
    ConflictPair,
    ContradictDecision,
    ContradictRequest,
    DraftCard,
    DraftClaim,
    DraftLink,
    DraftSpan,
    MergeDecision,
    MergeRequest,
    ProposeRequest,
    ProposeResponse,
)


def draft_from_dict(data: dict[str, Any]) -> DraftCard:
    claims = []
    for i, raw in enumerate(data.get("claims") or [], start=1):
        spans = [
            DraftSpan(source=str(s["source"]), loc=str(s["loc"]))
            for s in (raw.get("spans") or [])
        ]
        claims.append(
            DraftClaim(id=str(raw.get("id") or f"c{i}"), text=str(raw["text"]), spans=spans)
        )
    links = [
        DraftLink(predicate=str(ln["predicate"]), to=str(ln["to"]))
        for ln in (data.get("links") or [])
    ]
    return DraftCard(
        kind=str(data["kind"]),
        name=str(data["name"]),
        summary=str(data.get("summary", "")),
        body=str(data.get("body", "")),
        aliases=[str(a) for a in (data.get("aliases") or [])],
        tags=[str(t) for t in (data.get("tags") or [])],
        links=links,
        claims=claims,
    )


class ScriptedLlmProvider:
    """按剧本应答：proposals 按源 id 出草案，conflicts 按既有卡 id 出矛盾对。"""

    name = "scripted"

    def __init__(
        self,
        proposals: dict[str, list[DraftCard]] | None = None,
        conflicts: dict[str, list[ConflictPair]] | None = None,
    ) -> None:
        self._proposals = proposals or {}
        self._conflicts = conflicts or {}

    def describe(self) -> dict[str, Any]:
        return {"provider": "scripted", "name": "scripted", "temperature": 0}

    def propose(self, request: ProposeRequest) -> ProposeResponse:
        return ProposeResponse(drafts=list(self._proposals.get(request.source_id, [])))

    def merge_judge(self, request: MergeRequest) -> MergeDecision:
        return MergeDecision(verdict="unsure", reason="scripted：并卡一律交人工")

    def contradict_judge(self, request: ContradictRequest) -> ContradictDecision:
        return ContradictDecision(conflicts=list(self._conflicts.get(request.existing_id, [])))


def load_scripted(path: Path) -> ScriptedLlmProvider:
    """从 YAML 剧本构造 provider。

    形状：``{proposals: {<source_id>: [<draft dict>, …]}, conflicts: {<card_id>: [<pair>, …]}}``
    """
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    proposals = {
        str(source_id): [draft_from_dict(d) for d in drafts or []]
        for source_id, drafts in (data.get("proposals") or {}).items()
    }
    conflicts = {
        str(card_id): [
            ConflictPair(
                existing_claim=str(p["existing_claim"]),
                draft_claim=str(p["draft_claim"]),
                topic=str(p.get("topic", "")),
            )
            for p in pairs or []
        ]
        for card_id, pairs in (data.get("conflicts") or {}).items()
    }
    return ScriptedLlmProvider(proposals=proposals, conflicts=conflicts)
