from __future__ import annotations

from datetime import date, datetime

import pytest
from citebase import frontmatter


def test_parse_roundtrip() -> None:
    doc = frontmatter.parse("---\nid: x\nn: 1\n---\n正文第一行\n")
    assert doc.meta == {"id": "x", "n": 1}
    assert doc.body.strip() == "正文第一行"
    again = frontmatter.parse(frontmatter.serialize(doc.meta, doc.body))
    assert again.meta == doc.meta
    assert again.body.strip() == doc.body.strip()


def test_parse_requires_frontmatter() -> None:
    with pytest.raises(ValueError, match="frontmatter"):
        frontmatter.parse("没有分隔块的正文")


def test_parse_requires_mapping() -> None:
    with pytest.raises(ValueError, match="映射"):
        frontmatter.parse("---\n- 1\n- 2\n---\n正文\n")


def test_empty_meta_becomes_dict() -> None:
    doc = frontmatter.parse("---\n\n---\n正文\n")
    assert doc.meta == {}
    assert doc.body == "正文\n"


def test_save_and_load_file(tmp_path) -> None:
    path = tmp_path / "card.md"
    frontmatter.save_file(path, frontmatter.Document(meta={"id": "x"}, body="正文"))
    doc = frontmatter.load_file(path)
    assert doc.meta == {"id": "x"}
    assert doc.body.strip() == "正文"


def test_jsonable_converts_dates() -> None:
    payload = {
        "d": date(2026, 8, 21),
        "ts": [datetime(2026, 8, 21, 12, 0, 0)],
        "nested": {"keep": "str"},
    }
    out = frontmatter.jsonable(payload)
    assert out["d"] == "2026-08-21"
    assert out["ts"] == ["2026-08-21T12:00:00"]
    assert out["nested"] == {"keep": "str"}
