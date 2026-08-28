"""sqlite 检索后端（M4）：与 memory 后端逐分一致是验收线（对照测试）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from citebase import cli, retrieve
from citebase import index as index_mod
from citebase.backends import select_backend
from citebase.backends.sqlite import SqliteIndexBackend, write_sqlite
from citebase.vault import Vault

#: 覆盖全部漏斗跳与过滤参数的对照查询集。
PARITY_QUERIES = [
    ("幂等性", {}),                       # 精确别名
    ("GM11", {}),                         # ASCII 别名（若无则走 bm25/miss，同样要求一致）
    ("缓存 同时失效", {}),                # BM25
    ("重试", {"kind": "pitfall"}),        # kind 过滤
    ("重试风暴", {"limit": 3}),           # limit
    ("幂等", {}),                         # 部分词
    ("idempotency", {}),                  # 英文
    ("量子引力波色谱", {}),               # 未命中（建议语一致）
    ("退避", {"include_suspect": True}),  # include_suspect 参数
]


@pytest.fixture()
def sqlite_backend(example_root: Path, tmp_path: Path) -> SqliteIndexBackend:
    idx = index_mod.build(Vault.load(example_root))
    path = write_sqlite(tmp_path, idx)
    backend = SqliteIndexBackend(path)
    yield backend
    backend.close()


def test_search_parity_memory_vs_sqlite(
    example_root: Path, sqlite_backend: SqliteIndexBackend
) -> None:
    """M4 验收线：后端切换不改四工具行为——含得分、排序、tried 与建议语。"""
    idx = index_mod.build(Vault.load(example_root))
    for query, kwargs in PARITY_QUERIES:
        via_memory = retrieve.search(idx, query, **kwargs).to_dict()
        via_sqlite = retrieve.search(sqlite_backend, query, **kwargs).to_dict()
        assert via_memory == via_sqlite, f"后端结果不一致：{query!r} {kwargs}"


def test_follow_parity_memory_vs_sqlite(
    example_root: Path, sqlite_backend: SqliteIndexBackend
) -> None:
    idx = index_mod.build(Vault.load(example_root))
    for card_id in sorted(Vault.load(example_root).cards):
        assert retrieve.follow(idx, card_id) == retrieve.follow(sqlite_backend, card_id)
    assert retrieve.follow(sqlite_backend, "card-ghost") is None


def test_select_backend_requires_cache_file(tmp_path: Path) -> None:
    from helpers import make_vault

    root = make_vault(tmp_path / "vault")
    (root / "vault.yaml").write_text(
        "name: test-vault\npacks: [testpack]\nindex_backend: sqlite\n",
        encoding="utf-8",
    )
    with pytest.raises(FileNotFoundError, match=r"index\.sqlite"):
        select_backend(Vault.load(root))


def test_cli_index_builds_sqlite_cache_and_search_uses_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from helpers import base_meta, make_claim, make_vault, write_card

    root = make_vault(tmp_path / "vault")
    write_card(root, base_meta(aliases=["alpha"], claims=[make_claim()]))
    (root / "vault.yaml").write_text(
        "name: test-vault\npacks: [testpack]\nindex_backend: sqlite\n",
        encoding="utf-8",
    )

    # 未建缓存时明确报错引导
    assert cli.main(["search", "alpha", "--vault", str(root)]) == 2
    assert "index.sqlite" in capsys.readouterr().out

    assert cli.main(["index", "--vault", str(root)]) == 0
    assert "sqlite 加速缓存" in capsys.readouterr().out
    assert (root / "_index" / "index.sqlite").is_file()

    assert cli.main(["search", "alpha", "--vault", str(root)]) == 0
    assert "card-concept-alpha" in capsys.readouterr().out
