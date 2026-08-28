"""JSON 快照导出：一份可复算的产品数据源（页面/下游直接消费）。

确定性：同一 vault 状态必然导出同一字节序列（无时间戳、键排序、卡按 id 排序）——
快照可 diff、可缓存、可进 CI 对照。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from citebase.model import DEFAULT_HIDDEN_STATUSES, Card
from citebase.vault import Vault

SNAPSHOT_SCHEMA = "citebase-snapshot/0.1"


def visible_cards(vault: Vault, *, include_hidden: bool = False) -> list[Card]:
    cards = (
        vault.cards[card_id]
        for card_id in sorted(vault.cards)
    )
    if include_hidden:
        return list(cards)
    return [c for c in cards if c.meta.status not in DEFAULT_HIDDEN_STATUSES]


def license_warnings(vault: Vault, cards: list[Card]) -> list[dict[str, Any]]:
    """被引源许可证为 unknown 的警示清单（导出合规联动）。"""
    cited: dict[str, int] = {}
    for card in cards:
        for claim in card.meta.claims:
            for span in claim.sources:
                cited[span.source] = cited.get(span.source, 0) + 1
    warnings = []
    for source_id in sorted(cited):
        meta = vault.sources.get(source_id)
        if meta is not None and meta.license == "unknown":
            warnings.append(
                {"source": source_id, "license": "unknown", "cited_spans": cited[source_id]}
            )
    return warnings


def build_snapshot(vault: Vault, *, include_hidden: bool = False) -> dict[str, Any]:
    cards = visible_cards(vault, include_hidden=include_hidden)
    by_kind: dict[str, int] = {}
    by_status: dict[str, int] = {}
    claims = links = 0
    payload_cards: list[dict[str, Any]] = []
    for card in cards:
        meta = card.meta
        by_kind[meta.kind] = by_kind.get(meta.kind, 0) + 1
        by_status[meta.status] = by_status.get(meta.status, 0) + 1
        claims += len(meta.claims)
        links += len(meta.links)
        entry = meta.model_dump(mode="json")
        entry["body"] = card.body
        entry["path"] = card.path
        payload_cards.append(entry)
    return {
        "schema": SNAPSHOT_SCHEMA,
        "vault": vault.config.name,
        "include_hidden": include_hidden,
        "stats": {
            "cards": len(payload_cards),
            "claims": claims,
            "links": links,
            "by_kind": dict(sorted(by_kind.items())),
            "by_status": dict(sorted(by_status.items())),
        },
        "license_warnings": license_warnings(vault, cards),
        "cards": payload_cards,
    }


def export_json(
    vault: Vault, out_path: Path, *, include_hidden: bool = False
) -> dict[str, Any]:
    snapshot = build_snapshot(vault, include_hidden=include_hidden)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return snapshot
