"""prompt 模板加载：版本化文件 + 内容哈希，写入 _compile_log 供回放对照。"""

from __future__ import annotations

import hashlib
from importlib import resources

from citebase.ports import PromptSpec


def load_prompt(stage: str, variant: str = "v1") -> PromptSpec:
    name = f"{stage}.{variant}.prompt.md"
    text = (
        resources.files("citebase").joinpath(f"compiler/prompts/{name}").read_text("utf-8")
    )
    return PromptSpec(
        id=name,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        text=text,
    )
