"""MCP 消费面（L4）：读侧四工具的薄封装。

铁律（ADR-0006）：Agent 只读、人治理——本子包不得 import compiler，
治理动词（compile / drift / audit / resolve）永不进 MCP。
"""

from cardvault.mcp.server import build_server, follow_impl, quote_impl, read_impl, search_impl

__all__ = ["build_server", "follow_impl", "quote_impl", "read_impl", "search_impl"]
