"""检索日志与知识缺口清单（M3）。

匿名化记录：只存查询文本与命中情况，不关联任何用户身份（威胁模型 §5）。
高频未命中查询 = 建卡待办；与 golden 评测的未命中样例合并去重
（quality-gates §5：未命中样例是缺口清单的一部分）。
日志是尽力而为的旁路：写入失败绝不打断检索。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cardvault.retrieve import SearchResult

LOG_DIR = "_logs"
LOG_FILE = "retrieval.jsonl"


def log_path(vault_root: Path) -> Path:
    return vault_root / LOG_DIR / LOG_FILE


def log_search(
    vault_root: Path, query: str, result: SearchResult, *, surface: str
) -> None:
    """追加一条检索记录（surface: cli | mcp）。旁路失败静默忽略。"""
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "query": query,
        "hit": result.hit,
        "first": result.hits[0].id if result.hits else None,
        "surface": surface,
    }
    try:
        path = log_path(vault_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:  # pragma: no cover - 日志绝不打断检索
        pass


def read_log(vault_root: Path) -> list[dict[str, Any]]:
    path = log_path(vault_root)
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # 坏行跳过：日志是旁路不是台账
    return records


def gap_report(
    vault_root: Path,
    *,
    golden_misses: list[dict[str, Any]] | None = None,
    min_count: int = 1,
) -> list[dict[str, Any]]:
    """合并「检索日志未命中」与「golden 未命中」，按频次降序输出缺口清单。"""
    counts: dict[str, dict[str, Any]] = {}

    def bump(query: str, origin: str) -> None:
        normalized = " ".join(query.split())
        if not normalized:
            return
        key = normalized.casefold()
        entry = counts.setdefault(
            key, {"query": normalized, "count": 0, "origins": set()}
        )
        entry["count"] += 1
        entry["origins"].add(origin)

    for record in read_log(vault_root):
        if record.get("hit") is False and record.get("query"):
            bump(str(record["query"]), f"log:{record.get('surface', 'unknown')}")
    for miss in golden_misses or []:
        if miss.get("q"):
            bump(str(miss["q"]), "golden")

    gaps = [
        {
            "query": entry["query"],
            "count": entry["count"],
            "origins": sorted(entry["origins"]),
        }
        for entry in counts.values()
        if entry["count"] >= min_count
    ]
    gaps.sort(key=lambda g: (-g["count"], g["query"]))
    return gaps
