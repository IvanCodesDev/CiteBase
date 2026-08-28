"""人工治理动词（M2）：suspect 复核与矛盾裁决——机器产信号，人平反。"""

from __future__ import annotations

from pathlib import Path

import pytest
from citebase import govern
from citebase.audit import read_audit
from citebase.drift import set_card_status
from citebase.model import CardMeta
from citebase.vault import Vault
from helpers import base_meta, make_claim, make_drift_vault, write_card

CARD_ID = "card-concept-alpha"
CONTRA_ID = "card-contradiction-alpha"


def _meta(root: Path, card_id: str) -> CardMeta:
    return Vault.load(root).cards[card_id].meta


def _setup_suspect(tmp_path: Path) -> Path:
    root, _ = make_drift_vault(tmp_path)
    write_card(root, base_meta(claims=[make_claim()]))
    set_card_status(root, Vault.load(root).cards[CARD_ID].path, "suspect")
    return root


def _write_contradiction(root: Path) -> None:
    write_card(
        root,
        base_meta(
            CONTRA_ID,
            kind="contradiction",
            name="Alpha 冲突",
            status="contested",
            claims=[
                make_claim("第一行事实。", cid="c1"),
                make_claim("第二行事实。", "extracted/text.md#L2-L2", cid="c2"),
            ],
        ),
        body="## 冲突\n\n两个论断互斥。\n",
    )


def test_review_pass_restores_active_and_refreshes_verification(tmp_path: Path) -> None:
    root = _setup_suspect(tmp_path)

    assert govern.review_suspect(root, CARD_ID, outcome="pass", actor="tester") == "active"

    meta = _meta(root, CARD_ID)
    assert meta.status == "active"
    assert [v.source for v in meta.verified_against] == ["src-notes"]
    assert meta.verified_against[0].revision.startswith("sha256:")
    last = read_audit(root)[-1]
    assert (last["action"], last["actor"], last["outcome"]) == ("suspect_review", "tester", "pass")


def test_review_retire_is_terminal(tmp_path: Path) -> None:
    root = _setup_suspect(tmp_path)

    assert govern.review_suspect(root, CARD_ID, outcome="retire") == "retired"
    assert _meta(root, CARD_ID).status == "retired"


def test_review_guards(tmp_path: Path) -> None:
    root, _ = make_drift_vault(tmp_path)
    write_card(root, base_meta(claims=[make_claim()]))

    with pytest.raises(ValueError, match="outcome"):
        govern.review_suspect(root, CARD_ID, outcome="banish")
    with pytest.raises(KeyError):
        govern.review_suspect(root, "card-ghost", outcome="pass")
    with pytest.raises(ValueError, match="不在 suspect 状态"):
        govern.review_suspect(root, CARD_ID, outcome="pass")


def test_resolve_contradiction_flow(tmp_path: Path) -> None:
    root, _ = make_drift_vault(tmp_path)
    _write_contradiction(root)

    govern.resolve_contradiction(root, CONTRA_ID, winner="c1", note="以上游为准", actor="tester")

    meta = _meta(root, CONTRA_ID)
    assert meta.status == "retired"
    assert {c.id: c.status for c in meta.claims} == {"c1": "active", "c2": "superseded"}
    last = read_audit(root)[-1]
    assert (last["action"], last["winner"]) == ("resolve", "c1")


def test_resolve_guards(tmp_path: Path) -> None:
    root, _ = make_drift_vault(tmp_path)
    write_card(root, base_meta(claims=[make_claim()]))
    _write_contradiction(root)

    with pytest.raises(KeyError):
        govern.resolve_contradiction(root, "card-ghost", winner="c1")
    with pytest.raises(ValueError, match="不是矛盾卡"):
        govern.resolve_contradiction(root, CARD_ID, winner="c1")
    with pytest.raises(ValueError, match="winner"):
        govern.resolve_contradiction(root, CONTRA_ID, winner="c9")

    govern.resolve_contradiction(root, CONTRA_ID, winner="c1")
    with pytest.raises(ValueError, match="contested"):
        govern.resolve_contradiction(root, CONTRA_ID, winner="c2")
