from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from helpers import EXAMPLE_ROOT, make_vault


@pytest.fixture(scope="session", autouse=True)
def _clean_example_logs() -> Iterator[None]:
    """对示例 vault 的检索会写 _logs/ 旁路日志；会话结束后清理，保持示例纯净。"""
    yield
    shutil.rmtree(EXAMPLE_ROOT / "_logs", ignore_errors=True)


@pytest.fixture()
def example_root() -> Path:
    return EXAMPLE_ROOT


@pytest.fixture()
def mini_vault(tmp_path: Path) -> Path:
    return make_vault(tmp_path / "vault")
