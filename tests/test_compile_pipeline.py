from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from citebase import frontmatter
from citebase.audit import read_audit
from citebase.compiler import approve, compile_vault, load_queue, reject
from citebase.compiler.compile_log import read_manifest
from citebase.compiler.providers import ScriptedLlmProvider
from citebase.compiler.review import load_history
from citebase.ports import ConflictPair, DraftCard, DraftClaim, DraftLink, DraftSpan
from citebase.vault import Vault
from helpers import base_meta, make_claim, write_card


def sourced_claim(text: str = "第一行事实。", loc: str = "extracted/text.md#L1-L1") -> DraftClaim:
    return DraftClaim(id="c1", text=text, spans=[DraftSpan(source="src-notes", loc=loc)])


def make_draft(
    name: str,
    *,
    kind: str = "concept",
    claims: list[DraftClaim] | None = None,
    links: list[DraftLink] | None = None,
    aliases: list[str] | None = None,
) -> DraftCard:
    return DraftCard(
        kind=kind,
        name=name,
        summary="一句话摘要。",
        body="## 是什么\n\n正文。\n",
        aliases=aliases or [],
        links=links or [],
        claims=claims if claims is not None else [sourced_claim()],
    )


def test_happy_path_review_then_approve_and_reject(mini_vault: Path) -> None:
    provider = ScriptedLlmProvider(
        {
            "src-notes": [
                make_draft("Backoff Notes"),
                make_draft(
                    "CV Notes",
                    kind="method",
                    claims=[sourced_claim("第二行事实。", "extracted/text.md#L2-L2")],
                ),
            ]
        }
    )
    report = compile_vault(mini_vault, provider)

    assert report.proposed == 2
    assert len(report.pending) == 2  # 新源 100% 送审
    assert report.auto_approved == []
    assert report.machine_rejected == {}
    for draft_id in report.pending:
        assert (mini_vault / "_review" / "drafts" / f"{draft_id}.md").is_file()

    manifest = read_manifest(mini_vault, report.run_id)
    assert manifest["outputs"]["pending_review"] == 2
    assert manifest["model"]["provider"] == "scripted"
    assert "propose.v1.prompt.md#sha256:" in manifest["prompts"]["propose"]

    first, second = sorted(report.pending)
    dest = approve(mini_vault, first, actor="tester")
    assert (mini_vault / dest).is_file()
    vault = Vault.load(mini_vault)
    assert first in vault.cards

    reject(mini_vault, second, reason="质量不足", actor="tester")
    assert (mini_vault / "_review" / "rejected" / f"{second}.md").is_file()
    assert second not in Vault.load(mini_vault).cards

    statuses = {e.draft_id: e.status for e in load_queue(mini_vault)}
    assert statuses[first] == "approved"
    assert statuses[second] == "rejected"

    batches = load_history(mini_vault)["src-notes"]
    assert batches[0]["approved"] == 1
    assert batches[0]["rejected"] == 1

    actions = [r["action"] for r in read_audit(mini_vault)]
    assert "compile_run" in actions
    assert "promote" in actions
    assert "reject" in actions


def test_adversarial_sourceless_claims_intercepted_100_percent(mini_vault: Path) -> None:
    """M1 验收线：注入 5 个无源论断的对抗样本，机器闸拦截率必须 100%。"""
    drafts = [
        DraftCard(
            kind="concept",
            name=f"Fabricated {i}",
            summary="没有出处的编造论断。",
            body="## 是什么\n\n编造内容。\n",
            claims=[DraftClaim(id="c1", text=f"凭空编造的事实 {i}", spans=[])],
        )
        for i in range(5)
    ]
    report = compile_vault(mini_vault, ScriptedLlmProvider({"src-notes": drafts}))

    assert report.proposed == 5
    assert len(report.machine_rejected) == 5
    assert report.pending == []
    assert report.auto_approved == []
    assert report.interception_rate == 1.0
    for reasons in report.machine_rejected.values():
        assert any("L-PROV-1" in reason for reason in reasons)

    for entry in load_queue(mini_vault):
        assert entry.status == "machine_rejected"
        assert "L-PROV-1" in entry.rules
        assert (mini_vault / "_review" / "rejected" / f"{entry.draft_id}.md").is_file()
    assert not (mini_vault / "cards").exists() or not list(
        (mini_vault / "cards").rglob("*.md")
    )


def test_mixed_batch_intercepts_only_invalid(mini_vault: Path) -> None:
    drafts = [make_draft("Good One")] + [
        DraftCard(
            kind="concept",
            name=f"Bad {i}",
            summary="无源。",
            body="x",
            claims=[DraftClaim(id="c1", text="无源论断", spans=[])],
        )
        for i in range(5)
    ]
    report = compile_vault(mini_vault, ScriptedLlmProvider({"src-notes": drafts}))
    assert report.proposed == 6
    assert len(report.machine_rejected) == 5
    assert len(report.pending) == 1


def test_unresolvable_span_rejected_by_l_prov_2(mini_vault: Path) -> None:
    draft = make_draft(
        "Ghost Span", claims=[sourced_claim("越界论断", "extracted/text.md#L1-L99")]
    )
    report = compile_vault(mini_vault, ScriptedLlmProvider({"src-notes": [draft]}))
    assert len(report.machine_rejected) == 1
    reasons = next(iter(report.machine_rejected.values()))
    assert any("L-PROV-2" in r for r in reasons)


