"""Markdown + YAML frontmatter 的解析与序列化。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

_FM_RE = re.compile(r"\A---\s*\n(?P<meta>.*?)\n---\s*\n?(?P<body>.*)\Z", re.DOTALL)


@dataclass
class Document:
    meta: dict[str, Any]
    body: str


def parse(text: str) -> Document:
    m = _FM_RE.match(text)
    if m is None:
        raise ValueError("缺少 YAML frontmatter（文件必须以 '---' 分隔块开头）")
    meta = yaml.safe_load(m.group("meta"))
    if meta is None:
        meta = {}
    if not isinstance(meta, dict):
        raise ValueError("frontmatter 必须是 YAML 映射")
    return Document(meta=meta, body=m.group("body"))


def serialize(meta: dict[str, Any], body: str) -> str:
    meta_text = yaml.safe_dump(
        meta, sort_keys=False, allow_unicode=True, default_flow_style=False, width=100
    ).strip()
    return f"---\n{meta_text}\n---\n\n{body.strip()}\n"


def load_file(path: Path) -> Document:
    return parse(path.read_text(encoding="utf-8"))


def save_file(path: Path, doc: Document) -> None:
    path.write_text(serialize(doc.meta, doc.body), encoding="utf-8", newline="\n")


def jsonable(value: Any) -> Any:
    """把 YAML 解析产物转为可 JSON 化结构（date/datetime → ISO 字符串），供 jsonschema 校验。"""
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value
