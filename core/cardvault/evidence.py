"""执行证据事件（M3）：解析、校验、登记为源。

EvidenceEvent 是一种 Source（``adapter: evidence``）——经验知识的出处就是那次真实
运行（对象模型 §9）。事件不可变：登记原件 = ``evidence/*.jsonl`` 里的原始行，
revision = 原件字节哈希；派生物 ``extracted/event.txt`` 是规范化的逐字段单行渲染，
论断 span 按行绑定其中（回流通道校验见威胁模型 §2-③：结构化字段 + 限长 +
注入扫描在草案阶段统一执行）。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

EVIDENCE_DIR = "evidence"
EVENT_ORIGINAL = "originals/event.json"
EVENT_DERIVATIVE = "extracted/event.txt"
EXTRACTOR_NAME = "evidence@1"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceSystem(_StrictModel):
    name: str = Field(min_length=1, max_length=100)
    version: str | None = Field(default=None, max_length=50)


class ConsultedCard(_StrictModel):
    card_id: str = Field(pattern=r"^(?:[a-z0-9-]+::)?card-[a-z0-9]+(-[a-z0-9]+)*$")
    claims_used: list[Annotated[str, Field(pattern=r"^c[0-9]+$")]] = []


class EvidenceOutcome(_StrictModel):
    status: Literal["success", "failure", "partial"]
    metrics: dict[str, float | int | str | bool] = {}


class EvidenceFailure(_StrictModel):
    category: str | None = Field(default=None, max_length=100)
    summary: str | None = Field(default=None, max_length=2000)
    root_cause_hypothesis: str | None = Field(default=None, max_length=2000)


class EvidenceEvent(_StrictModel):
    """spec/evidence-event.schema.json v0.1 的运行时形态。"""

    event_id: str = Field(pattern=r"^evt-[a-z0-9]+([-.][a-z0-9]+)*$")
    ts: datetime
    system: EvidenceSystem
    task_ref: str | None = Field(default=None, max_length=200)
    cards_consulted: list[ConsultedCard] = []
    outcome: EvidenceOutcome
    failure: EvidenceFailure | None = None


@dataclass
class LoadedEvent:
    event: EvidenceEvent
    file: str  # vault 内相对路径（POSIX）
    line: int  # 1-based
    raw: str  # 原始 JSONL 行（不含换行符）


@dataclass
class EvidenceLoadResult:
    events: list[LoadedEvent] = field(default_factory=list)
    invalid: list[dict[str, Any]] = field(default_factory=list)  # {file, line, error}
    duplicates: list[str] = field(default_factory=list)  # 重复 event_id（后到者被跳过）


def load_events(vault_root: Path) -> EvidenceLoadResult:
    """读取 ``evidence/*.jsonl`` 全部事件；坏行记入 invalid，不中断整体装载。"""
    result = EvidenceLoadResult()
    evidence_dir = vault_root / EVIDENCE_DIR
    if not evidence_dir.is_dir():
        return result
    seen: set[str] = set()
    for file in sorted(evidence_dir.glob("*.jsonl")):
        rel = f"{EVIDENCE_DIR}/{file.name}"
        for line_no, raw in enumerate(
            file.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not raw.strip():
                continue
            try:
                event = EvidenceEvent.model_validate(json.loads(raw))
            except (json.JSONDecodeError, ValidationError) as e:
                result.invalid.append(
                    {"file": rel, "line": line_no, "error": _first_error_line(str(e))}
                )
                continue
            if event.event_id in seen:
                result.duplicates.append(event.event_id)
                continue
            seen.add(event.event_id)
            result.events.append(LoadedEvent(event=event, file=rel, line=line_no, raw=raw))
    result.events.sort(key=lambda le: (le.event.ts, le.event.event_id))
    return result


def _first_error_line(message: str) -> str:
    return message.splitlines()[0][:200]


# ---------- 规范化渲染（派生物是论断 span 的绑定目标，行号必须确定） ----------


def _oneline(text: str) -> str:
    """自由文本单行化：换行与连续空白折叠为单空格，保证行寻址稳定。"""
    return " ".join(text.split())


def render_event_text(event: EvidenceEvent) -> tuple[str, dict[str, int]]:
    """逐字段单行渲染事件；返回 (文本, 字段 → 1-based 行号)。"""
    lines: list[str] = []
    linemap: dict[str, int] = {}

    def put(key: str, value: str) -> None:
        lines.append(f"{key}: {_oneline(value)}")
        linemap[key] = len(lines)

    put("event_id", event.event_id)
    put("ts", event.ts.isoformat())
    system = event.system.name
    if event.system.version:
        system += f"@{event.system.version}"
    put("system", system)
    if event.task_ref:
        put("task_ref", event.task_ref)
    put("outcome.status", event.outcome.status)
    for key in sorted(event.outcome.metrics):
        put(f"outcome.metrics.{key}", str(event.outcome.metrics[key]))
    for i, card in enumerate(event.cards_consulted):
        rendered = card.card_id
        if card.claims_used:
            rendered += "#" + ",".join(card.claims_used)
        put(f"cards_consulted[{i}]", rendered)
    if event.failure is not None:
        if event.failure.category:
            put("failure.category", event.failure.category)
        if event.failure.summary:
            put("failure.summary", event.failure.summary)
        if event.failure.root_cause_hypothesis:
            put("failure.root_cause_hypothesis", event.failure.root_cause_hypothesis)
    return "\n".join(lines) + "\n", linemap


def claim_loc(event: EvidenceEvent) -> str:
    """论断 span 的绑定行：优先 failure.summary，其次 failure.category，最后 outcome.status。"""
    _, linemap = render_event_text(event)
    for key in ("failure.summary", "failure.category", "outcome.status"):
        if key in linemap:
            line = linemap[key]
            return f"{EVENT_DERIVATIVE}#L{line}-L{line}"
    raise AssertionError("outcome.status 必然存在")  # pragma: no cover


# ---------- 事件登记为源（幂等；事件不可变） ----------


def _revision_of(stored: bytes) -> str:
    return f"sha256:{hashlib.sha256(stored).hexdigest()}"


def source_registered(vault_root: Path, event_id: str) -> bool:
    return (vault_root / "sources" / event_id / "meta.yaml").is_file()


def register_event_source(vault_root: Path, loaded: LoadedEvent) -> bool:
    """把事件登记为 ``sources/<event_id>/``；已登记则跳过（返回 False）。

    原件不动、派生另存：originals/event.json 保存原始 JSONL 行，
    extracted/event.txt 是规范化渲染（置信度 1.0——事件是结构化投递，无解析损失）。
    """
    if source_registered(vault_root, loaded.event.event_id):
        return False
    source_dir = vault_root / "sources" / loaded.event.event_id
    stored = (loaded.raw + "\n").encode("utf-8")
    original = source_dir / EVENT_ORIGINAL
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(stored)

    text, _ = render_event_text(loaded.event)
    derivative = source_dir / EVENT_DERIVATIVE
    derivative.parent.mkdir(parents=True, exist_ok=True)
    derivative.write_text(text, encoding="utf-8", newline="\n")

    meta = {
        "id": loaded.event.event_id,
        "adapter": "evidence",
        "uri": f"{loaded.file}#L{loaded.line}",
        "revision": _revision_of(stored),
        "fetched_at": datetime.now(UTC).isoformat(),
        "extractions": [
            {"path": EVENT_DERIVATIVE, "extractor": EXTRACTOR_NAME, "confidence": 1.0}
        ],
        "license": "internal",
    }
    (source_dir / "meta.yaml").write_text(
        yaml.safe_dump(meta, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
        newline="\n",
    )
    return True


def evidence_source_changed(vault_root: Path, source_id: str, revision: str) -> bool | None:
    """漂移通道 A 的 evidence 特化：事件不可变，重算登记原件哈希即可判定。

    原件缺失 → None（按已变更处理）；被篡改 → True。
    """
    original = vault_root / "sources" / source_id / EVENT_ORIGINAL
    if not original.is_file():
        return None
    return _revision_of(original.read_bytes()) != revision
