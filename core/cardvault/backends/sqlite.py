"""sqlite 后端：``_index/index.sqlite``，10k 卡级检索加速缓存。

设计取舍（诚实声明）：不用 FTS5 的内建 bm25() 排序——它的分词与打分和内核的
加权分词（ASCII 词 + CJK bigram + 字段权重）不等价，会破坏「后端切换不改四工具
行为」这条 M4 验收线。这里用 postings 表 + 覆盖索引按需取倒排行，BM25 打分仍走
retrieve 里同一段 Python——两个后端对同一索引**逐分一致**。

该文件是纯生成缓存（非提交物；L-IDX-1 的逐字节校验只针对 JSON 索引），
由 ``vault index`` 在 ``index_backend: sqlite`` 时重建，坏了删掉重建即可。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

SQLITE_FILE = "index.sqlite"
_SCHEMA_VERSION = "cardvault-sqlite/0.1"

_SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE catalog(
    card_id TEXT PRIMARY KEY,
    entry TEXT NOT NULL,
    doclen INTEGER NOT NULL
);
CREATE TABLE aliases(key TEXT NOT NULL, card_id TEXT NOT NULL);
CREATE INDEX idx_aliases_key ON aliases(key);
CREATE TABLE links(
    card_id TEXT NOT NULL,
    direction TEXT NOT NULL,
    predicate TEXT NOT NULL,
    other TEXT NOT NULL
);
CREATE INDEX idx_links_card ON links(card_id, direction);
CREATE TABLE postings(token TEXT NOT NULL, card_id TEXT NOT NULL, tf INTEGER NOT NULL);
CREATE INDEX idx_postings_token ON postings(token, card_id, tf);
"""


def write_sqlite(vault_root: Path, idx: dict[str, Any], *, index_dir: str = "_index") -> Path:
    """从内存索引产出 sqlite 缓存；先写临时文件再原子替换，避免半成品。"""
    out_dir = vault_root / index_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / SQLITE_FILE
    tmp = out_dir / (SQLITE_FILE + ".tmp")
    tmp.unlink(missing_ok=True)

    conn = sqlite3.connect(tmp)
    try:
        conn.executescript(_SCHEMA)
        meta = idx["meta"]
        doclen: dict[str, int] = meta["doclen"]
        conn.executemany(
            "INSERT INTO meta(key, value) VALUES (?, ?)",
            [
                ("schema", _SCHEMA_VERSION),
                ("cards", str(meta["cards"])),
                ("avgdl", str(meta["avgdl"])),
            ],
        )
        conn.executemany(
            "INSERT INTO catalog(card_id, entry, doclen) VALUES (?, ?, ?)",
            [
                (cid, json.dumps(entry, ensure_ascii=False, sort_keys=True), doclen.get(cid, 0))
                for cid, entry in idx["catalog"].items()
            ],
        )
        conn.executemany(
            "INSERT INTO aliases(key, card_id) VALUES (?, ?)",
            [
                (key, cid)
                for key, ids in idx["aliases"].items()
                for cid in ids
            ],
        )
        link_rows: list[tuple[str, str, str, str]] = []
        for cid, edges in idx["links"]["out"].items():
            link_rows.extend((cid, "out", e["predicate"], e["to"]) for e in edges)
        for cid, edges in idx["links"]["in"].items():
            link_rows.extend((cid, "in", e["predicate"], e["from"]) for e in edges)
        conn.executemany(
            "INSERT INTO links(card_id, direction, predicate, other) VALUES (?, ?, ?, ?)",
            link_rows,
        )
        conn.executemany(
            "INSERT INTO postings(token, card_id, tf) VALUES (?, ?, ?)",
            [
                (token, cid, tf)
                for token, by_card in idx["inverted"].items()
                for cid, tf in by_card.items()
            ],
        )
        conn.commit()
    finally:
        conn.close()
    tmp.replace(final)
    return final


class SqliteIndexBackend:
    """只读查询端：按需取条目/倒排/链接，不整库载入。"""

    name = "sqlite"

    def __init__(self, path: Path) -> None:
        if not Path(path).is_file():
            raise FileNotFoundError(f"sqlite 索引不存在：{path}（先运行 vault index）")
        self._conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self._entry_cache: dict[str, dict[str, Any] | None] = {}
        self._alias_keys: list[str] | None = None
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'cards'"
        ).fetchone()
        avg = self._conn.execute("SELECT value FROM meta WHERE key = 'avgdl'").fetchone()
        self._n_docs = int(row[0]) if row else 0
        self._avgdl = float(avg[0]) if avg else 0.0

    def close(self) -> None:
        self._conn.close()

    def entry(self, card_id: str) -> dict[str, Any] | None:
        if card_id not in self._entry_cache:
            row = self._conn.execute(
                "SELECT entry FROM catalog WHERE card_id = ?", (card_id,)
            ).fetchone()
            self._entry_cache[card_id] = json.loads(row[0]) if row else None
        return self._entry_cache[card_id]

    def alias_ids(self, key: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT card_id FROM aliases WHERE key = ? ORDER BY rowid", (key,)
        ).fetchall()
        return [r[0] for r in rows]

    def alias_keys(self) -> list[str]:
        if self._alias_keys is None:
            rows = self._conn.execute(
                "SELECT key FROM aliases GROUP BY key ORDER BY MIN(rowid)"
            ).fetchall()
            self._alias_keys = [r[0] for r in rows]
        return list(self._alias_keys)

    def postings(self, tokens: list[str]) -> dict[str, dict[str, int]]:
        if not tokens:
            return {}
        placeholders = ",".join("?" for _ in tokens)
        rows = self._conn.execute(
            f"SELECT token, card_id, tf FROM postings WHERE token IN ({placeholders})",
            tokens,
        ).fetchall()
        out: dict[str, dict[str, int]] = {}
        for token, cid, tf in rows:
            out.setdefault(token, {})[cid] = tf
        return out

    def doc_stats(self) -> tuple[int, float]:
        return self._n_docs, self._avgdl

    def doclen(self, card_id: str) -> int:
        row = self._conn.execute(
            "SELECT doclen FROM catalog WHERE card_id = ?", (card_id,)
        ).fetchone()
        return int(row[0]) if row else 0

    def links(self, card_id: str) -> dict[str, list[dict[str, str]]]:
        rows = self._conn.execute(
            "SELECT direction, predicate, other FROM links WHERE card_id = ? ORDER BY rowid",
            (card_id,),
        ).fetchall()
        out: dict[str, list[dict[str, str]]] = {"out": [], "in": []}
        for direction, predicate, other in rows:
            key = "to" if direction == "out" else "from"
            out[direction].append({"predicate": predicate, key: other})
        return out
