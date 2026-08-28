"""人工治理动词：suspect 复核（audit review）与矛盾裁决（resolve）。

机器只产信号，不能自我平反；裁决与复核只在 CLI，全部写 _audit（append-only）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from citebase import frontmatter
from citebase.audit import append_audit
from citebase.drift import refresh_index_if_present, set_card_status
from citebase.model import Card
from citebase.vault import Vault

SUSPECT_OUTCOMES = ("pass", "retire")


def list_suspects(vault_root: Path) -> list[Card]:
    vault = Vault.load(vault_root)
    return sorted(
        (c for c in vault.cards.values() if c.meta.status == "suspect"),
        key=lambda c: c.meta.id,
    )


def review_suspect(
    vault_root: Path,
    card_id: str,
    *,
    outcome: str,
    note: str = "",
    actor: str = "human",
) -> str:
    """复核 suspect 卡：pass → active + 刷新 verified_against；retire → 终态退役。"""
    if outcome not in SUSPECT_OUTCOMES:
        raise ValueError(f"outcome 只能是 {SUSPECT_OUTCOMES}，收到：{outcome}")
    vault = Vault.load(vault_root)
    card = vault.cards.get(card_id)
    if card is None:
        raise KeyError(f"卡片不存在：{card_id}")
    if card.meta.status != "suspect":
        raise ValueError(f"卡片不在 suspect 状态（当前：{card.meta.status}），无需复核")

    if outcome == "pass":
        cited = sorted({s.source for c in card.meta.claims for s in c.sources})
        today = datetime.now(UTC).date().isoformat()
        verified = [
            {"source": sid, "revision": vault.sources[sid].revision, "at": today}
            for sid in cited
            if sid in vault.sources
        ]
        path = vault_root / card.path
        doc = frontmatter.load_file(path)
        doc.meta["status"] = "active"
        if verified:
            doc.meta["verified_against"] = verified
        frontmatter.save_file(path, doc)
        new_status = "active"
    else:
        set_card_status(vault_root, card.path, "retired")
        new_status = "retired"

    append_audit(
        vault_root,
        "suspect_review",
        actor,
        {"card_id": card_id, "outcome": outcome, "new_status": new_status, "note": note},
    )
    refresh_index_if_present(vault_root)
    return new_status


def resolve_contradiction(
    vault_root: Path,
    card_id: str,
    *,
    winner: str,
    note: str = "",
    actor: str = "human",
) -> None:
    """裁决矛盾卡：胜方论断 active、败方 superseded、矛盾卡本体 retired（历史可查）。

    编译器绝不自动裁决（provenance-and-drift §3）；本动词只在 CLI 暴露。
    """
    vault = Vault.load(vault_root)
    card = vault.cards.get(card_id)
    if card is None:
        raise KeyError(f"矛盾卡不存在：{card_id}")
    if card.meta.kind != "contradiction":
        raise ValueError(f"{card_id} 不是矛盾卡（kind={card.meta.kind}）")
    if card.meta.status != "contested":
        raise ValueError(f"矛盾卡不在 contested 状态（当前：{card.meta.status}），无法重复裁决")
    claim_ids = [c.id for c in card.meta.claims]
    if winner not in claim_ids:
        raise ValueError(f"winner 必须是矛盾卡内的论断 id（{claim_ids}），收到：{winner}")

    path = vault_root / card.path
    doc = frontmatter.load_file(path)
    for claim in doc.meta.get("claims", []):
        claim["status"] = "active" if claim.get("id") == winner else "superseded"
    doc.meta["status"] = "retired"
    frontmatter.save_file(path, doc)

    append_audit(
        vault_root,
        "resolve",
        actor,
        {"card_id": card_id, "winner": winner, "note": note},
    )
    refresh_index_if_present(vault_root)
