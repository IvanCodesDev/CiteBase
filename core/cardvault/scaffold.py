"""``vault init``：脚手架一个空 vault（vault.yaml + 内置 generic 包 + CI 即治理模板）。"""

from __future__ import annotations

from pathlib import Path

_VAULT_YAML = """\
name: {name}
packs: [generic]
low_confidence_threshold: 0.6
# 编译（M1）需要 LLM 端点时取消注释；密钥走环境变量，不落盘：
# llm:
#   provider: openai-compat
#   base_url: https://api.example.com/v1
#   model: your-model
#   api_key_env: CARDVAULT_API_KEY
# 卡片上万后启用 sqlite 检索缓存（vault index 重建；行为与 memory 逐分一致）：
# index_backend: sqlite
"""

#: 内置 generic 包：概念 / 方法 / 陷阱。领域词汇只准住在 Pack（L-CORE-1），
#: generic 保持零领域词，tag 词表留给使用者。
_GENERIC_PACK = """\
name: generic
version: 0.1.0
description: 通用基础包：概念 / 方法 / 陷阱
card_kinds:
  - kind: concept
    body_sections: [是什么, 何时用, 怎么用, 边界与陷阱, 关联]
  - kind: method
    body_sections: [是什么, 何时用, 怎么用, 边界与陷阱, 关联]
  - kind: pitfall
    body_sections: [现象, 根因, 规避, 触发条件, 关联]
link_predicates: [related_to, refines, pitfall, cites, used_in]
tag_vocab: {}
"""

_GOLDEN_STUB = """\
# golden set：检索评测用例（M0 验收线：每个 vault ≥20 条，命中率 ≥ 0.8）
# 条目形如：
# - q: 查询
#   expect: [card-xxx]
#   expect_rank: 3
[]
"""

#: CI 即治理（quality-gates §3）：坏账本红灯，不静默腐烂。
_CI_TEMPLATE = """\
name: vault-ci
on: [push, pull_request]
jobs:
  govern:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install cardvault
      - run: vault lint
      - run: vault index --check
      - run: vault eval --min-hit 0.8
      - run: vault eval --faithfulness --max-unfaithful 0.02
      - run: vault drift --report --warn-threshold 0.05
"""

_KEEP_DIRS = ("cards", "sources", "refs", "evidence")


def init_vault(target: Path, *, name: str | None = None) -> list[str]:
    """创建空 vault。返回创建的相对路径清单；目标已是 vault 时报错。"""
    target = target.resolve()
    if (target / "vault.yaml").exists():
        raise ValueError(f"目标已是一个 vault：{target / 'vault.yaml'}")
    target.mkdir(parents=True, exist_ok=True)
    vault_name = name or target.name

    created: list[str] = []

    def write(rel: str, content: str) -> None:
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        created.append(rel)

    write("vault.yaml", _VAULT_YAML.format(name=vault_name))
    write("packs/generic/pack.yaml", _GENERIC_PACK)
    write("evals/golden.yaml", _GOLDEN_STUB)
    write(".github/workflows/vault-ci.yml", _CI_TEMPLATE)
    for rel in _KEEP_DIRS:
        (target / rel).mkdir(parents=True, exist_ok=True)
        write(f"{rel}/.gitkeep", "")
    return created
