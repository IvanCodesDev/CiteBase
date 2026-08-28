"""MCP 四工具（M2）：与 CLI 同一条漏斗实现，只读、无命中契约、数据边界包裹。"""

from __future__ import annotations

from pathlib import Path

import pytest
from citebase.mcp.server import (
    DATA_BOUNDARY_CLOSE,
    DATA_BOUNDARY_OPEN,
    follow_impl,
    quote_impl,
    read_impl,
    search_impl,
)


def test_search_impl_hit(example_root: Path) -> None:
    result = search_impl(example_root, "幂等性")

    assert result["hit"] is True
    assert result["hits"][0]["id"] == "card-concept-idempotency"
    assert "injection_risk" in result["hits"][0]


def test_search_impl_no_hit_contract(example_root: Path) -> None:
    """无命中必须返回结构化降级信号：宿主要显式声明「库内无此内容」。"""
    result = search_impl(example_root, "量子引力波色谱")

    assert result["hit"] is False
    assert result["hits"] == []
    assert result["tried"]
    assert result["suggestion"]


def test_read_impl_wraps_body_in_data_boundary(example_root: Path) -> None:
    payload = read_impl(example_root, "card-method-bootstrap")

    assert payload["found"] is True
    assert payload["body"].startswith(DATA_BOUNDARY_OPEN)
    assert payload["body"].endswith(DATA_BOUNDARY_CLOSE)


def test_read_impl_missing_card(example_root: Path) -> None:
    payload = read_impl(example_root, "card-ghost")

    assert payload["found"] is False
    assert "knowledge_search" in payload["hint"]


def test_follow_impl_lists_neighbours(example_root: Path) -> None:
    payload = follow_impl(example_root, "card-method-exponential-backoff")

    assert payload["found"] is True
    assert "card-pitfall-retry-storm" in str(payload)

    missing = follow_impl(example_root, "card-ghost")
    assert missing["found"] is False


def test_quote_impl_verified_and_wrapped(example_root: Path) -> None:
    payload = quote_impl(example_root, "card-concept-idempotency#c1")

    assert payload["found"] is True
    span = payload["spans"][0]
    assert span["verified"] is True
    assert span["text"].startswith(DATA_BOUNDARY_OPEN)

    bad = quote_impl(example_root, "card-ghost#c1")
    assert bad["found"] is False


def test_build_server_registers_and_runs(example_root: Path) -> None:
    """冒烟：装了 mcp SDK 时 build_server 必须可构造（工具注册不抛错）。"""
    pytest.importorskip("mcp")
    from citebase.mcp.server import build_server

    assert build_server(example_root) is not None


def test_main_rejects_non_vault(tmp_path: Path) -> None:
    from citebase.mcp.server import main

    assert main(["--vault", str(tmp_path)]) == 2
