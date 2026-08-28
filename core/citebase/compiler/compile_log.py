"""编译留痕：``_compile_log/<run_id>.yaml`` run manifest（compile-pipeline §4）。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

COMPILE_LOG_DIR = "_compile_log"


def next_run_id(vault_root: Path, *, now: datetime | None = None) -> str:
    moment = now or datetime.now(UTC)
    date = moment.strftime("%Y-%m-%d")
    log_dir = vault_root / COMPILE_LOG_DIR
    n = 1
    while (log_dir / f"compile-{date}-{n:03d}.yaml").exists():
        n += 1
    return f"compile-{date}-{n:03d}"


def write_manifest(vault_root: Path, run_id: str, manifest: dict[str, Any]) -> Path:
    log_dir = vault_root / COMPILE_LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{run_id}.yaml"
    path.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
        newline="\n",
    )
    return path


def read_manifest(vault_root: Path, run_id: str) -> dict[str, Any]:
    path = vault_root / COMPILE_LOG_DIR / f"{run_id}.yaml"
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data
