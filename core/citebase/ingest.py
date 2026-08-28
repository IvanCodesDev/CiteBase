"""源登记（L0）：adapter.fetch 原件 + extractor 产派生物 + 写 meta.yaml。

全程无 LLM。原件不动、派生另存；抽取器名与置信度入档（可追责）。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml

from citebase.extractors import default_extractors
from citebase.model import SourceMeta
from citebase.ports import Extractor, SourceAdapter

_SLUG_RE = re.compile(r"[a-z0-9]+")


def slugify(text: str) -> str:
    """kebab-case ASCII slug；无 ASCII 内容时退化为内容哈希前 8 位。"""
    runs = _SLUG_RE.findall(text.lower())
    slug = "-".join(runs)
    if slug:
        return slug
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def derivative_relpath(rel: Path, *, single: bool) -> str:
    """派生物落点：单原件源固定 extracted/text.md；多原件保持相对路径（非 .md 追加后缀防碰撞）。"""
    if single:
        return "extracted/text.md"
    posix = rel.as_posix()
    if posix.endswith(".md"):
        return f"extracted/{posix}"
    return f"extracted/{posix}.md"


@dataclass
class IngestResult:
    meta: SourceMeta
    source_dir: Path
    derivatives: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # 无抽取器可处理的原件


def _pick_extractor(extractors: list[Extractor], original: Path) -> Extractor | None:
    for extractor in extractors:
        if extractor.can_extract(original):
            return extractor
    return None


def ingest(
    vault_root: Path,
    adapter: SourceAdapter,
    *,
    source_id: str | None = None,
    license_: str = "unknown",
    force: bool = False,
    extractors: list[Extractor] | None = None,
) -> IngestResult:
    uri = adapter.resolve()
    resolved_id = source_id or f"src-{slugify(Path(uri).stem)}"
    source_dir = vault_root / "sources" / resolved_id
    if source_dir.exists() and not force:
        raise ValueError(f"源已存在：{resolved_id}（用 --force 重新登记）")

    originals_dir = source_dir / "originals"
    originals = adapter.fetch(originals_dir)
    if not originals:
        raise ValueError(f"源没有任何可登记的原件：{uri}")

    chosen = extractors if extractors is not None else default_extractors()
    single = len(originals) == 1
    extractions: list[dict[str, object]] = []
    derivatives: list[str] = []
    skipped: list[str] = []
    for original in originals:
        extractor = _pick_extractor(chosen, original)
        rel = original.relative_to(originals_dir)
        if extractor is None:
            skipped.append(rel.as_posix())
            continue
        extracted = extractor.extract(original)
        relpath = derivative_relpath(rel, single=single)
        dest = source_dir / relpath
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(extracted.text, encoding="utf-8", newline="\n")
        extractions.append(
            {"path": relpath, "extractor": extractor.name, "confidence": extracted.confidence}
        )
        derivatives.append(relpath)

    if not extractions:
        raise ValueError(f"没有抽取器能处理该源的任何原件（跳过 {len(skipped)} 个）：{uri}")

    meta = SourceMeta.model_validate(
        {
            "id": resolved_id,
            "adapter": adapter.name,
            "uri": uri,
            "revision": adapter.revision(),
            "fetched_at": datetime.now(UTC).isoformat(),
            "extractions": extractions,
            "license": license_,
        }
    )
    payload = meta.model_dump(mode="json")
    (source_dir / "meta.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
        newline="\n",
    )
    return IngestResult(
        meta=meta, source_dir=source_dir, derivatives=derivatives, skipped=skipped
    )
