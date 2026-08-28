"""SourceSpan 的定位解析与内容哈希。

loc 语法（M0 支持两种）：
- ``<relpath>#L<start>-L<end>``：派生物文本的行区间（1-based，闭区间），
  span 文本 = 区间行以 \\n 连接；
- ``<relpath>``：整个派生物文件文本。

span_sha256 = sha256(span 文本的 UTF-8 字节)。重算不一致 = 引用造假或源漂移（L-PROV-2）。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from citebase.model import SourceSpan
from citebase.vault import Vault

_LINE_RANGE_RE = re.compile(r"\A(?P<path>[^#]+)#L(?P<start>\d+)-L(?P<end>\d+)\Z")


@dataclass
class ResolvedSpan:
    relpath: str
    text: str


class SpanError(ValueError):
    """loc 无法解析或指向的内容不存在。"""


def parse_loc(loc: str) -> tuple[str, tuple[int, int] | None]:
    m = _LINE_RANGE_RE.match(loc)
    if m is not None:
        start, end = int(m.group("start")), int(m.group("end"))
        if start < 1 or end < start:
            raise SpanError(f"非法行区间：{loc}")
        return m.group("path"), (start, end)
    if "#" in loc:
        raise SpanError(f"无法解析的 loc 片段语法：{loc}")
    return loc, None


def resolve(vault: Vault, span: SourceSpan) -> ResolvedSpan:
    relpath, line_range = parse_loc(span.loc)
    file = vault.source_file(span.source, relpath)
    if not file.is_file():
        raise SpanError(f"源派生物不存在：sources/{span.source}/{relpath}")
    text = file.read_text(encoding="utf-8")
    if line_range is None:
        return ResolvedSpan(relpath=relpath, text=text)
    lines = text.splitlines()
    start, end = line_range
    if end > len(lines):
        raise SpanError(
            f"行区间越界：{span.loc}（文件只有 {len(lines)} 行）"
        )
    return ResolvedSpan(relpath=relpath, text="\n".join(lines[start - 1 : end]))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute(vault: Vault, span: SourceSpan) -> str:
    """重算 span 哈希（抛 SpanError 表示定位失败）。"""
    return sha256_text(resolve(vault, span).text)


def verify(vault: Vault, span: SourceSpan) -> bool:
    return compute(vault, span) == span.span_sha256
