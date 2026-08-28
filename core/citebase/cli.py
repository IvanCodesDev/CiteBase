"""vault 命令行。

读侧：search / read / follow / quote（与 MCP 四工具同一实现，行为差异视为 bug；
M5 起支持 ``--scope`` 联邦检索与 ``dep::card`` 跨库引用）。
治理与工程侧（只在 CLI，永不进 MCP）：lint / index / eval / stats / hash / fix-hashes（M0），
ingest / compile / review（M1 编译循环），init / drift / audit / resolve（M2 治理），
backflow / contrib / gaps 与 eval --faithfulness（M3 证据回流与评测），
export site|json / bench 与 index 的 sqlite 加速缓存（M4 加速与导出），
deps sync|status（M5 联邦：锁定、过期与断链检查）。
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path
from typing import Any

from citebase import __version__, evalrun, frontmatter, retrieve, spanhash
from citebase import index as index_mod
from citebase import lint as lint_mod
from citebase.model import SourceSpan
from citebase.vault import Vault


def _force_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]


def _load_vault(path: str) -> Vault:
    return Vault.load(Path(path))


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


# ---------- 子命令 ----------


def cmd_lint(args: argparse.Namespace) -> int:
    vault = _load_vault(args.vault)
    findings = lint_mod.lint_vault(vault)
    errors = [f for f in findings if f.level == lint_mod.LEVEL_ERROR]
    warns = [f for f in findings if f.level == lint_mod.LEVEL_WARN]
    for f in findings:
        print(f.format())
    print(
        f"lint: {len(vault.cards)} 卡 {len(vault.sources)} 源 → "
        f"{len(errors)} error, {len(warns)} warn"
    )
    return 1 if errors else 0


def cmd_index(args: argparse.Namespace) -> int:
    vault = _load_vault(args.vault)
    idx = index_mod.build(vault)
    if args.check:
        problems = index_mod.check(vault.root, idx)
        if problems:
            for p in problems:
                print(f"ERROR L-IDX-1 {p}")
            return 1
        print(f"index --check: 一致（{idx['meta']['cards']} 卡）")
        return 0
    written = index_mod.write(vault.root, idx)
    print(f"index: 写入 {index_mod.INDEX_DIR}/ {len(written)} 个文件（{idx['meta']['cards']} 卡）")
    if vault.config.index_backend == "sqlite":
        from citebase.backends import write_sqlite

        path = write_sqlite(vault.root, idx)
        print(f"index: 重建 sqlite 加速缓存 {path.relative_to(vault.root).as_posix()}"
              "（生成物不入库）")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    from citebase.backends import select_backend
    from citebase.retrievelog import log_search

    vault = _load_vault(args.vault)
    scope: list[str] | None = args.scope or None
    if scope and scope != ["self"]:
        return _search_scoped(args, scope)
    result = retrieve.search(
        select_backend(vault),
        args.query,
        kind=args.kind,
        tags=args.tag or None,
        as_of=retrieve.parse_as_of(args.as_of),
        limit=args.limit,
        include_suspect=args.include_suspect,
    )
    log_search(vault.root, args.query, result, surface="cli")
    if args.json:
        _print_json(result.to_dict())
        return 0
    if not result.hit:
        print("未命中")
        print(f"  已尝试：{' → '.join(result.tried)}")
        print(f"  建议：{result.suggestion}")
        return 0
    for i, h in enumerate(result.hits, 1):
        status_note = "" if h.status == "active" else f" [{h.status}]"
        print(f"{i:2}. {h.id}  {h.name}{status_note}  ({h.kind}, {h.jump}, {h.score:.2f})")
        print(f"    {h.summary}")
        if h.claim:
            print(f"    论断：{h.claim}")
    return 0


def _search_scoped(args: argparse.Namespace, scope: list[str]) -> int:
    """联邦检索（M5）：逐库同一条漏斗，命中标注来源库。"""
    from citebase.federation import FederationError, search_scoped

    try:
        result = search_scoped(
            Path(args.vault),
            args.query,
            scope=scope,
            kind=args.kind,
            tags=args.tag or None,
            as_of_text=args.as_of,
            limit=args.limit,
            include_suspect=args.include_suspect,
        )
    except FederationError as e:
        print(f"错误:{e}")
        return 1
    if args.json:
        _print_json(result)
        return 0
    if not result["hit"]:
        print("未命中（联邦范围：" + ", ".join(scope) + "）")
        print(f"  建议：{result.get('suggestion', '')}")
        return 0
    for i, h in enumerate(result["hits"], 1):
        marker = "" if h["vault"] == "self" else f" ←{h['vault']}"
        print(
            f"{i:2}. {h['id']}  {h['name']}{marker}  "
            f"({h['kind']}, {h['jump']}, {h['score']:.2f})"
        )
        print(f"    {h['summary']}")
    return 0


def cmd_read(args: argparse.Namespace) -> int:
    vault = _load_vault(args.vault)
    if "::" in args.card_id:
        from citebase.federation import FederationError, federated_read

        try:
            card = federated_read(vault.root, args.card_id)
        except FederationError as e:
            print(f"错误:{e}")
            return 1
    else:
        card = retrieve.read_card(vault, args.card_id)
    if card is None:
        print(f"卡片不存在：{args.card_id}")
        return 1
    if args.json:
        payload = card.meta.model_dump(mode="json")
        payload["body"] = card.body
        payload["path"] = card.path
        _print_json(payload)
        return 0
    m = card.meta
    print(f"# {m.name}（{m.id}）")
    print(f"kind={m.kind} status={m.status} version={m.version} path={card.path}")
    print(f"summary: {m.summary}")
    if m.aliases:
        print(f"aliases: {', '.join(m.aliases)}")
    if m.tags:
        print(f"tags: {', '.join(m.tags)}")
    if m.claims:
        print("claims:")
        for c in m.claims:
            print(f"  [{c.id}] {c.text}")
            for s in c.sources:
                print(f"      源 {s.source} @ {s.loc}")
    if m.links:
        print("links:")
        for ln in m.links:
            print(f"  -{ln.predicate}-> {ln.to}")
    print("\n" + card.body.strip())
    return 0


def cmd_follow(args: argparse.Namespace) -> int:
    from citebase.backends import select_backend

    vault = _load_vault(args.vault)
    if "::" in args.card_id:
        from citebase.federation import FederationError, federated_follow

        try:
            edges = federated_follow(vault.root, args.card_id, predicate=args.predicate)
        except FederationError as err:
            print(f"错误:{err}")
            return 1
    else:
        edges = retrieve.follow(
            select_backend(vault), args.card_id, predicate=args.predicate
        )
    if edges is None:
        print(f"卡片不存在：{args.card_id}")
        return 1
    if args.json:
        _print_json(edges)
        return 0
    print(f"{args.card_id} 的邻居：")
    for direction, key in (("出边", "out"), ("入边", "in")):
        for e in edges[key]:
            arrow = f"-{e['predicate']}->" if key == "out" else f"<-{e['predicate']}-"
            print(f"  {direction} {arrow} {e['card']}  {e['name']}")
            if e["summary"]:
                print(f"       {e['summary']}")
    if not edges["out"] and not edges["in"]:
        print("  （无链接）")
    return 0


def cmd_quote(args: argparse.Namespace) -> int:
    vault = _load_vault(args.vault)
    if "::" in args.ref:
        from citebase.federation import FederationError, federated_quote

        try:
            result = federated_quote(vault.root, args.ref)
        except FederationError as e:
            print(f"错误:{e}")
            return 1
    else:
        result = retrieve.quote(vault, args.ref)
    if result is None:
        print(f"引用不存在：{args.ref}（格式：<card-id>#<claim-id>）")
        return 1
    if args.json:
        _print_json(result.to_dict())
        return 0
    print(f"论断 {result.card_id}#{result.claim_id}（{result.card_name}，status={result.status}）")
    print(f"  {result.text}")
    for s in result.spans:
        mark = "已验证" if s.verified else "验证失败"
        print(f"  源 {s.source} @ {s.loc} [{mark}] license={s.license}")
        if s.error:
            print(f"    错误：{s.error}")
        elif s.text is not None:
            excerpt = s.text if len(s.text) <= 200 else s.text[:200] + "…"
            print(f"    原文：{excerpt}")
    return 0 if all(s.verified for s in result.spans) else 1


def cmd_hash(args: argparse.Namespace) -> int:
    vault = _load_vault(args.vault)
    span = SourceSpan(source=args.source_id, loc=args.loc, span_sha256="0" * 64)
    try:
        print(spanhash.compute(vault, span))
    except spanhash.SpanError as e:
        print(f"错误：{e}")
        return 1
    return 0


def cmd_fix_hashes(args: argparse.Namespace) -> int:
    """手写卡片的作者工具：重算全部 span 哈希；--write 时就地更新 frontmatter。"""
    vault = _load_vault(args.vault)
    total = fixed = failed = 0
    for card in vault.cards.values():
        file = vault.root / card.path
        doc = frontmatter.load_file(file)
        changed = False
        for claim in doc.meta.get("claims", []) or []:
            for span_raw in claim.get("sources", []) or []:
                total += 1
                span = SourceSpan(
                    source=span_raw["source"],
                    loc=span_raw["loc"],
                    span_sha256=span_raw.get("span_sha256", ""),
                )
                try:
                    actual = spanhash.compute(vault, span)
                except spanhash.SpanError as e:
                    failed += 1
                    print(f"无法定位 {card.path} {claim.get('id')}: {e}")
                    continue
                if actual != span.span_sha256:
                    fixed += 1
                    print(
                        f"{'更新' if args.write else '需更新'} {card.path} "
                        f"{claim.get('id')}: {span.loc}"
                    )
                    if args.write:
                        span_raw["span_sha256"] = actual
                        changed = True
        if changed:
            frontmatter.save_file(file, doc)
    print(f"fix-hashes: 共 {total} 个 span，{fixed} 个不一致，{failed} 个定位失败")
    if args.write:
        return 1 if failed else 0
    return 1 if (fixed or failed) else 0


def cmd_eval(args: argparse.Namespace) -> int:
    vault = _load_vault(args.vault)
    if args.faithfulness:
        return _eval_faithfulness(vault, args)
    golden_path = Path(args.golden) if args.golden else vault.root / "evals" / "golden.yaml"
    if not golden_path.is_file():
        print(f"golden 文件不存在：{golden_path}")
        return 1
    cases = evalrun.load_golden(golden_path)
    idx = index_mod.build(vault)
    report = evalrun.run(idx, cases, limit=args.limit)
    if args.json:
        _print_json(report.to_dict())
    else:
        print(
            f"eval: {report.total} 问 → 命中率 {report.hit_rate:.2%}"
            f"，首位命中率 {report.first_hit_rate:.2%}，rank 违约 {report.rank_failures}"
        )
        for m in report.misses:
            print(f"  未达标：{m['q']} —— {m['why']}；got={m['got']}")
    ok = True
    if args.min_hit is not None and report.hit_rate < args.min_hit:
        print(f"低于命中率红线 {args.min_hit}")
        ok = False
    if args.min_first is not None and report.first_hit_rate < args.min_first:
        print(f"低于首位命中率红线 {args.min_first}")
        ok = False
    return 0 if ok else 1


def _eval_faithfulness(vault: Vault, args: argparse.Namespace) -> int:
    """忠实度抽查（M3）：哈希通道自动判定；语义核对清单交人工（--export 导出）。"""
    report = evalrun.run_faithfulness(vault, sample=args.sample, seed=args.seed)
    if args.export:
        Path(args.export).write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
            newline="\n",
        )
    if args.json:
        _print_json(report.to_dict())
    else:
        print(
            f"faithfulness: 论断总体 {report.population}，抽样 {report.sampled}"
            f"，机器判不忠实 {len(report.unfaithful)}（{report.unfaithful_rate:.2%}）"
        )
        for item in report.unfaithful:
            print(f"  不忠实：{item['ref']} —— {item['why']}")
        if args.export:
            print(f"  语义核对清单已导出：{args.export}（人工核对语义忠实性）")
    if report.unfaithful_rate > args.max_unfaithful:
        print(f"超过不忠实率红线 {args.max_unfaithful:.2%}")
        return 1
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    vault = _load_vault(args.vault)
    by_kind: dict[str, int] = {}
    by_status: dict[str, int] = {}
    claims = links = 0
    for card in vault.cards.values():
        by_kind[card.meta.kind] = by_kind.get(card.meta.kind, 0) + 1
        by_status[card.meta.status] = by_status.get(card.meta.status, 0) + 1
        claims += len(card.meta.claims)
        links += len(card.meta.links)
    data = {
        "vault": vault.config.name,
        "cards": len(vault.cards),
        "sources": len(vault.sources),
        "claims": claims,
        "links": links,
        "by_kind": dict(sorted(by_kind.items())),
        "by_status": dict(sorted(by_status.items())),
        "packs": sorted(vault.packs),
        "load_errors": len(vault.load_errors),
    }
    if args.json:
        _print_json(data)
    else:
        print(f"vault: {data['vault']}")
        print(
            f"cards={data['cards']} sources={data['sources']} "
            f"claims={data['claims']} links={data['links']}"
        )
        print(f"by_kind: {data['by_kind']}")
        print(f"by_status: {data['by_status']}")
        print(f"packs: {data['packs']} load_errors: {data['load_errors']}")
    return 0


# ---------- M1：编译循环 ----------


def cmd_ingest(args: argparse.Namespace) -> int:
    from citebase.adapters import adapter_for_path
    from citebase.ingest import ingest

    vault_root = Path(args.vault)
    if not (vault_root / "vault.yaml").is_file():
        print(f"错误:不是一个 vault：缺少 {vault_root / 'vault.yaml'}")
        return 2
    try:
        result = ingest(
            vault_root,
            adapter_for_path(Path(args.path)),
            source_id=args.id,
            license_=args.license,
            force=args.force,
        )
    except (ValueError, FileNotFoundError) as e:
        print(f"错误:{e}")
        return 1
    print(f"ingest: {result.meta.id} ← {result.meta.uri}")
    print(f"  adapter={result.meta.adapter} revision={result.meta.revision}")
    for rel in result.derivatives:
        print(f"  派生物 {rel}")
    for rel in result.skipped:
        print(f"  跳过（无抽取器可处理）：{rel}")
    return 0


def cmd_compile(args: argparse.Namespace) -> int:
    from citebase.compiler import compile_vault, load_scripted
    from citebase.compiler.openai_compat import LlmUnavailableError, OpenAICompatProvider
    from citebase.ports import LlmProvider

    vault_root = Path(args.vault)
    provider: LlmProvider
    if args.scripted:
        provider = load_scripted(Path(args.scripted))
    else:
        try:
            provider = OpenAICompatProvider.from_settings(Vault.load(vault_root).config.llm)
        except LlmUnavailableError as e:
            print(f"跳过编译：{e}")
            return 1
    try:
        report = compile_vault(
            vault_root,
            provider,
            source_ids=args.source or None,
            review_rate_override=args.review_rate,
        )
    except ValueError as e:
        print(f"错误:{e}")
        return 1
    print(
        f"compile {report.run_id}: 提议 {report.proposed} 张 → "
        f"送审 {len(report.pending)}，自动入库 {len(report.auto_approved)}，"
        f"机器闸拒绝 {len(report.machine_rejected)}，矛盾卡 {len(report.contradictions)}"
    )
    for source_id in report.skipped_sources:
        print(f"  跳过（无派生物）：{source_id}")
    for draft_id, reasons in report.machine_rejected.items():
        print(f"  拒 {draft_id}")
        for reason in reasons:
            print(f"    {reason}")
    for draft_id in report.pending:
        marks = []
        if draft_id in report.merge_candidates:
            marks.append(f"并卡候选→{report.merge_candidates[draft_id]}")
        if draft_id in report.contradictions:
            marks.append("矛盾卡")
        suffix = f"（{'；'.join(marks)}）" if marks else ""
        print(f"  待审 {draft_id}{suffix}")
    for draft_id in report.auto_approved:
        print(f"  已入库 {draft_id}")
    print(
        f"  tokens: in={report.usage.input_tokens} out={report.usage.output_tokens}"
        f"（详见 _compile_log/{report.run_id}.yaml）"
    )
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    from citebase.compiler import review as review_mod

    vault_root = Path(args.vault)
    action = args.action
    if action == "list":
        entries = review_mod.load_queue(vault_root)
        if args.status:
            entries = [e for e in entries if e.status == args.status]
        if not entries:
            print("审核队列为空")
            return 0
        for e in entries:
            marks = []
            if e.merge_into:
                marks.append(f"并卡候选→{e.merge_into}")
            if e.contradiction:
                marks.append("矛盾卡")
            if e.rules:
                marks.append(",".join(dict.fromkeys(e.rules)))
            suffix = f"  [{'；'.join(marks)}]" if marks else ""
            print(f"{e.status:16} {e.draft_id}  ← {e.source} @ {e.run_id}{suffix}")
        return 0
    if action == "show":
        entries = review_mod.load_queue(vault_root)
        try:
            entry = review_mod.get_entry(entries, args.draft_id)
        except KeyError as e:
            print(f"错误:{e}")
            return 1
        print(f"draft: {entry.draft_id}（{entry.kind} · {entry.name}）")
        print(f"status: {entry.status}  source: {entry.source}  run: {entry.run_id}")
        if entry.merge_into:
            print(f"并卡候选 → {entry.merge_into}")
        if entry.contradiction:
            print("类型：矛盾卡（绝不自动裁决）")
        for w in entry.warnings:
            print(f"warn: {w}")
        for m in entry.messages:
            print(f"拒因: {m}")
        if entry.dropped_links:
            print(f"被丢弃的链接建议: {', '.join(entry.dropped_links)}")
        for candidate in (
            review_mod.draft_file(vault_root, entry.draft_id),
            review_mod.rejected_file(vault_root, entry.draft_id),
        ):
            if candidate.is_file():
                print("---")
                print(candidate.read_text(encoding="utf-8"))
                break
        else:
            if entry.promoted_to:
                print(f"已入库：{entry.promoted_to}")
        return 0
    if action == "approve":
        try:
            dest = review_mod.approve(
                vault_root,
                args.draft_id,
                merge_into=args.merge_into,
                force_new=args.force_new,
                actor=args.by,
            )
        except (ValueError, KeyError, FileNotFoundError, FileExistsError) as e:
            print(f"错误:{e}")
            return 1
        print(f"approve: {args.draft_id} → {dest}")
        return 0
    if action == "reject":
        try:
            review_mod.reject(vault_root, args.draft_id, reason=args.reason, actor=args.by)
        except (ValueError, KeyError) as e:
            print(f"错误:{e}")
            return 1
        print(f"reject: {args.draft_id}（原因已留痕）")
        return 0
    print(f"错误:未知动作 {action}")
    return 2


# ---------- M2：治理动词 ----------


def cmd_init(args: argparse.Namespace) -> int:
    from citebase.scaffold import init_vault

    try:
        created = init_vault(Path(args.path), name=args.name)
    except ValueError as e:
        print(f"错误:{e}")
        return 1
    print(f"init: {Path(args.path).resolve()}")
    for rel in created:
        print(f"  + {rel}")
    print("下一步：vault ingest <文件> 登记源，vault compile 编译；CI 模板已生成。")
    return 0


def cmd_drift(args: argparse.Namespace) -> int:
    from citebase.drift import run_drift

    report = run_drift(Path(args.vault), apply=not args.report)
    for signal in report.signals:
        where = signal.source or f"{signal.card_id}#{signal.claim_id}"
        print(f"  {signal.kind:18} {where}: {signal.detail}")
    mode = "已应用" if report.applied else "仅报告"
    print(
        f"drift: 信号 {len(report.signals)} 条，"
        f"置 suspect {len(report.marked_suspect)} 张（{mode}），"
        f"过期论断 {len(report.expired_claims)} 条"
    )
    projected = report.suspect_cards + (0 if report.applied else len(report.marked_suspect))
    ratio = projected / report.total_cards if report.total_cards else 0.0
    print(f"  suspect 占比：{ratio:.1%}（{projected}/{report.total_cards}）")
    if args.warn_threshold is not None and ratio > args.warn_threshold:
        print(
            f"  警告：suspect 占比超过阈值 {args.warn_threshold:.1%}，"
            "请尽快复核（vault audit list）"
        )
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    from citebase import govern

    vault_root = Path(args.vault)
    if args.action == "list":
        suspects = govern.list_suspects(vault_root)
        if not suspects:
            print("复核队列为空：没有 suspect 卡")
            return 0
        for card in suspects:
            print(f"suspect {card.meta.id}  {card.meta.name}  ({card.path})")
        print(f"共 {len(suspects)} 张；用 vault audit review <card-id> --outcome pass|retire 复核")
        return 0
    if args.action == "review":
        try:
            new_status = govern.review_suspect(
                vault_root,
                args.card_id,
                outcome=args.outcome,
                note=args.note,
                actor=args.by,
            )
        except (KeyError, ValueError) as e:
            print(f"错误:{e}")
            return 1
        print(f"audit review: {args.card_id} → {new_status}（已留痕 _audit）")
        return 0
    print(f"错误:未知动作 {args.action}")
    return 2


def cmd_resolve(args: argparse.Namespace) -> int:
    from citebase import govern

    try:
        govern.resolve_contradiction(
            Path(args.vault),
            args.card_id,
            winner=args.winner,
            note=args.note,
            actor=args.by,
        )
    except (KeyError, ValueError) as e:
        print(f"错误:{e}")
        return 1
    print(f"resolve: {args.card_id} 裁决完成，胜方 {args.winner}（矛盾卡退役，历史可查）")
    return 0


# ---------- M3：证据回流与评测 ----------


def cmd_backflow(args: argparse.Namespace) -> int:
    from citebase.compiler.backflow import run_backflow

    try:
        report = run_backflow(
            Path(args.vault), min_cluster=args.min_cluster, kind=args.kind
        )
    except (ValueError, FileNotFoundError) as e:
        print(f"错误:{e}")
        return 1
    print(
        f"backflow {report.run_id}: 事件 {report.events_total} 条"
        f"（新登记源 {report.new_sources}，坏行 {len(report.invalid_lines)}"
        f"，重复 {len(report.duplicates)}，无类别失败 {report.uncategorized}）"
    )
    for line in report.invalid_lines:
        print(f"  坏行 {line['file']}:{line['line']} —— {line['error']}")
    for category, count in sorted(report.clusters.items()):
        note = ""
        if category in report.below_threshold:
            note = "（未达提卡阈值）"
        elif category in report.already_covered:
            note = f"（已有承接：{report.already_covered[category]}）"
        print(f"  聚类「{category}」×{count}{note}")
    for draft_id in report.pending:
        print(f"  待审草案 {draft_id}（vault review show {draft_id}）")
    for draft_id, reasons in report.machine_rejected.items():
        print(f"  机器闸拒绝 {draft_id}：{'；'.join(reasons)}")
    if report.injection_flagged:
        print(f"  注入旗标：{report.injection_flagged} 张草案带 injection_risk")
    if report.pending:
        print(f"共 {len(report.pending)} 张草案送审；回流不豁免治理，请人工复核后入库。")
    return 0


def cmd_contrib(args: argparse.Namespace) -> int:
    from citebase.contrib import run_contrib

    report = run_contrib(
        Path(args.vault),
        min_events=args.min_events,
        apply_negative=args.apply_negative,
        actor=args.by,
    )
    if args.json:
        _print_json(report.to_dict())
        return 0
    print(
        f"contrib: 事件 {report.events_total} 条，总体成功率 "
        f"{report.overall_success_rate:.2%}（榜单按 lift 降序，可复算）"
    )
    for c in report.cards:
        gone = "" if c.exists else " [卡不在库内]"
        print(
            f"  {c.card_id}{gone}  被用 {c.consulted} 次  "
            f"成功率 {c.success_rate:.2%} vs 基线 {c.baseline_rate:.2%}"
            f"  lift {c.lift:+.2%}"
        )
    if report.negative:
        print(f"  负贡献候选（样本 ≥{args.min_events}）：{', '.join(report.negative)}")
        if report.applied_suspect:
            print(f"  已置 suspect：{', '.join(report.applied_suspect)}（vault audit list 复核）")
        else:
            print("  用 --apply-negative 置 suspect 进复核队列（机器只产信号，人平反）")
    return 0


def cmd_gaps(args: argparse.Namespace) -> int:
    from citebase.retrievelog import gap_report

    vault = _load_vault(args.vault)
    golden_misses: list[dict[str, Any]] = []
    golden_path = vault.root / "evals" / "golden.yaml"
    if golden_path.is_file():
        cases = evalrun.load_golden(golden_path)
        if cases:
            idx = index_mod.build(vault)
            golden_misses = evalrun.run(idx, cases).misses
    gaps = gap_report(vault.root, golden_misses=golden_misses, min_count=args.min_count)
    if args.json:
        _print_json(gaps)
        return 0
    if not gaps:
        print("gaps: 无缺口记录（检索日志无未命中，golden 全命中）")
        return 0
    print(f"gaps: {len(gaps)} 个知识缺口（按频次降序，即建卡待办）")
    for g in gaps:
        print(f"  ×{g['count']}  {g['query']}  （来源：{', '.join(g['origins'])}）")
    return 0


# ---------- M5：Vault 联邦 ----------


def cmd_deps(args: argparse.Namespace) -> int:
    from citebase.federation import FederationError, deps_status, deps_sync

    vault_root = Path(args.vault)
    if not (vault_root / "vault.yaml").is_file():
        print(f"错误:不是一个 vault：缺少 {vault_root / 'vault.yaml'}")
        return 2
    if args.action == "sync":
        try:
            report = deps_sync(vault_root)
        except (FederationError, FileNotFoundError) as e:
            print(f"错误:{e}")
            return 1
        if not report.synced:
            print("deps sync: vault.yaml 未声明任何依赖")
            return 0
        print(f"deps sync: 已锁定 {len(report.synced)} 个依赖 → vault.lock")
        for impact in report.impacts:
            print(
                f"  {impact.dep_id}: 上游新增 {len(impact.added)} / "
                f"变更 {len(impact.changed)} / 移除 {len(impact.removed)}"
            )
            for cid in impact.changed:
                print(f"    变更 {cid}")
            for cid in impact.removed:
                print(f"    移除 {cid}")
            if impact.affected_local:
                print(f"    影响本库卡：{', '.join(impact.affected_local)}")
        return 0
    if args.action == "status":
        try:
            status = deps_status(vault_root)
        except (FederationError, FileNotFoundError) as e:
            print(f"错误:{e}")
            return 1
        if not status.deps:
            print("deps status: 未声明任何依赖（联邦是可选层）")
            return 0
        for dep in status.deps:
            note = f" —— {dep.detail}" if dep.detail else ""
            print(f"  {dep.dep_id}: {dep.state}{note}")
            for ref in dep.broken_refs:
                print(f"    断链 {ref}")
            for ref in dep.terminal_refs:
                print(f"    终态引用 {ref}")
        if status.clean:
            print("deps status: 全部依赖锁定一致")
            return 0
        print("deps status: 存在待处理项（needs_sync/stale/断链/终态引用）")
        return 1
    print(f"错误:未知动作 {args.action}")
    return 2


# ---------- M4：加速与导出 ----------


def cmd_export(args: argparse.Namespace) -> int:
    vault = _load_vault(args.vault)
    out = Path(args.out)
    if args.what == "json":
        from citebase.exporters import export_json

        snapshot = export_json(vault, out, include_hidden=args.include_hidden)
        stats = snapshot["stats"]
        print(
            f"export json: {out} （{stats['cards']} 卡，{stats['claims']} 论断，"
            f"{stats['links']} 链接）"
        )
        for warning in snapshot["license_warnings"]:
            print(
                f"  许可证警示：{warning['source']} license=unknown"
                f"（被引 {warning['cited_spans']} 处），对外发布前请核实"
            )
        return 0
    from citebase.exporters import export_site

    report = export_site(vault, out, include_hidden=args.include_hidden)
    print(f"export site: {out} （{report.cards} 卡，{len(report.files)} 个文件）")
    for warning in report.license_warnings:
        print(
            f"  许可证警示：{warning['source']} license=unknown"
            f"（被引 {warning['cited_spans']} 处），对外发布前请核实"
        )
    return 0


def cmd_bench(args: argparse.Namespace) -> int:
    import tempfile

    from citebase.bench import run_bench

    with tempfile.TemporaryDirectory(prefix="citebase-bench-") as tmp:
        report = run_bench(
            cards=args.cards, queries=args.queries, seed=args.seed, workdir=Path(tmp)
        )
    if args.json:
        _print_json(report.to_dict())
    else:
        print(
            f"bench: {report.cards} 卡合成库；索引重建 {report.build_index_ms:.0f}ms，"
            f"sqlite 缓存写入 {report.write_sqlite_ms:.0f}ms"
        )
        for r in report.results:
            print(
                f"  {r.backend:6} {r.queries} 查询 → P50 {r.p50_ms:.2f}ms  "
                f"P95 {r.p95_ms:.2f}ms  max {r.max_ms:.2f}ms  （启动 {r.setup_ms:.0f}ms）"
            )
    if args.max_p95 is not None:
        worst = max(r.p95_ms for r in report.results)
        if worst > args.max_p95:
            print(f"P95 {worst:.2f}ms 超过红线 {args.max_p95}ms")
            return 1
    return 0


# ---------- 入口 ----------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vault",
        description="Citebase：编译式知识库（M0：无 LLM 的 lint / 索引 / 检索）",
    )
    parser.add_argument("--version", action="version", version=f"citebase {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help_: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_)
        p.add_argument("--vault", default=".", help="vault 根目录（默认当前目录）")
        return p

    add("lint", "出处硬闸与结构规则检查").set_defaults(func=cmd_lint)

    p = add("index", "重建 _index/（--check 校验一致性，L-IDX-1）")
    p.add_argument("--check", action="store_true")
    p.set_defaults(func=cmd_index)

    p = add("search", "漏斗检索：精确 → BM25 → 图邻域")
    p.add_argument("query")
    p.add_argument("--kind")
    p.add_argument("--tag", action="append")
    p.add_argument("--as-of", dest="as_of", help="ISO 时间点，按时点过滤论断")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--include-suspect", action="store_true")
    p.add_argument(
        "--scope",
        action="append",
        help="联邦检索范围（可重复）：self 与已声明依赖 id；默认只搜本库",
    )
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_search)

    p = add("read", "读取完整卡片")
    p.add_argument("card_id")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_read)

    p = add("follow", "顺链跳读邻居卡")
    p.add_argument("card_id")
    p.add_argument("--predicate")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_follow)

    p = add("quote", "取论断原文与可核源片段（<card-id>#<claim-id>）")
    p.add_argument("ref")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_quote)

    p = add("hash", "计算某源某位置的 span 哈希（手写卡片作者工具）")
    p.add_argument("source_id")
    p.add_argument("loc")
    p.set_defaults(func=cmd_hash)

    p = add("fix-hashes", "重算全部 span 哈希；--write 就地更新")
    p.add_argument("--write", action="store_true")
    p.set_defaults(func=cmd_fix_hashes)

    p = add("eval", "golden set 评测（命中率 / 首位命中率）与忠实度抽查（--faithfulness）")
    p.add_argument("--golden", help="golden.yaml 路径（默认 <vault>/evals/golden.yaml）")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--min-hit", type=float, dest="min_hit")
    p.add_argument("--min-first", type=float, dest="min_first")
    p.add_argument(
        "--faithfulness", action="store_true", help="M3：抽样核验论断与源片段的绑定"
    )
    p.add_argument("--sample", type=int, default=50, help="忠实度抽样上限（默认 50）")
    p.add_argument("--seed", type=int, default=0, help="抽样种子（结果可复算）")
    p.add_argument(
        "--max-unfaithful",
        type=float,
        dest="max_unfaithful",
        default=0.02,
        help="不忠实率红线（默认 0.02）",
    )
    p.add_argument("--export", help="导出语义核对清单（JSON 路径）")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_eval)

    p = add("stats", "vault 概览统计")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_stats)

    p = add("ingest", "登记源：拷贝原件 + 抽取派生物 + 写 meta.yaml（无 LLM）")
    p.add_argument("path", help="文件或目录")
    p.add_argument("--id", help="源 id（默认 src-<slug>）")
    p.add_argument("--license", default="unknown")
    p.add_argument("--force", action="store_true", help="源已存在时重新登记")
    p.set_defaults(func=cmd_ingest)

    p = add("compile", "七步编译：propose → 并卡对齐 → 建链 → 矛盾 → 机器闸 → 抽样送审")
    p.add_argument("--source", action="append", help="只编译指定源（可重复；默认全部）")
    p.add_argument("--scripted", help="脚本化应答 YAML（离线 / 演示 / 测试）")
    p.add_argument(
        "--review-rate", type=float, dest="review_rate", help="覆盖抽样率（0–1）"
    )
    p.set_defaults(func=cmd_compile)

    rp = sub.add_parser("review", help="人工抽查闸：队列查看与裁决")
    rsub = rp.add_subparsers(dest="action", required=True)
    lp = rsub.add_parser("list", help="列出审核队列")
    lp.add_argument("--vault", default=".")
    lp.add_argument("--status", help="按状态过滤")
    lp.set_defaults(func=cmd_review)
    sp = rsub.add_parser("show", help="查看单个草案与拒因")
    sp.add_argument("draft_id")
    sp.add_argument("--vault", default=".")
    sp.set_defaults(func=cmd_review)
    ap = rsub.add_parser("approve", help="通过：草案入库（或并入既有卡）")
    ap.add_argument("draft_id")
    ap.add_argument("--merge-into", dest="merge_into", help="并入的目标卡 id")
    ap.add_argument("--force-new", dest="force_new", action="store_true")
    ap.add_argument("--by", default="human", help="操作者署名（入 _audit）")
    ap.add_argument("--vault", default=".")
    ap.set_defaults(func=cmd_review)
    jp = rsub.add_parser("reject", help="驳回：留痕并移入 _review/rejected/")
    jp.add_argument("draft_id")
    jp.add_argument("--reason", required=True)
    jp.add_argument("--by", default="human")
    jp.add_argument("--vault", default=".")
    jp.set_defaults(func=cmd_review)

    p = sub.add_parser("init", help="脚手架一个空 vault（含 generic 包与 CI 模板）")
    p.add_argument("path", nargs="?", default=".", help="目标目录（默认当前目录）")
    p.add_argument("--name", help="vault 名称（默认目录名）")
    p.set_defaults(func=cmd_init)

    p = add("drift", "失效信号总线：双通道漂移 + 时效过期 → suspect")
    p.add_argument("--report", action="store_true", help="只报告不落盘（CI 用）")
    p.add_argument(
        "--warn-threshold",
        type=float,
        dest="warn_threshold",
        help="suspect 占比警告阈值（如 0.05）",
    )
    p.set_defaults(func=cmd_drift)

    audit_parser = sub.add_parser("audit", help="suspect 复核：机器产信号，人平反")
    asub = audit_parser.add_subparsers(dest="action", required=True)
    alp = asub.add_parser("list", help="列出复核队列（suspect 卡）")
    alp.add_argument("--vault", default=".")
    alp.set_defaults(func=cmd_audit)
    arp = asub.add_parser("review", help="复核：pass 平反并刷新 verified_against；retire 退役")
    arp.add_argument("card_id")
    arp.add_argument("--outcome", required=True, choices=["pass", "retire"])
    arp.add_argument("--note", default="")
    arp.add_argument("--by", default="human")
    arp.add_argument("--vault", default=".")
    arp.set_defaults(func=cmd_audit)

    p = add("resolve", "裁决矛盾卡：胜方 active、败方 superseded（绝不自动裁决）")
    p.add_argument("card_id")
    p.add_argument("--winner", required=True, help="胜方论断 id（矛盾卡内的 c1/c2）")
    p.add_argument("--note", default="")
    p.add_argument("--by", default="human")
    p.set_defaults(func=cmd_resolve)

    p = add("backflow", "回流编译：evidence 事件失败聚类 → 陷阱卡草案（一律送审）")
    p.add_argument(
        "--min-cluster",
        type=int,
        dest="min_cluster",
        default=2,
        help="同类失败提卡阈值（默认 2；单次失败只记台账不成卡）",
    )
    p.add_argument("--kind", default="pitfall", help="回流卡类（默认 pitfall，需在启用 Pack 内）")
    p.set_defaults(func=cmd_backflow)

    p = add("contrib", "知识贡献度榜单：引用卡的任务成功率 vs 基线（可复算）")
    p.add_argument(
        "--min-events",
        type=int,
        dest="min_events",
        default=5,
        help="负贡献候选的最小样本量（默认 5）",
    )
    p.add_argument(
        "--apply-negative",
        action="store_true",
        dest="apply_negative",
        help="把负贡献卡置 suspect 进复核队列（默认只报告）",
    )
    p.add_argument("--by", default="human")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_contrib)

    p = add("gaps", "知识缺口清单：检索日志未命中 + golden 未命中，合并去重")
    p.add_argument(
        "--min-count", type=int, dest="min_count", default=1, help="最小出现次数（默认 1）"
    )
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_gaps)

    ep = sub.add_parser("export", help="导出：site（静态站点）/ json（产品快照）")
    esub = ep.add_subparsers(dest="what", required=True)
    for what, help_ in (("site", "静态站点目录"), ("json", "产品快照文件")):
        wp = esub.add_parser(what, help=help_)
        wp.add_argument("--out", required=True, help="输出路径")
        wp.add_argument(
            "--include-hidden",
            action="store_true",
            dest="include_hidden",
            help="包含 suspect/superseded/retired（默认按检索可见性排除）",
        )
        wp.add_argument("--vault", default=".")
        wp.set_defaults(func=cmd_export)

    p = sub.add_parser("bench", help="检索性能基线：合成 N 卡跑双后端（M4 红线 P95<200ms）")
    p.add_argument("--cards", type=int, default=10_000)
    p.add_argument("--queries", type=int, default=200)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--max-p95", type=float, dest="max_p95", help="P95 红线（ms），超限 exit 1")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_bench)

    dp = sub.add_parser("deps", help="知识依赖（M5 联邦）：sync 锁定 / status 过期与断链检查")
    dsub = dp.add_subparsers(dest="action", required=True)
    sp2 = dsub.add_parser("sync", help="解析依赖并写 vault.lock（含升级影响面报告）")
    sp2.add_argument("--vault", default=".")
    sp2.set_defaults(func=cmd_deps)
    st2 = dsub.add_parser("status", help="锁定一致性 / 依赖过期 / 断链与终态引用（CI 可用）")
    st2.add_argument("--vault", default=".")
    st2.set_defaults(func=cmd_deps)

    return parser


def main(argv: list[str] | None = None) -> int:
    _force_utf8()
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except FileNotFoundError as e:
        print(f"错误:{e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
