"""测试共用构造器：真实示例 vault 路径 + 可编程的最小临时 vault。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from citebase import frontmatter

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = REPO_ROOT / "examples" / "generic-basics"

SOURCE_TEXT = "第一行事实。\n第二行事实。\n第三行事实。\n"

PACK_YAML = """\
name: testpack
version: 0.1.0
description: 测试用最小包
card_kinds:
  - kind: concept
    body_sections: [是什么]
  - kind: method
    body_sections: [是什么]
  - kind: pitfall
    body_sections: [现象, 根因, 规避, 触发条件, 关联]
link_predicates: [related_to]
"""

SOURCE_META_TPL = """\
id: src-notes
adapter: file
uri: extracted/text.md
revision: v1
extractions:
  - path: extracted/text.md
    extractor: manual@1
    confidence: {confidence}
"""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def span_text(loc: str) -> str:
    """按 spanhash 的 loc 语义在测试源文本上取片段（仅供构造正确哈希）。"""
    if "#" not in loc:
        return SOURCE_TEXT
    start_s, end_s = loc.split("#L", 1)[1].split("-L", 1)
    lines = SOURCE_TEXT.splitlines()
    return "\n".join(lines[int(start_s) - 1 : int(end_s)])


def make_vault(root: Path, *, confidence: float = 1.0) -> Path:
    (root / "packs" / "testpack").mkdir(parents=True)
    (root / "vault.yaml").write_text("name: test-vault\npacks: [testpack]\n", encoding="utf-8")
    (root / "packs" / "testpack" / "pack.yaml").write_text(PACK_YAML, encoding="utf-8")
    src = root / "sources" / "src-notes"
    (src / "extracted").mkdir(parents=True)
    (src / "meta.yaml").write_text(SOURCE_META_TPL.format(confidence=confidence), encoding="utf-8")
    (src / "extracted" / "text.md").write_text(SOURCE_TEXT, encoding="utf-8", newline="\n")
    return root


def make_drift_vault(tmp_path: Path) -> tuple[Path, Path]:
    """带真实上游文件的最小 vault（漂移/治理测试用）。

    src-notes 指向 tmp 里的真实上游文件，revision 为内容哈希——改写/删除上游
    即可触发通道 A；篡改 extracted/text.md 即可触发通道 B。
    返回 (vault_root, upstream_file)。
    """
    from citebase.adapters import FileSourceAdapter

    upstream = tmp_path / "upstream" / "notes.md"
    upstream.parent.mkdir(parents=True, exist_ok=True)
    upstream.write_text(SOURCE_TEXT, encoding="utf-8", newline="\n")
    root = make_vault(tmp_path / "vault")
    revision = FileSourceAdapter(upstream).revision()
    meta = (
        "id: src-notes\n"
        "adapter: file\n"
        f'uri: "{upstream.resolve().as_posix()}"\n'
        f"revision: {revision}\n"
        "extractions:\n"
        "  - path: extracted/text.md\n"
        "    extractor: manual@1\n"
        "    confidence: 1.0\n"
    )
    (root / "sources" / "src-notes" / "meta.yaml").write_text(meta, encoding="utf-8")
    return root, upstream


def base_meta(card_id: str = "card-concept-alpha", **overrides: Any) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "id": card_id,
        "kind": "concept",
        "name": "Alpha",
        "summary": "一句话摘要。",
        "version": 1,
        "status": "active",
    }
    meta.update(overrides)
    return meta


def make_claim(
    text: str = "第一行事实。",
    loc: str = "extracted/text.md#L1-L1",
    *,
    cid: str = "c1",
    sha: str | None = None,
    source: str = "src-notes",
    **extra: Any,
) -> dict[str, Any]:
    return {
        "id": cid,
        "text": text,
        "sources": [
            {
                "source": source,
                "loc": loc,
                "span_sha256": sha if sha is not None else sha256_text(span_text(loc)),
            }
        ],
        **extra,
    }


def write_card(
    root: Path,
    meta: dict[str, Any],
    body: str = "## 是什么\n\n正文。\n",
    relpath: str | None = None,
) -> Path:
    if relpath is None:
        relpath = f"cards/{meta.get('kind', 'x')}/{meta['id']}.md"
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter.save_file(path, frontmatter.Document(meta=meta, body=body))
    return path


# ---------- M3：证据事件构造器 ----------


def make_event(
    n: int,
    *,
    status: str = "failure",
    category: str | None = None,
    summary: str | None = None,
    root_cause: str | None = None,
    cards: list[str] | None = None,
    ts: str | None = None,
) -> dict[str, Any]:
    """构造一条合法的 EvidenceEvent 字典（JSONL 行的内容）。"""
    event: dict[str, Any] = {
        "event_id": f"evt-2026-08-14-run-{n:04d}",
        "ts": ts or f"2026-08-14T{n % 24:02d}:{n % 60:02d}:00Z",
        "system": {"name": "omm-evals", "version": "0.3"},
        "task_ref": f"run-{n:04d}",
        "outcome": {"status": status},
    }
    if cards:
        event["cards_consulted"] = [{"card_id": c} for c in cards]
    failure: dict[str, Any] = {}
    if category:
        failure["category"] = category
    if summary:
        failure["summary"] = summary
    if root_cause:
        failure["root_cause_hypothesis"] = root_cause
    if failure:
        event["failure"] = failure
    return event


def write_events(
    vault_root: Path,
    events: list[dict[str, Any]],
    *,
    filename: str = "2026-08.jsonl",
) -> Path:
    evidence_dir = vault_root / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / filename
    lines = [json.dumps(e, ensure_ascii=False) for e in events]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path
