"""为手工撰写的卡片回填 span_sha256 占位哈希。

只填充值为 PENDING 的占位符；已有哈希一律不改写——哈希不一致由
``vault lint``（L-PROV-2）报告并人工核查，本工具不得掩盖源漂移。

用法（仓库根目录）::

    python scripts/refresh_span_hashes.py examples/citebase-self
"""

from __future__ import annotations

import sys
from pathlib import Path

from citebase import spanhash
from citebase.vault import Vault

PLACEHOLDER = "PENDING"


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    vault = Vault.load(root)
    total = 0
    for card in vault.cards.values():
        path = vault.root / card.path
        text = path.read_text(encoding="utf-8")
        if f"span_sha256: {PLACEHOLDER}" not in text:
            continue
        filled = 0
        # 替换按文件出现顺序进行，与 frontmatter 中 claims/sources 的声明顺序一致。
        for claim in card.meta.claims:
            for span in claim.sources:
                if span.span_sha256 != PLACEHOLDER:
                    continue
                digest = spanhash.compute(vault, span)
                text = text.replace(
                    f"span_sha256: {PLACEHOLDER}", f"span_sha256: {digest}", 1
                )
                filled += 1
        path.write_text(text, encoding="utf-8")
        total += filled
        print(f"{card.path}: 回填 {filled} 个哈希")
    print(f"共回填 {total} 个 span 哈希")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
