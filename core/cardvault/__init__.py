"""CardVault：编译式知识库内核（M0：无 LLM 的 lint / 索引 / 检索）。"""

from cardvault.model import (
    Card,
    CardMeta,
    Claim,
    Link,
    Pack,
    SourceMeta,
    SourceSpan,
    VaultConfig,
)
from cardvault.vault import Vault

__version__ = "0.1.0.dev0"

__all__ = [
    "Card",
    "CardMeta",
    "Claim",
    "Link",
    "Pack",
    "SourceMeta",
    "SourceSpan",
    "Vault",
    "VaultConfig",
    "__version__",
]
