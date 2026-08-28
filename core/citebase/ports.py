"""端口定义（六边形架构）：core 定义协议，外围实现，运行时装配。

M1 落地三个端口：SourceAdapter / Extractor / LlmProvider；M4 落地 IndexBackend。
VaultResolver（M5）按里程碑再落，签名以架构文档为准。
core 自身不依赖任何 LLM SDK；LlmProvider 只被 compiler 子包调用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from citebase.model import Pack

# ---------- L0：源适配 ----------


@runtime_checkable
class SourceAdapter(Protocol):
    """「有修订号、能检测变更、能取内容」的东西。"""

    name: str

    def resolve(self) -> str:
        """规范化并校验来源位置；不存在时抛 FileNotFoundError。"""
        ...

    def revision(self) -> str:
        """可比较相等性的修订号（如 sha256:…）。"""
        ...

    def changed_since(self, revision: str) -> bool | None:
        """None = 无法判断（调用方必须按「已变更」处理，宁可多审）。"""
        ...

    def fetch(self, originals_dir: Path) -> list[Path]:
        """把原件拷贝进 sources/<id>/originals/（原件不动、派生另存）。"""
        ...


# ---------- L0：联邦解析（M5） ----------


@runtime_checkable
class VaultResolver(Protocol):
    """把依赖声明解析为本地目录（M5 联邦）。

    git 实现克隆/检出到 ``_deps/<vault-id>/``；path 实现直接指向本地目录。
    鉴权全权交给 git 凭据体系，Citebase 不自建。
    """

    name: str

    def resolve(self, vault_root: Path, dep_id: str) -> Path:
        """返回依赖 vault 的本地根目录；解析失败抛 ValueError / FileNotFoundError。"""
        ...

    def resolved_rev(self, vault_root: Path, dep_id: str) -> str:
        """锁定写入 vault.lock 的修订标识（git 为 commit sha；path 为 'local-path'）。"""
        ...


# ---------- L2：索引后端（M4） ----------


@runtime_checkable
class IndexBackend(Protocol):
    """检索漏斗的数据访问端口：换后端只改性能，不改四工具行为。

    memory（进程内 dict）与 sqlite（``_index/index.sqlite``）两个实现必须对同一
    索引产出**逐分一致**的检索结果（含得分与排序）——对照测试是验收线。
    """

    name: str

    def entry(self, card_id: str) -> dict[str, Any] | None:
        """catalog 条目（name/kind/summary/status/tags/aliases/claims/…）。"""
        ...

    def alias_ids(self, key: str) -> list[str]:
        """精确别名命中（key 已 casefold）。"""
        ...

    def alias_keys(self) -> list[str]:
        """全部别名键，顺序 = 索引构建顺序（图跳与建议的近似锚点池）。"""
        ...

    def postings(self, tokens: list[str]) -> dict[str, dict[str, int]]:
        """token → {card_id: 加权 tf}，只返回出现过的 token。"""
        ...

    def doc_stats(self) -> tuple[int, float]:
        """(文档数, 平均文档长度)。"""
        ...

    def doclen(self, card_id: str) -> int: ...

    def links(self, card_id: str) -> dict[str, list[dict[str, str]]]:
        """{"out": [{predicate,to}...], "in": [{predicate,from}...]}，顺序同构建。"""
        ...


# ---------- L1：抽取 ----------


@dataclass
class ExtractedText:
    """一份派生物文本与其解析置信度。"""

    text: str
    confidence: float


@runtime_checkable
class Extractor(Protocol):
    name: str  # 形如 plain@1；连同版本写入源 meta（可追责）

    def can_extract(self, original: Path) -> bool: ...

    def extract(self, original: Path) -> ExtractedText: ...


# ---------- L1：LLM 提议（草案对象 = 端口的公共语言） ----------


@dataclass
class DraftSpan:
    """草案里的源定位：只有 loc，没有哈希——哈希由编译器实算，绝不信任 LLM 报数。"""

    source: str
    loc: str


@dataclass
class DraftClaim:
    id: str
    text: str
    spans: list[DraftSpan] = field(default_factory=list)  # 允许为空：机器闸负责拦截


@dataclass
class DraftLink:
    predicate: str
    to: str


@dataclass
class DraftCard:
    kind: str
    name: str
    summary: str
    body: str
    aliases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    links: list[DraftLink] = field(default_factory=list)
    claims: list[DraftClaim] = field(default_factory=list)


@dataclass
class PromptSpec:
    """prompt 版本与内容哈希，写入 _compile_log 供回放对照。"""

    id: str
    sha256: str
    text: str


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, other: TokenUsage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens


@dataclass
class CardDigest:
    """既有卡的最小画像，供 propose/merge 对齐用。"""

    id: str
    kind: str
    name: str
    aliases: list[str]
    summary: str


@dataclass
class ProposeRequest:
    source_id: str
    derivatives: dict[str, str]  # 相对 loc 前缀（如 extracted/text.md）→ 文本
    pack: Pack
    existing: list[CardDigest]
    prompt: PromptSpec


@dataclass
class ProposeResponse:
    drafts: list[DraftCard]
    usage: TokenUsage = field(default_factory=TokenUsage)


@dataclass
class MergeRequest:
    draft: DraftCard
    existing_id: str
    existing_claims: list[tuple[str, str]]  # (claim_id, text)


@dataclass
class MergeDecision:
    verdict: str  # merge | new | unsure（unsure 一律升级人工）
    reason: str = ""


@dataclass
class ContradictRequest:
    existing_id: str
    existing_claims: list[tuple[str, str]]
    draft_claims: list[tuple[str, str]]
    prompt: PromptSpec


@dataclass
class ConflictPair:
    existing_claim: str
    draft_claim: str
    topic: str


@dataclass
class ContradictDecision:
    conflicts: list[ConflictPair] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)


@runtime_checkable
class LlmProvider(Protocol):
    """只有 compiler 会调用；core 的 lint / index / search 全程无 LLM。"""

    name: str

    def describe(self) -> dict[str, Any]:
        """写入 _compile_log 的 model 段（provider / name / temperature …）。"""
        ...

    def propose(self, request: ProposeRequest) -> ProposeResponse: ...

    def merge_judge(self, request: MergeRequest) -> MergeDecision: ...

    def contradict_judge(self, request: ContradictRequest) -> ContradictDecision: ...
