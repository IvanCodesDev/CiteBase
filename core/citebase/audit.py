"""审计台账：``_audit/audit.jsonl``，append-only，不可修改不可删除。

记录「谁在何时因何动了哪条知识」：编译入库、人工审批、驳回、裁决、复核。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

AUDIT_DIR = "_audit"
AUDIT_FILE = "audit.jsonl"


def append_audit(vault_root: Path, action: str, actor: str, detail: dict[str, Any]) -> None:
    audit_dir = vault_root / AUDIT_DIR
    audit_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "action": action,
        "actor": actor,
        **detail,
    }
    line = json.dumps(record, ensure_ascii=False, sort_keys=False)
    with (audit_dir / AUDIT_FILE).open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(line + "\n")


def read_audit(vault_root: Path) -> list[dict[str, Any]]:
    file = vault_root / AUDIT_DIR / AUDIT_FILE
    if not file.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in file.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records
