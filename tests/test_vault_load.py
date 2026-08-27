from __future__ import annotations

from pathlib import Path

import pytest
from cardvault.vault import Vault
from helpers import base_meta, make_vault, write_card


def test_load_example_vault(example_root: Path) -> None:
    vault = Vault.load(example_root)
    assert vault.load_errors == []
    assert len(vault.cards) == 24
    assert len(vault.sources) == 3
    assert set(vault.packs) == {"generic"}


def test_enabled_vocabularies(example_root: Path) -> None:
    vault = Vault.load(example_root)
    assert {"concept", "method", "pitfall", "contradiction"} <= vault.enabled_kinds()
    assert "supersedes" in vault.enabled_predicates()
    assert "related_to" in vault.enabled_predicates()


def test_missing_vault_yaml(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        Vault.load(tmp_path)


def test_broken_card_recorded_not_fatal(mini_vault: Path) -> None:
    write_card(mini_vault, base_meta())
    bad = mini_vault / "cards" / "concept" / "broken.md"
    bad.write_text("没有 frontmatter 的文件", encoding="utf-8")
    vault = Vault.load(mini_vault)
    assert len(vault.cards) == 1
    assert any("broken.md" in e.path for e in vault.load_errors)


def test_duplicate_card_id_recorded(mini_vault: Path) -> None:
    write_card(mini_vault, base_meta())
    write_card(mini_vault, base_meta(), relpath="cards/concept/dup.md")
    vault = Vault.load(mini_vault)
    assert len(vault.cards) == 1
    assert any("id 重复" in e.message for e in vault.load_errors)


def test_missing_pack_recorded(tmp_path: Path) -> None:
    root = make_vault(tmp_path / "v")
    (root / "vault.yaml").write_text("name: v\npacks: [ghost]\n", encoding="utf-8")
    vault = Vault.load(root)
    assert vault.packs == {}
    assert any("不存在" in e.message for e in vault.load_errors)


def test_extraction_confidence(mini_vault: Path) -> None:
    vault = Vault.load(mini_vault)
    assert vault.extraction_confidence("src-notes", "extracted/text.md") == 1.0
    assert vault.extraction_confidence("src-notes", "extracted/nope.md") is None
    assert vault.extraction_confidence("src-ghost", "extracted/text.md") is None
