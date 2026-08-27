from __future__ import annotations

from typing import Any

import pytest
from cardvault import index as index_mod
from cardvault import retrieve
from cardvault.vault import Vault
from helpers import EXAMPLE_ROOT, base_meta, make_claim, write_card


@pytest.fixture(scope="module")
def example() -> tuple[Vault, dict[str, Any]]:
    vault = Vault.load(EXAMPLE_ROOT)
    return vault, index_mod.build(vault)


def test_exact_hit_by_name(example: tuple[Vault, dict[str, Any]]) -> None:
    _, idx = example
    result = retrieve.search(idx, "幂等性")
    assert result.hit
    assert result.hits[0].id == "card-concept-idempotency"
    assert result.hits[0].jump == "exact"


def test_exact_hit_alias_case_insensitive(example: tuple[Vault, dict[str, Any]]) -> None:
    _, idx = example
    result = retrieve.search(idx, "Bootstrap")
    assert result.hit
    assert result.hits[0].id == "card-method-bootstrap"
    assert result.hits[0].jump == "exact"


def test_bm25_keyword_hit(example: tuple[Vault, dict[str, Any]]) -> None:
    _, idx = example
    result = retrieve.search(idx, "训练误差下降 验证误差上升")
    assert result.hit
    assert result.hits[0].id == "card-pitfall-overfitting"
    assert result.hits[0].jump == "bm25"
    assert result.hits[0].claim is not None


def test_kind_filter_falls_through_exact(example: tuple[Vault, dict[str, Any]]) -> None:
    """「早停」精确命中的是 method 卡；kind=pitfall 时应降级到 BM25 命中过拟合卡。"""
    _, idx = example
    result = retrieve.search(idx, "早停", kind="pitfall")
    assert result.hit
    assert result.hits[0].jump == "bm25"
    assert result.hits[0].id == "card-pitfall-overfitting"


def test_graph_jump_on_near_alias(example: tuple[Vault, dict[str, Any]]) -> None:
    """拼写近似「bootstrap」但无 token 命中时，走链接图邻域第三跳。"""
    _, idx = example
    result = retrieve.search(idx, "bootstrapp")
    assert result.hit
    assert all(h.jump == "graph" for h in result.hits)
    ids = {h.id for h in result.hits}
    assert {"card-method-bootstrap", "card-concept-confidence-interval"} <= ids


def test_no_hit_contract(example: tuple[Vault, dict[str, Any]]) -> None:
    _, idx = example
    result = retrieve.search(idx, "量子引力波色谱")
    assert not result.hit
    assert result.hits == []
    assert len(result.tried) == 3
    assert result.suggestion


def test_tag_filter(example: tuple[Vault, dict[str, Any]]) -> None:
    _, idx = example
    result = retrieve.search(idx, "交叉验证", tags=["时间序列"])
    assert not result.hit or all(
        "时间序列" in idx["catalog"][h.id]["tags"] for h in result.hits
    )


def test_suspect_hidden_by_default(tmp_path) -> None:
    from helpers import make_vault

    root = make_vault(tmp_path / "v")
    write_card(root, base_meta(status="suspect", claims=[make_claim()]))
    idx = index_mod.build(Vault.load(root))
    assert not retrieve.search(idx, "Alpha").hit
    shown = retrieve.search(idx, "Alpha", include_suspect=True)
    assert shown.hit
    assert shown.hits[0].status == "suspect"


def test_claim_valid_time_windows() -> None:
    active = {"status": "active", "valid_from": None, "valid_until": None}
    assert retrieve.claim_valid(active, None)
    expired = {"status": "active", "valid_from": None, "valid_until": "2020-01-01T00:00:00"}
    assert not retrieve.claim_valid(expired, None)
    not_yet = {"status": "active", "valid_from": "2999-01-01T00:00:00", "valid_until": None}
    assert not retrieve.claim_valid(not_yet, None)
    superseded = {"status": "superseded", "valid_from": None, "valid_until": None}
    assert not retrieve.claim_valid(superseded, None)
    as_of = retrieve.parse_as_of("2019-06-01T00:00:00")
    assert retrieve.claim_valid(expired, as_of)


def test_parse_as_of() -> None:
    assert retrieve.parse_as_of(None) is None
    assert retrieve.parse_as_of("") is None
    parsed = retrieve.parse_as_of("2026-01-01T08:00:00+08:00")
    assert parsed is not None
    assert parsed.tzinfo is None
    assert parsed.hour == 0


def test_follow_edges(example: tuple[Vault, dict[str, Any]]) -> None:
    _, idx = example
    edges = retrieve.follow(idx, "card-method-exponential-backoff")
    assert edges is not None
    out_targets = {e["card"] for e in edges["out"]}
    assert {"card-concept-idempotency", "card-pitfall-retry-storm"} <= out_targets
    incoming = {e["card"] for e in edges["in"]}
    assert "card-concept-idempotency" in incoming
    assert retrieve.follow(idx, "card-ghost") is None


def test_follow_predicate_filter(example: tuple[Vault, dict[str, Any]]) -> None:
    _, idx = example
    edges = retrieve.follow(idx, "card-method-exponential-backoff", predicate="pitfall")
    assert edges is not None
    assert [e["card"] for e in edges["out"]] == ["card-pitfall-retry-storm"]


def test_quote_verified(example: tuple[Vault, dict[str, Any]]) -> None:
    vault, _ = example
    result = retrieve.quote(vault, "card-concept-idempotency#c1")
    assert result is not None
    assert result.text.startswith("幂等操作")
    assert all(s.verified for s in result.spans)
    assert result.spans[0].text == "幂等操作重复执行的效果与执行一次相同，是安全重试的前提。"
    assert result.spans[0].license == "CC-BY-4.0"


def test_quote_invalid_refs(example: tuple[Vault, dict[str, Any]]) -> None:
    vault, _ = example
    assert retrieve.quote(vault, "card-concept-idempotency") is None
    assert retrieve.quote(vault, "card-ghost#c1") is None
    assert retrieve.quote(vault, "card-concept-idempotency#c99") is None
