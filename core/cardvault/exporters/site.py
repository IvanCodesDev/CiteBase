"""静态站点导出：零依赖、零 JS 构建的可读知识站点。

人读卡片的第三种形态（对 Agent 是协议、对人是文档、对产品是数据）：
index.html 按卡类分组列出摘要，每卡一页展示论断与出处（source + loc + 哈希前缀），
出处透明是页面的一等内容而非脚注。正文用内置的最小 Markdown 渲染器
（标题/列表/代码块/行内代码/粗体/段落），不引第三方渲染依赖。
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cardvault.exporters.json_snapshot import license_warnings, visible_cards
from cardvault.model import Card
from cardvault.vault import Vault

_CSS = """\
body { font-family: system-ui, "Segoe UI", sans-serif; margin: 2rem auto; max-width: 52rem;
       line-height: 1.65; color: #1c1e21; padding: 0 1rem; }
h1, h2, h3 { line-height: 1.3; }
code, pre { font-family: ui-monospace, Consolas, monospace; background: #f4f4f5;
            border-radius: 4px; }
code { padding: 0.1em 0.35em; }
pre { padding: 0.8em 1em; overflow-x: auto; }
a { color: #0b5fff; text-decoration: none; }
a:hover { text-decoration: underline; }
.badge { display: inline-block; font-size: 0.78rem; padding: 0.08em 0.55em;
         border-radius: 999px; background: #eef2ff; color: #3730a3; margin-right: 0.4em; }
.badge.status-contested { background: #fef3c7; color: #92400e; }
.badge.status-suspect { background: #fee2e2; color: #991b1b; }
.claim { border-left: 3px solid #c7d2fe; padding: 0.4em 0.9em; margin: 0.7em 0;
         background: #fafafa; }
.claim .src { font-size: 0.82rem; color: #6b7280; }
.summary { color: #4b5563; }
.warn { background: #fef2f2; border: 1px solid #fecaca; padding: 0.6em 1em;
        border-radius: 6px; }
footer { margin-top: 3rem; font-size: 0.82rem; color: #9ca3af; }
"""


@dataclass
class SiteReport:
    files: list[str] = field(default_factory=list)
    cards: int = 0
    license_warnings: list[dict[str, Any]] = field(default_factory=list)


def _md_to_html(markdown: str) -> str:
    """最小 Markdown 渲染：#标题 / - 列表 / ``` 代码块 / `行内` / **粗体** / 段落。"""
    out: list[str] = []
    paragraph: list[str] = []
    in_code = False
    code_lines: list[str] = []
    in_list = False

    def flush_paragraph() -> None:
        if paragraph:
            out.append(f"<p>{_inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    def _inline(text: str) -> str:
        escaped = html.escape(text, quote=False)
        parts = escaped.split("`")
        for i in range(1, len(parts), 2):
            parts[i] = f"<code>{parts[i]}</code>"
        rendered = "".join(parts)
        chunks = rendered.split("**")
        for i in range(1, len(chunks), 2):
            chunks[i] = f"<strong>{chunks[i]}</strong>"
        return "".join(chunks)

    for raw in markdown.splitlines():
        line = raw.rstrip()
        if in_code:
            if line.strip().startswith("```"):
                out.append(f"<pre>{html.escape('\n'.join(code_lines))}</pre>")
                code_lines.clear()
                in_code = False
            else:
                code_lines.append(raw)
            continue
        if line.strip().startswith("```"):
            flush_paragraph()
            close_list()
            in_code = True
            continue
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            close_list()
            continue
        if stripped.startswith("#"):
            flush_paragraph()
            close_list()
            level = min(len(stripped) - len(stripped.lstrip("#")), 6)
            out.append(f"<h{level}>{_inline(stripped[level:].strip())}</h{level}>")
            continue
        if stripped.startswith(("- ", "* ")):
            flush_paragraph()
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(stripped[2:].strip())}</li>")
            continue
        paragraph.append(stripped)
    if in_code:  # 未闭合代码块按原样吐出
        out.append(f"<pre>{html.escape('\n'.join(code_lines))}</pre>")
    flush_paragraph()
    close_list()
    return "\n".join(out)


def _page(title: str, body: str, *, root_prefix: str = "") -> str:
    return (
        "<!DOCTYPE html>\n<html lang=\"zh\">\n<head>\n<meta charset=\"utf-8\">\n"
        f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{html.escape(title)}</title>\n"
        f"<link rel=\"stylesheet\" href=\"{root_prefix}style.css\">\n"
        "</head>\n<body>\n"
        f"{body}\n"
        "<footer>由 CardVault 导出 · 出处可核，论断可验</footer>\n"
        "</body>\n</html>\n"
    )


def _card_page(vault: Vault, card: Card, exported: set[str]) -> str:
    meta = card.meta
    parts: list[str] = ['<p><a href="../index.html">← 索引</a></p>']
    badges = f"<span class=\"badge\">{html.escape(meta.kind)}</span>"
    badges += f"<span class=\"badge status-{meta.status}\">{html.escape(meta.status)}</span>"
    parts.append(f"<h1>{html.escape(meta.name)}</h1>")
    parts.append(f"<p>{badges} <code>{html.escape(meta.id)}</code></p>")
    parts.append(f"<p class=\"summary\">{html.escape(meta.summary)}</p>")
    if meta.aliases:
        parts.append(
            "<p>别名：" + "、".join(html.escape(a) for a in meta.aliases) + "</p>"
        )
    if meta.tags:
        parts.append("<p>标签：" + "、".join(html.escape(t) for t in meta.tags) + "</p>")

    if meta.claims:
        parts.append("<h2>论断</h2>")
        for claim in meta.claims:
            spans = []
            for span in claim.sources:
                src = vault.sources.get(span.source)
                license_ = src.license if src else "?"
                spans.append(
                    f"源 <code>{html.escape(span.source)}</code> @ "
                    f"<code>{html.escape(span.loc)}</code>"
                    f"（sha256:{html.escape(span.span_sha256[:12])}…，license={html.escape(license_)}）"
                )
            status_note = "" if claim.status == "active" else f" [{html.escape(claim.status)}]"
            parts.append(
                "<div class=\"claim\">"
                f"<div><strong>[{html.escape(claim.id)}]</strong> "
                f"{html.escape(claim.text)}{status_note}</div>"
                f"<div class=\"src\">{'；'.join(spans)}</div>"
                "</div>"
            )

    if meta.links:
        parts.append("<h2>关联</h2><ul>")
        for link in meta.links:
            target = vault.cards.get(link.to)
            label = html.escape(target.meta.name) if target else html.escape(link.to)
            if link.to in exported:
                parts.append(
                    f"<li>-{html.escape(link.predicate)}→ "
                    f"<a href=\"{html.escape(link.to)}.html\">{label}</a></li>"
                )
            else:
                note = "未随站点导出" if target else "缺失/跨库"
                parts.append(
                    f"<li>-{html.escape(link.predicate)}→ {label}（{note}）</li>"
                )
        parts.append("</ul>")

    if card.body.strip():
        parts.append("<h2>正文</h2>")
        parts.append(_md_to_html(card.body))
    return _page(f"{meta.name} · {vault.config.name}", "\n".join(parts), root_prefix="../")


def _index_page(vault: Vault, cards: list[Card], warnings: list[dict[str, Any]]) -> str:
    parts = [f"<h1>{html.escape(vault.config.name)}</h1>"]
    parts.append(
        f"<p class=\"summary\">{len(cards)} 张卡片 · "
        f"{sum(len(c.meta.claims) for c in cards)} 条论断（全部绑定源片段哈希）</p>"
    )
    if warnings:
        items = "，".join(f"<code>{html.escape(w['source'])}</code>" for w in warnings)
        parts.append(
            f"<div class=\"warn\">许可证警示：以下被引源 license=unknown，"
            f"对外发布前请核实：{items}</div>"
        )
    by_kind: dict[str, list[Card]] = {}
    for card in cards:
        by_kind.setdefault(card.meta.kind, []).append(card)
    for kind in sorted(by_kind):
        parts.append(f"<h2>{html.escape(kind)}（{len(by_kind[kind])}）</h2><ul>")
        for card in by_kind[kind]:
            parts.append(
                f"<li><a href=\"cards/{html.escape(card.meta.id)}.html\">"
                f"{html.escape(card.meta.name)}</a>"
                f" — <span class=\"summary\">{html.escape(card.meta.summary)}</span></li>"
            )
        parts.append("</ul>")
    return _page(vault.config.name, "\n".join(parts))


def export_site(
    vault: Vault, out_dir: Path, *, include_hidden: bool = False
) -> SiteReport:
    cards = visible_cards(vault, include_hidden=include_hidden)
    report = SiteReport(cards=len(cards), license_warnings=license_warnings(vault, cards))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "cards").mkdir(parents=True, exist_ok=True)

    def write(rel: str, text: str) -> None:
        (out_dir / rel).write_text(text, encoding="utf-8", newline="\n")
        report.files.append(rel)

    write("style.css", _CSS)
    write("index.html", _index_page(vault, cards, report.license_warnings))
    exported = {card.meta.id for card in cards}
    for card in cards:
        write(f"cards/{card.meta.id}.html", _card_page(vault, card, exported))
    return report
