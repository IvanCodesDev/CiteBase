"""七步编译循环（compile-pipeline §1）。

① extract 已由 ``vault ingest`` 预先完成；本模块执行 ② propose → ③ merge 对齐 →
④ interlink 过滤 → ⑤ contradict → ⑥ validate 机器闸 → ⑦ review 抽样闸。

机器闸复用 lint 的同一套规则（质量门铁律：规则只写一份），跑在「基库 + 草案」的
虚拟视图上；无源论断在 schema 层即被结构性拒绝（L-PROV-1）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema

from cardvault import __version__, frontmatter
from cardvault import lint as lint_mod
from cardvault.audit import append_audit
from cardvault.compiler.compile_log import next_run_id, write_manifest
from cardvault.compiler.drafts import (
    StagedDraft,
    assign_draft_id,
    draft_to_meta,
)
from cardvault.compiler.promptload import load_prompt
from cardvault.compiler.review import (
    QueueEntry,
    load_history,
    load_queue,
    promote_draft,
    rejected_file,
    review_rate,
    sample_size,
    save_queue,
    start_batch,
)
from cardvault.model import Card, CardKindDef, CardMeta, Pack
from cardvault.ports import (
    CardDigest,
    ConflictPair,
    ContradictRequest,
    LlmProvider,
    ProposeRequest,
    TokenUsage,
)
from cardvault.vault import Vault


@dataclass
class CompileReport:
    run_id: str
    sources: list[str]
    proposed: int = 0
    pending: list[str] = field(default_factory=list)
    auto_approved: list[str] = field(default_factory=list)
    machine_rejected: dict[str, list[str]] = field(default_factory=dict)
    contradictions: list[str] = field(default_factory=list)
    merge_candidates: dict[str, str] = field(default_factory=dict)
    dropped_links: dict[str, list[str]] = field(default_factory=dict)
    warnings: dict[str, list[str]] = field(default_factory=dict)
    skipped_sources: list[str] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)

    @property
    def interception_rate(self) -> float:
        """机器闸拦截数 /（拦截数 + 放行数）——对抗演练用的观测指标。"""
        total = len(self.machine_rejected) + len(self.pending) + len(self.auto_approved)
        return len(self.machine_rejected) / total if total else 0.0


def _merged_pack(vault: Vault) -> Pack:
    kinds: dict[str, CardKindDef] = {}
    predicates: list[str] = []
    vocab: dict[str, list[str]] = {}
    for pack in vault.packs.values():
        for kind_def in pack.card_kinds:
            kinds.setdefault(kind_def.kind, kind_def)
        predicates.extend(pack.link_predicates)
        vocab.update(pack.tag_vocab)
    return Pack(
        name="enabled",
        version="0",
        description="运行时合并的启用词表",
        card_kinds=list(kinds.values()),
        link_predicates=sorted(set(predicates)),
        tag_vocab=vocab,
    )


def _read_derivatives(vault_root: Path, source_id: str) -> dict[str, str]:
    extracted_dir = vault_root / "sources" / source_id / "extracted"
    if not extracted_dir.is_dir():
        return {}
    out: dict[str, str] = {}
    for file in sorted(extracted_dir.rglob("*")):
        if file.is_file():
            rel = file.relative_to(extracted_dir).as_posix()
            out[f"extracted/{rel}"] = file.read_text(encoding="utf-8")
    return out


def _alias_map(vault: Vault) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for card_id in sorted(vault.cards):
        meta = vault.cards[card_id].meta
        for alias in [meta.name, *meta.aliases]:
            mapping.setdefault(alias.casefold(), card_id)
    return mapping


def _is_missing_sources(error: jsonschema.exceptions.ValidationError) -> bool:
    path = list(error.absolute_path)
    if error.validator == "minItems" and path and path[-1] == "sources":
        return True
    return bool(error.validator == "required" and "'sources'" in error.message)


def _contradiction_draft(
    vault: Vault,
    target: Card,
    staged: StagedDraft,
    pair: ConflictPair,
    taken: set[str],
) -> StagedDraft | None:
    existing_claim = next(
        (c for c in target.meta.claims if c.id == pair.existing_claim), None
    )
    draft_claims: list[dict[str, Any]] = list(staged.meta.get("claims") or [])
    draft_claim = next((c for c in draft_claims if c.get("id") == pair.draft_claim), None)
    if existing_claim is None or draft_claim is None:
        return None
    topic = pair.topic or target.meta.name
    draft_id = assign_draft_id("contradiction", f"{target.meta.name} {topic}", taken)
    meta: dict[str, Any] = {
        "id": draft_id,
        "kind": "contradiction",
        "name": f"矛盾：{target.meta.name}（{topic}）"[:120],
        "summary": f"两个源对「{topic}」给出不相容论断，待人工裁决。"[:80],
        "claims": [
            {
                "id": "c1",
                "text": existing_claim.text,
                "sources": [
                    {"source": s.source, "loc": s.loc, "span_sha256": s.span_sha256}
                    for s in existing_claim.sources
                ],
                "status": "contested",
            },
            {
                "id": "c2",
                "text": str(draft_claim.get("text", "")),
                "sources": list(draft_claim.get("sources") or []),
                "status": "contested",
            },
        ],
        "version": 1,
        "status": "contested",
        "schema_version": "0.1",
    }
    body = (
        "## 双方\n\n"
        f"- 既有：{target.meta.id}#{pair.existing_claim}\n"
        f"- 新证：{staged.draft_id}#{pair.draft_claim}（源 {staged.source_id}）\n\n"
        "## 裁决\n\n未裁决。编译器绝不自动裁决；由人工在 CLI 关闭（M2 `vault resolve`）。\n"
    )
    return StagedDraft(
        draft_id=draft_id,
        meta=meta,
        body=body,
        source_id=staged.source_id,
        contradiction=True,
    )


def _machine_gate(
    vault_root: Path, staged: list[StagedDraft]
) -> tuple[dict[str, list[tuple[str, str]]], dict[str, list[str]]]:
    """⑥ validate：schema 验形 + lint 验义，跑在「基库 + 草案」虚拟视图上。"""
    rejected: dict[str, list[tuple[str, str]]] = {}
    warnings: dict[str, list[str]] = {}
    vault = Vault.load(vault_root)
    validator = lint_mod.card_validator()

    for sd in staged:
        payload = frontmatter.jsonable(sd.meta)
        schema_errors = list(validator.iter_errors(payload))
        if schema_errors:
            findings = []
            for err in schema_errors:
                rule = "L-PROV-1" if _is_missing_sources(err) else "SCHEMA"
                where = "/".join(str(p) for p in err.absolute_path) or "<frontmatter>"
                findings.append((rule, f"{where}: {err.message}"))
            rejected[sd.draft_id] = findings
            continue
        meta_obj = CardMeta.model_validate(sd.meta)
        vault.cards[sd.draft_id] = Card(meta=meta_obj, body=sd.body, path=sd.relpath)

    prefix = "_review/drafts/"
    for finding in lint_mod.lint_vault(vault):
        if not finding.path.startswith(prefix):
            continue
        draft_id = finding.path.removeprefix(prefix).removesuffix(".md")
        if finding.level == lint_mod.LEVEL_ERROR:
            rejected.setdefault(draft_id, []).append((finding.rule, finding.message))
        else:
            warnings.setdefault(draft_id, []).append(f"{finding.rule}: {finding.message}")
    return rejected, warnings


def compile_vault(
    vault_root: Path,
    provider: LlmProvider,
    *,
    source_ids: list[str] | None = None,
    review_rate_override: float | None = None,
) -> CompileReport:
    vault = Vault.load(vault_root)
    settings = vault.config.review
    run_id = next_run_id(vault_root)
    propose_prompt = load_prompt("propose")
    contradict_prompt = load_prompt("contradict")
    actor = f"compiler@{__version__}"

    targets = sorted(source_ids) if source_ids else sorted(vault.sources)
    unknown = [s for s in targets if s not in vault.sources]
    if unknown:
        raise ValueError(f"源未登记：{', '.join(unknown)}（先 vault ingest）")

    report = CompileReport(run_id=run_id, sources=list(targets))
    pack = _merged_pack(vault)
    digests = [
        CardDigest(
            id=c.meta.id,
            kind=c.meta.kind,
            name=c.meta.name,
            aliases=list(c.meta.aliases),
            summary=c.meta.summary,
        )
        for c in vault.cards.values()
    ]
    alias_map = _alias_map(vault)
    queue = load_queue(vault_root)
    taken: set[str] = set(vault.cards) | {e.draft_id for e in queue}

    # ② propose → ③ merge → ④ interlink → ⑤ contradict
    staged: list[StagedDraft] = []
    enabled_predicates = vault.enabled_predicates()
    for source_id in targets:
        derivatives = _read_derivatives(vault_root, source_id)
        if not derivatives:
            report.skipped_sources.append(source_id)
            continue
        response = provider.propose(
            ProposeRequest(
                source_id=source_id,
                derivatives=derivatives,
                pack=pack,
                existing=digests,
                prompt=propose_prompt,
            )
        )
        report.usage.add(response.usage)
        for draft in response.drafts:
            report.proposed += 1
            kept, dropped = [], []
            for link in draft.links:
                if link.predicate in enabled_predicates and link.to in vault.cards:
                    kept.append(link)
                else:
                    dropped.append(f"{link.predicate}->{link.to}")
            draft.links = kept

            merge_into: str | None = None
            for alias in [draft.name, *draft.aliases]:
                hit = alias_map.get(alias.casefold())
                if hit:
                    merge_into = hit
                    break

            draft_id = assign_draft_id(draft.kind, draft.name, taken)
            taken.add(draft_id)
            sd = StagedDraft(
                draft_id=draft_id,
                meta=draft_to_meta(vault, draft, draft_id),
                body=draft.body,
                source_id=source_id,
                merge_into=merge_into,
                dropped_links=dropped,
            )
            staged.append(sd)
            if dropped:
                report.dropped_links[draft_id] = dropped
            if merge_into:
                report.merge_candidates[draft_id] = merge_into
                target = vault.cards[merge_into]
                if draft.claims and target.meta.claims:
                    decision = provider.contradict_judge(
                        ContradictRequest(
                            existing_id=merge_into,
                            existing_claims=[(c.id, c.text) for c in target.meta.claims],
                            draft_claims=[
                                (str(c.get("id")), str(c.get("text", "")))
                                for c in sd.meta.get("claims", [])
                            ],
                            prompt=contradict_prompt,
                        )
                    )
                    report.usage.add(decision.usage)
                    for conflict_pair in decision.conflicts:
                        contra = _contradiction_draft(vault, target, sd, conflict_pair, taken)
                        if contra is not None:
                            taken.add(contra.draft_id)
                            staged.append(contra)
                            report.contradictions.append(contra.draft_id)

    # 草案落盘（机器闸靠文件跑同一套 lint）
    for sd in staged:
        path = vault_root / sd.relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        frontmatter.save_file(path, frontmatter.Document(meta=sd.meta, body=sd.body))

    # ⑥ validate 机器闸
    rejected_map, warnings_map = _machine_gate(vault_root, staged)
    survivors: list[StagedDraft] = []
    for sd in staged:
        if sd.draft_id in rejected_map:
            findings = rejected_map[sd.draft_id]
            src = vault_root / sd.relpath
            dest = rejected_file(vault_root, sd.draft_id)
            dest.parent.mkdir(parents=True, exist_ok=True)
            src.replace(dest)
            queue.append(
                QueueEntry(
                    draft_id=sd.draft_id,
                    run_id=run_id,
                    source=sd.source_id,
                    status="machine_rejected",
                    kind=str(sd.meta.get("kind", "")),
                    name=str(sd.meta.get("name", "")),
                    merge_into=sd.merge_into,
                    contradiction=sd.contradiction,
                    rules=[rule for rule, _ in findings],
                    messages=[msg for _, msg in findings],
                    dropped_links=sd.dropped_links,
                )
            )
            report.machine_rejected[sd.draft_id] = [f"{rule}: {msg}" for rule, msg in findings]
        else:
            survivors.append(sd)
    report.warnings = warnings_map

    # ⑦ review 抽样闸（按源分批；并卡候选与矛盾卡一律送审）
    by_source: dict[str, list[StagedDraft]] = {}
    for sd in survivors:
        by_source.setdefault(sd.source_id, []).append(sd)
    history_all = load_history(vault_root)
    for source_id in targets:
        group = by_source.get(source_id, [])
        machine_rejected_count = sum(
            1 for sd in staged if sd.source_id == source_id and sd.draft_id in rejected_map
        )
        if not group and machine_rejected_count == 0:
            continue
        rate = (
            review_rate_override
            if review_rate_override is not None
            else review_rate(history_all.get(source_id, []), settings)
        )
        forced = [sd for sd in group if sd.merge_into or sd.contradiction]
        optional = sorted(
            (sd for sd in group if not (sd.merge_into or sd.contradiction)),
            key=lambda sd: sd.draft_id,
        )
        keep_n = sample_size(rate, len(optional))
        to_review = forced + optional[:keep_n]
        to_auto = optional[keep_n:]

        for sd in to_review:
            queue.append(
                QueueEntry(
                    draft_id=sd.draft_id,
                    run_id=run_id,
                    source=sd.source_id,
                    status="pending",
                    kind=str(sd.meta.get("kind", "")),
                    name=str(sd.meta.get("name", "")),
                    merge_into=sd.merge_into,
                    contradiction=sd.contradiction,
                    warnings=warnings_map.get(sd.draft_id, []),
                    dropped_links=sd.dropped_links,
                )
            )
            report.pending.append(sd.draft_id)
        for sd in to_auto:
            dest_rel = promote_draft(vault_root, sd.draft_id, merge_into=None, actor=actor)
            queue.append(
                QueueEntry(
                    draft_id=sd.draft_id,
                    run_id=run_id,
                    source=sd.source_id,
                    status="auto_approved",
                    kind=str(sd.meta.get("kind", "")),
                    name=str(sd.meta.get("name", "")),
                    warnings=warnings_map.get(sd.draft_id, []),
                    dropped_links=sd.dropped_links,
                    promoted_to=dest_rel,
                    decided_by=actor,
                )
            )
            report.auto_approved.append(sd.draft_id)
        start_batch(
            vault_root,
            source_id,
            run_id,
            sent_review=len(to_review),
            auto_approved=len(to_auto),
            machine_rejected=machine_rejected_count,
        )

    save_queue(vault_root, queue)

    manifest: dict[str, Any] = {
        "run_id": run_id,
        "inputs": {
            "sources": [
                {"id": s, "revision": vault.sources[s].revision} for s in targets
            ]
        },
        "model": provider.describe(),
        "prompts": {
            "propose": f"{propose_prompt.id}#sha256:{propose_prompt.sha256[:12]}",
            "contradict": f"{contradict_prompt.id}#sha256:{contradict_prompt.sha256[:12]}",
        },
        "pack_versions": [f"{p.name}@{p.version}" for p in vault.packs.values()],
        "cost": {
            "input_tokens": report.usage.input_tokens,
            "output_tokens": report.usage.output_tokens,
        },
        "outputs": {
            "proposed": report.proposed,
            "pending_review": len(report.pending),
            "auto_approved": len(report.auto_approved),
            "machine_rejected": len(report.machine_rejected),
            "contradictions": len(report.contradictions),
            "injection_flagged": sum(
                1 for sd in staged if sd.meta.get("injection_risk") is True
            ),
            "skipped_sources": report.skipped_sources,
        },
    }
    write_manifest(vault_root, run_id, manifest)
    append_audit(
        vault_root,
        "compile_run",
        actor,
        {"run_id": run_id, "sources": targets, "outputs": manifest["outputs"]},
    )
    return report
