"""Vault 加载器：读取 vault.yaml、packs、cards、sources。

加载是宽容的：单个文件解析失败记入 load_errors 由 lint 报告，不中断整体加载。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

from cardvault import frontmatter
from cardvault.model import (
    KERNEL_KIND_CONTRADICTION,
    KERNEL_PREDICATES,
    Card,
    CardMeta,
    Pack,
    SourceMeta,
    VaultConfig,
)


@dataclass
class LoadError:
    path: str
    message: str


@dataclass
class Vault:
    root: Path
    config: VaultConfig
    packs: dict[str, Pack] = field(default_factory=dict)
    cards: dict[str, Card] = field(default_factory=dict)
    sources: dict[str, SourceMeta] = field(default_factory=dict)
    load_errors: list[LoadError] = field(default_factory=list)

    # ---------- 加载 ----------

    @classmethod
    def load(cls, root: Path | str) -> Vault:
        root = Path(root).resolve()
        config_path = root / "vault.yaml"
        if not config_path.is_file():
            raise FileNotFoundError(f"不是一个 vault：缺少 {config_path}")
        config = VaultConfig.model_validate(
            yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        )
        vault = cls(root=root, config=config)
        vault._load_packs()
        vault._load_sources()
        vault._load_cards()
        return vault

    def _rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def _load_packs(self) -> None:
        for name in self.config.packs:
            pack_path = self.root / "packs" / name / "pack.yaml"
            if not pack_path.is_file():
                self.load_errors.append(
                    LoadError(f"packs/{name}/pack.yaml", "vault.yaml 启用的 Pack 不存在")
                )
                continue
            try:
                data = yaml.safe_load(pack_path.read_text(encoding="utf-8")) or {}
                pack = Pack.model_validate(data)
            except (yaml.YAMLError, ValidationError) as e:
                self.load_errors.append(LoadError(self._rel(pack_path), f"Pack 解析失败：{e}"))
                continue
            self.packs[pack.name] = pack

    def _load_sources(self) -> None:
        sources_dir = self.root / "sources"
        if not sources_dir.is_dir():
            return
        for meta_path in sorted(sources_dir.glob("*/meta.yaml")):
            try:
                data = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
                meta = SourceMeta.model_validate(data)
            except (yaml.YAMLError, ValidationError) as e:
                self.load_errors.append(LoadError(self._rel(meta_path), f"源 meta 解析失败：{e}"))
                continue
            if meta.id in self.sources:
                self.load_errors.append(
                    LoadError(self._rel(meta_path), f"源 id 重复：{meta.id}")
                )
                continue
            self.sources[meta.id] = meta

    def _load_cards(self) -> None:
        cards_dir = self.root / "cards"
        if not cards_dir.is_dir():
            return
        for card_path in sorted(cards_dir.rglob("*.md")):
            rel = self._rel(card_path)
            try:
                doc = frontmatter.load_file(card_path)
                meta = CardMeta.model_validate(doc.meta)
            except (ValueError, yaml.YAMLError, ValidationError) as e:
                self.load_errors.append(LoadError(rel, f"卡片解析失败：{e}"))
                continue
            if meta.id in self.cards:
                self.load_errors.append(
                    LoadError(rel, f"卡片 id 重复：{meta.id}（已加载 {self.cards[meta.id].path}）")
                )
                continue
            self.cards[meta.id] = Card(meta=meta, body=doc.body, path=rel)

    # ---------- 词表 ----------

    def enabled_kinds(self) -> set[str]:
        kinds = {KERNEL_KIND_CONTRADICTION}
        for pack in self.packs.values():
            kinds.update(k.kind for k in pack.card_kinds)
        return kinds

    def enabled_predicates(self) -> set[str]:
        predicates = set(KERNEL_PREDICATES)
        for pack in self.packs.values():
            predicates.update(pack.link_predicates)
        return predicates

    # ---------- 源文件解析 ----------

    def source_file(self, source_id: str, relpath: str) -> Path:
        """解析某个源的派生物文件路径（不校验存在性，由调用方处理）。"""
        return self.root / "sources" / source_id / relpath

    def extraction_confidence(self, source_id: str, relpath: str) -> float | None:
        meta = self.sources.get(source_id)
        if meta is None:
            return None
        for ext in meta.extractions:
            if ext.path == relpath:
                return ext.confidence
        return None
