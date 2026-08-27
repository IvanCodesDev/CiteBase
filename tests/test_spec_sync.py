"""spec/ 是契约事实源；core/cardvault/spec/ 是打包副本——两份必须逐字节一致。"""

from __future__ import annotations

import pytest
from helpers import REPO_ROOT

SPEC_NAMES = ["card.schema.json", "evidence-event.schema.json", "pack.schema.json"]


@pytest.mark.parametrize("name", SPEC_NAMES)
def test_packaged_spec_in_sync(name: str) -> None:
    canonical = (REPO_ROOT / "spec" / name).read_text(encoding="utf-8")
    packaged = (REPO_ROOT / "core" / "cardvault" / "spec" / name).read_text(encoding="utf-8")
    assert canonical == packaged, f"{name}: spec/ 与 core/cardvault/spec/ 不同步"
