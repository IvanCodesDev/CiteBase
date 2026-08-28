from __future__ import annotations

from pathlib import Path

from citebase import index as index_mod
from citebase.vault import Vault
from helpers import base_meta, make_claim, write_card


def test_tokenize_ascii_and_cjk() -> None:
    assert index_mod.tokenize("Hello, World_x v2") == ["hello", "world_x", "v2"]
    assert index_mod.tokenize("缓存雪崩") == ["缓存", "存雪", "雪崩"]
    assert index_mod.tokenize("值") == ["值"]
    assert index_mod.tokenize("p值") == ["p", "值"]


def test_build_is_deterministic(example_root: Path) -> None:
    vault = Vault.load(example_root)
    first = index_mod.build(vault)
    second = index_mod.build(vault)
    assert first == second
    assert first["meta"]["cards"] == 24
    assert len(first["catalog"]) == 24


def test_alias_map_casefolded(example_root: Path) -> None:
    idx = index_mod.build(Vault.load(example_root))
    assert idx["aliases"]["幂等"] == ["card-concept-idempotency"]
    assert "bootstrap" in idx["aliases"]
    assert idx["aliases"]["bootstrap"] == ["card-method-bootstrap"]


def test_links_are_bidirectional(example_root: Path) -> None:
    idx = index_mod.build(Vault.load(example_root))
    out = idx["links"]["out"]["card-method-exponential-backoff"]
    assert {"predicate": "related_to", "to": "card-concept-idempotency"} in out
    incoming = idx["links"]["in"]["card-concept-idempotency"]
    assert {"predicate": "related_to", "from": "card-method-exponential-backoff"} in incoming


def test_write_then_check_consistent(mini_vault: Path) -> None:
    write_card(mini_vault, base_meta(claims=[make_claim()]))
    vault = Vault.load(mini_vault)
    idx = index_mod.build(vault)
    written = index_mod.write(mini_vault, idx)
    assert sorted(written) == sorted(index_mod.INDEX_FILES)
    assert index_mod.check(mini_vault, idx) == []


def test_check_detects_tamper_and_missing(mini_vault: Path) -> None:
    write_card(mini_vault, base_meta(claims=[make_claim()]))
    vault = Vault.load(mini_vault)
    idx = index_mod.build(vault)
    index_mod.write(mini_vault, idx)

    catalog = mini_vault / index_mod.INDEX_DIR / "catalog.json"
    catalog.write_text(catalog.read_text(encoding="utf-8") + " ", encoding="utf-8")
    problems = index_mod.check(mini_vault, idx)
    assert any("catalog.json" in p for p in problems)

    (mini_vault / index_mod.INDEX_DIR / "meta.json").unlink()
    problems = index_mod.check(mini_vault, idx)
    assert any("meta.json" in p and "缺失" in p for p in problems)