def test_unknown_kind_rejected_by_l_pack_1(mini_vault: Path) -> None:
    report = compile_vault(
        mini_vault,
        ScriptedLlmProvider({"src-notes": [make_draft("Theorem X", kind="theorem")]}),
    )
    reasons = next(iter(report.machine_rejected.values()))
    assert any("L-PACK-1" in r for r in reasons)


def test_illegal_links_dropped_but_draft_survives(mini_vault: Path) -> None:
    write_card(mini_vault, base_meta("card-concept-anchor", name="Anchor"))
    draft = make_draft(
        "Linker",
        links=[
            DraftLink(predicate="related_to", to="card-concept-anchor"),  # 合法，保留
            DraftLink(predicate="related_to", to="card-concept-ghost"),  # 目标缺失，丢弃
            DraftLink(predicate="loves", to="card-concept-anchor"),  # 谓词越界，丢弃
        ],
    )
    report = compile_vault(mini_vault, ScriptedLlmProvider({"src-notes": [draft]}))
    assert len(report.pending) == 1
    draft_id = report.pending[0]
    assert sorted(report.dropped_links[draft_id]) == [
        "loves->card-concept-anchor",
        "related_to->card-concept-ghost",
    ]
    doc = frontmatter.load_file(mini_vault / "_review" / "drafts" / f"{draft_id}.md")
    assert doc.meta["links"] == [{"predicate": "related_to", "to": "card-concept-anchor"}]


def test_merge_candidate_forced_review_and_merge(mini_vault: Path) -> None:
    write_card(mini_vault, base_meta(claims=[make_claim()]))  # card-concept-alpha「Alpha」
    draft = make_draft(
        "Alpha", claims=[sourced_claim("第二行事实。", "extracted/text.md#L2-L2")]
    )
    report = compile_vault(
        mini_vault,
        ScriptedLlmProvider({"src-notes": [draft]}),
        review_rate_override=0.0,  # 即使抽样率归零，并卡候选也必须送审
    )
    assert len(report.pending) == 1
    draft_id = report.pending[0]
    assert report.merge_candidates[draft_id] == "card-concept-alpha"

    with pytest.raises(ValueError, match="撞名"):
        approve(mini_vault, draft_id, actor="tester")

    approve(mini_vault, draft_id, merge_into="card-concept-alpha", actor="tester")
    vault = Vault.load(mini_vault)
    merged = vault.cards["card-concept-alpha"]
    assert merged.meta.version == 2
    assert [c.text for c in merged.meta.claims] == ["第二行事实。"]
    assert not (mini_vault / "_review" / "drafts" / f"{draft_id}.md").exists()


def test_contradiction_card_generated_not_auto_resolved(mini_vault: Path) -> None:
    write_card(mini_vault, base_meta(claims=[make_claim()]))
    draft = make_draft(
        "Alpha", claims=[sourced_claim("第二行事实。", "extracted/text.md#L2-L2")]
    )
    provider = ScriptedLlmProvider(
        {"src-notes": [draft]},
        conflicts={"card-concept-alpha": [ConflictPair("c1", "c1", "取值范围")]},
    )
    report = compile_vault(mini_vault, provider)

    assert len(report.contradictions) == 1
    contra_id = report.contradictions[0]
    assert contra_id.startswith("card-contradiction-")
    assert contra_id not in report.machine_rejected
    assert contra_id in report.pending  # 矛盾卡一律送审，绝不自动裁决

    doc = frontmatter.load_file(mini_vault / "_review" / "drafts" / f"{contra_id}.md")
    assert doc.meta["kind"] == "contradiction"
    assert doc.meta["status"] == "contested"
    claims = doc.meta["claims"]
    assert len(claims) == 2
    assert all(c["status"] == "contested" for c in claims)
    assert all(c["sources"] for c in claims)


def test_rate_zero_auto_approves_plain_drafts(mini_vault: Path) -> None:
    drafts = [make_draft("Auto One"), make_draft("Auto Two")]
    report = compile_vault(
        mini_vault, ScriptedLlmProvider({"src-notes": drafts}), review_rate_override=0.0
    )
    assert len(report.auto_approved) == 2
    assert report.pending == []
    vault = Vault.load(mini_vault)
    for draft_id in report.auto_approved:
        assert draft_id in vault.cards
    catalog = yaml.safe_load((mini_vault / "_index" / "catalog.json").read_text("utf-8"))
    for draft_id in report.auto_approved:
        assert draft_id in catalog


def test_unknown_source_raises(mini_vault: Path) -> None:
    with pytest.raises(ValueError, match="未登记"):
        compile_vault(mini_vault, ScriptedLlmProvider(), source_ids=["src-ghost"])


def test_source_without_derivatives_skipped(mini_vault: Path) -> None:
    src_dir = mini_vault / "sources" / "src-empty"
    src_dir.mkdir(parents=True)
    (src_dir / "meta.yaml").write_text(
        "id: src-empty\nadapter: file\nuri: x\nrevision: v1\n", encoding="utf-8"
    )
    report = compile_vault(
        mini_vault, ScriptedLlmProvider(), source_ids=["src-empty"]
    )
    assert report.skipped_sources == ["src-empty"]
    assert report.proposed == 0
