"""IndexBackend 实现（M4）：memory（进程内重建）与 sqlite（磁盘加速缓存）。

选择规则：``vault.yaml`` 的 ``index_backend``（默认 memory）。memory 每次从卡片
重建（永远新鲜，小库无感）；sqlite 读 ``_index/index.sqlite``（``vault index``
生成，10k 卡级把 search 从「重建整库」降为「按需查询」）。
"""

from __future__ import annotations

from typing import Any

from cardvault import index as index_mod
from cardvault.backends.memory import MemoryIndexBackend
from cardvault.backends.sqlite import SQLITE_FILE, SqliteIndexBackend, write_sqlite
from cardvault.ports import IndexBackend
from cardvault.vault import Vault

__all__ = [
    "SQLITE_FILE",
    "IndexBackend",
    "MemoryIndexBackend",
    "SqliteIndexBackend",
    "select_backend",
    "write_sqlite",
]


def select_backend(vault: Vault) -> IndexBackend | dict[str, Any]:
    """按 vault 配置选择检索后端；sqlite 模式要求先 ``vault index`` 生成缓存。"""
    if vault.config.index_backend == "sqlite":
        path = vault.root / index_mod.INDEX_DIR / SQLITE_FILE
        if not path.is_file():
            raise FileNotFoundError(
                f"index_backend=sqlite 但缺少 {index_mod.INDEX_DIR}/{SQLITE_FILE}"
                "（先运行 vault index）"
            )
        return SqliteIndexBackend(path)
    return index_mod.build(vault)
