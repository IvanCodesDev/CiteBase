from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from citebase.adapters import DirSourceAdapter, FileSourceAdapter
from citebase.extractors import PlainTextExtractor
from citebase.ingest import derivative_relpath, ingest, slugify
from citebase.model import SourceMeta


def test_slugify() -> None:
    assert slugify("2024 MCM Paper_0417") == "2024-mcm-paper-0417"
    assert slugify("Hello.World") == "hello-world"
    # 纯中文无 ASCII 内容 → 哈希后缀，保证 id 仍然合法
    assert len(slugify("统计笔记")) == 8


def test_derivative_relpath() -> None:
    assert derivative_relpath(Path("paper.pdf"), single=True) == "extracted/text.md"
    assert derivative_relpath(Path("docs/a.md"), single=False) == "extracted/docs/a.md"
    assert derivative_relpath(Path("data/b.txt"), single=False) == "extracted/data/b.txt.md"


def test_ingest_single_file(mini_vault: Path, tmp_path: Path) -> None:
    corpus = tmp_path / "外部资料"
    corpus.mkdir()
    file = corpus / "engineering-notes.md"
    file.write_bytes("幂等笔记\r\n第二行\n".encode())

    result = ingest(mini_vault, FileSourceAdapter(file))
    assert result.meta.id == "src-engineering-notes"
    src_dir = mini_vault / "sources" / result.meta.id
    assert (src_dir / "originals" / "engineering-notes.md").is_file()
    derived = (src_dir / "extracted" / "text.md").read_text(encoding="utf-8")
    assert derived == "幂等笔记\n第二行\n"  # CRLF 归一

    meta = SourceMeta.model_validate(
        yaml.safe_load((src_dir / "meta.yaml").read_text(encoding="utf-8"))
    )
    assert meta.adapter == "file"
    assert meta.revision.startswith("sha256:")
    assert meta.extractions[0].path == "extracted/text.md"
    assert meta.extractions[0].extractor == "plain@1"
    assert meta.extractions[0].confidence == 1.0


def test_ingest_duplicate_requires_force(mini_vault: Path, tmp_path: Path) -> None:
    file = tmp_path / "notes.md"
    file.write_text("x\n", encoding="utf-8")
    ingest(mini_vault, FileSourceAdapter(file), source_id="src-notes-2")
    with pytest.raises(ValueError, match="已存在"):
        ingest(mini_vault, FileSourceAdapter(file), source_id="src-notes-2")
    file.write_text("y\n", encoding="utf-8")
    result = ingest(mini_vault, FileSourceAdapter(file), source_id="src-notes-2", force=True)
    assert (mini_vault / "sources" / "src-notes-2" / "extracted" / "text.md").read_text(
        encoding="utf-8"
    ) == "y\n"
    assert result.meta.revision.startswith("sha256:")


def test_ingest_dir_with_skipped(mini_vault: Path, tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    (corpus / "docs").mkdir(parents=True)
    (corpus / "docs" / "a.md").write_text("A\n", encoding="utf-8")
    (corpus / "b.txt").write_text("B\n", encoding="utf-8")
    (corpus / "image.bin").write_bytes(b"\x00\x01")

    result = ingest(mini_vault, DirSourceAdapter(corpus), source_id="src-corpus")
    assert sorted(result.derivatives) == ["extracted/b.txt.md", "extracted/docs/a.md"]
    assert result.skipped == ["image.bin"]


def test_ingest_rejects_all_unextractable(mini_vault: Path, tmp_path: Path) -> None:
    file = tmp_path / "binary.bin"
    file.write_bytes(b"\x00")
    with pytest.raises(ValueError, match="没有抽取器"):
        ingest(mini_vault, FileSourceAdapter(file), extractors=[PlainTextExtractor()])
