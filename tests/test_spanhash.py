from __future__ import annotations

from pathlib import Path

import pytest
from citebase import spanhash
from citebase.model import SourceSpan
from citebase.vault import Vault
from helpers import SOURCE_TEXT, sha256_text, span_text


def test_parse_loc_variants() -> None:
    assert spanhash.parse_loc("extracted/text.md") == ("extracted/text.md", None)
    assert spanhash.parse_loc("extracted/text.md#L2-L3") == ("extracted/text.md", (2, 3))


def test_parse_loc_rejects_bad_range() -> None:
    with pytest.raises(spanhash.SpanError):
        spanhash.parse_loc("extracted/text.md#L3-L1")
    with pytest.raises(spanhash.SpanError):
        spanhash.parse_loc("extracted/text.md#p2")


def test_resolve_line_range(mini_vault: Path) -> None:
    vault = Vault.load(mini_vault)
    span = SourceSpan(
        source="src-notes",
        loc="extracted/text.md#L2-L3",
        span_sha256=sha256_text(span_text("extracted/text.md#L2-L3")),
    )
    resolved = spanhash.resolve(vault, span)
    assert resolved.text == "第二行事实。\n第三行事实。"
    assert spanhash.verify(vault, span)


def test_resolve_full_file(mini_vault: Path) -> None:
    vault = Vault.load(mini_vault)
    span = SourceSpan(
        source="src-notes",
        loc="extracted/text.md",
        span_sha256=sha256_text(SOURCE_TEXT),
    )
    assert spanhash.resolve(vault, span).text == SOURCE_TEXT
    assert spanhash.verify(vault, span)


def test_resolve_out_of_range(mini_vault: Path) -> None:
    vault = Vault.load(mini_vault)
    span = SourceSpan(source="src-notes", loc="extracted/text.md#L1-L99", span_sha256="0" * 64)
    with pytest.raises(spanhash.SpanError, match="越界"):
        spanhash.resolve(vault, span)


def test_resolve_missing_file(mini_vault: Path) -> None:
    vault = Vault.load(mini_vault)
    span = SourceSpan(source="src-notes", loc="extracted/nope.md", span_sha256="0" * 64)
    with pytest.raises(spanhash.SpanError, match="不存在"):
        spanhash.resolve(vault, span)


def test_verify_detects_drift(mini_vault: Path) -> None:
    vault = Vault.load(mini_vault)
    span = SourceSpan(
        source="src-notes",
        loc="extracted/text.md#L1-L1",
        span_sha256=sha256_text("第一行事实。"),
    )
    assert spanhash.verify(vault, span)
    (mini_vault / "sources" / "src-notes" / "extracted" / "text.md").write_text(
        "被改掉的第一行。\n第二行事实。\n第三行事实。\n", encoding="utf-8", newline="\n"
    )
    assert not spanhash.verify(vault, span)
