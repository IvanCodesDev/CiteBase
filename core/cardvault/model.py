"""核心对象模型（pydantic v2）。

内核只认识 Source / Card / Claim / Link 四个抽象与内置 contradiction 卡类；
领域语义住在 Ontology Pack（L-CORE-1：内核零领域词）。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

KERNEL_KIND_CONTRADICTION = "contradiction"
#: 内核保留谓词：supersedes 有副作用（把目标卡置为 superseded），任何 Pack 下都合法。
KERNEL_PREDICATES = frozenset({"supersedes"})
#: 终态：字段冻结，不得被 active 卡链接引用（supersedes 谓词除外）。
TERMINAL_STATUSES = frozenset({"superseded", "retired"})
#: 检索默认隐藏的状态（宁可少说话，不说过期话）。
DEFAULT_HIDDEN_STATUSES = frozenset({"suspect", "superseded", "retired"})
#: 跨库引用分隔符（M5 联邦），本地 id 禁用。
FEDERATION_SEPARATOR = "::"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceSpan(StrictModel):
    """论断与源片段的绑定：验证链的最小锚点。"""

    source: str
    loc: str
    span_sha256: str


class Claim(StrictModel):
    """论断：可独立验证的最小事实单元（验证单元）。"""

    id: str
    text: str
    sources: list[SourceSpan] = Field(min_length=1)
    confidence: float | None = None
    low_confidence: bool = False
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    status: str = "active"  # active | superseded | contested


class Link(StrictModel):
    predicate: str
    to: str


class Verification(StrictModel):
    source: str
    revision: str
    at: date


class CardMeta(StrictModel):
    """卡片 frontmatter（读取单元）。结构契约见 spec/card.schema.json。"""

    id: str
    kind: str
    name: str
    summary: str
    aliases: list[str] = []
    tags: list[str] = []
    links: list[Link] = []
    claims: list[Claim] = []
    version: int = 1
    status: str = "active"  # active | suspect | superseded | retired | contested
    verified_against: list[Verification] = []
    injection_risk: bool = False
    schema_version: str = "0.1"


class Card(StrictModel):
    meta: CardMeta
    body: str
    path: str  # vault 内相对路径（POSIX 风格）


class Extraction(StrictModel):
    path: str
    extractor: str
    confidence: float = 1.0


class SourceMeta(StrictModel):
    """源登记：任何「有修订号、能检测变更、能取内容」的东西。"""

    id: str
    adapter: str
    uri: str
    revision: str
    fetched_at: datetime | None = None
    extractions: list[Extraction] = []
    license: str = "unknown"


class CardKindDef(StrictModel):
    kind: str
    body_sections: list[str]


class Pack(StrictModel):
    """Ontology Pack：纯声明，不含可执行代码。"""

    name: str
    version: str
    description: str = ""
    card_kinds: list[CardKindDef]
    link_predicates: list[str] = []
    tag_vocab: dict[str, list[str]] = {}


class LlmSettings(StrictModel):
    """vault.yaml 的 llm 段：真实编译所需的 OpenAI 兼容端点（密钥走环境变量，不落盘）。"""

    provider: str = "openai-compat"
    base_url: str = ""
    model: str = ""
    api_key_env: str = "CARDVAULT_API_KEY"
    temperature: float = 0.0
    timeout_seconds: float = 120.0


class ReviewSettings(StrictModel):
    """人工抽查闸的自适应抽样参数（compile-pipeline §3）。"""

    #: 抽样率阶梯：新源 100%，历史越好越往后走。
    rates: list[float] = Field(default_factory=lambda: [1.0, 0.5, 0.25, 0.1])
    #: 「连续两批通过率 ≥ good_pass_rate」才允许降档。
    good_pass_rate: float = 0.9
    #: 「任一批驳回率 > bad_reject_rate」立即回到 100%。
    bad_reject_rate: float = 0.3


class DepSpec(StrictModel):
    """一条知识依赖声明（M5 联邦）：git 锁定到 rev，或本地路径（示例/单仓多库）。

    不存在浮动的 latest：git 依赖必须显式给 rev；升级依赖 = 改 rev + ``vault deps
    sync`` = 一次 PR。只支持一层依赖（不解析传递依赖，防依赖地狱）。
    """

    git: str | None = None
    path: str | None = None
    rev: str | None = None

    @model_validator(mode="after")
    def _check_source(self) -> DepSpec:
        if (self.git is None) == (self.path is None):
            raise ValueError("依赖必须且只能声明 git 或 path 之一")
        if self.git is not None and not self.rev:
            raise ValueError("git 依赖必须锁定 rev（不存在浮动的 latest）")
        return self


class VaultConfig(StrictModel):
    """vault.yaml。"""

    name: str = "vault"
    packs: list[str] = []
    low_confidence_threshold: float = 0.6
    llm: LlmSettings | None = None
    review: ReviewSettings = Field(default_factory=ReviewSettings)
    #: 检索后端：memory（每次进程内重建，永远新鲜）| sqlite（_index/index.sqlite
    #: 加速缓存，10k 卡级用；由 vault index 重建）。换后端不改四工具行为。
    index_backend: Literal["memory", "sqlite"] = "memory"
    #: 知识依赖（M5 联邦）：vault-id → 来源与锁定。不声明 deps 的 vault
    #: 行为与 M0 完全一致（联邦是可选层）。
    deps: dict[str, DepSpec] = {}
