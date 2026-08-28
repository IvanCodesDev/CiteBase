from __future__ import annotations

from pathlib import Path

import pytest
from citebase.adapters import DirSourceAdapter, FileSourceAdapter, adapter_for_path


def test_file_adapter_revision_and_change(tmp_path: Path) -> None:
    file = tmp_path / "notes.md"
    file.write_text("v1\n", encoding="utf-8")
    adapter = FileSourceAdapter(file)
    rev = adapter.revision()
    assert rev.startswith("sha256:")
    assert adapter.changed_since(rev) is False
    file.write_text("v2\n", encoding="utf-8")
    assert adapter.changed_since(rev) is True


def test_file_adapter_fetch(tmp_path: Path) -> None:
    file = tmp_path / "notes.md"
    file.write_text("正文\n", encoding="utf-8")
    dest_dir = tmp_path / "originals"
    copied = FileSourceAdapter(file).fetch(dest_dir)
    assert [p.name for p in copied] == ["notes.md"]
    assert (dest_dir / "notes.md").read_text(encoding="utf-8") == "正文\n"


def test_file_adapter_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        FileSourceAdapter(tmp_path / "nope.md").resolve()


def test_dir_adapter_revision_tracks_tree(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    (root / "sub").mkdir(parents=True)
    (root / "a.md").write_text("A\n", encoding="utf-8")
    (root / "sub" / "b.txt").write_text("B\n", encoding="utf-8")
    adapter = DirSourceAdapter(root)
    rev = adapter.revision()
    assert adapter.changed_since(rev) is False
    (root / "sub" / "b.txt").write_text("B2\n", encoding="utf-8")
    assert adapter.changed_since(rev) is True


def test_dir_adapter_ignores_hidden_and_fetches_tree(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    (root / ".git").mkdir(parents=True)
    (root / ".git" / "config").write_text("x", encoding="utf-8")
    (root / "a.md").write_text("A\n", encoding="utf-8")
    copied = DirSourceAdapter(root).fetch(tmp_path / "originals")
    assert [p.name for p in copied] == ["a.md"]


def test_adapter_for_path(tmp_path: Path) -> None:
    (tmp_path / "d").mkdir()
    (tmp_path / "f.md").write_text("x", encoding="utf-8")
    assert isinstance(adapter_for_path(tmp_path / "d"), DirSourceAdapter)
    assert isinstance(adapter_for_path(tmp_path / "f.md"), FileSourceAdapter)
