"""lint 引擎：出处硬闸与结构规则（机器执行的治理）。

同一套规则服务三个执行点：编译期机器闸（M1 起）、本地 ``vault lint``、CI。
生效规则：SCHEMA / L-ID-1 / L-PACK-1 / L-PROV-1 / L-PROV-2 / L-PROV-4 /
L-LINK-1 / L-LIFE-1 / L-SUM-1；L-SEC-1 注入扫描（warn）与 L-REF-1 引用白名单
结构检查（M2）；L-FED-1 跨库引用可解析、L-FED-2 终态上游引用（warn）、
L-FED-3 lock 一致性（M5 联邦，替代 M0 的 L-FED-0 占位）。
其余落点：L-IDX-1 在 ``vault index --check``；L-CORE-1 是内核仓库 CI 规则，不在 vault lint。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib import resources
from typing import Any

import jsonschema
import yaml

from citebase import frontmatter, security, spanhash
from citebase.model import (
    FEDERATION_SEPARATOR,
    KERNEL_PREDICATES,
    TERMINAL_STATUSES,
    Card,
)
from citebase.vault import Vault

LEVEL_ERROR = "error"
LEVEL_WARN = "warn"


@dataclass
class Finding:
    rule: str
    level: str
    path: str
    message: str

    def format(self) -> str:
        return f"{self.level.upper():5} {self.rule:9} {self.path}: {self.message}"


def _load_card_schema() -> dict[str, Any]:
    text = resources.files("citebase").joinpath("spec/card.schema.json").read_text("utf-8")
    return json.loads(text)  # type: ignore[no-any-return]


def card_validator() -> jsonschema.Draft202012Validator:
    """卡片 frontmatter 的 schema 校验器；编译期机器闸与 lint 共用同一份。"""
    return jsonschema.Draft202012Validator(_load_card_schema())


class _FederationContext:
    """惰性解析依赖库（M5）：lint 期间每个依赖至多加载一次，无 deps 时零开销。"""

    def __init__(self, vault: Vault) -> None:
        self._vault = vault
        self._lock: dict[str, Any] | None = None
        self._dep_vaults: dict[str, Vault | None] = {}

    @property
    def lock(self) -> dict[str, Any]:
        if self._lock is None:
            from citebase.federation import load_lock

            self._lock = load_lock(self._vault.root)
        return self._lock

    def dep_vault(self, dep_id: str) -> Vault | None:
        if dep_id not in self._dep_vaults:
            from citebase.federation import resolver_for

            spec = self._vault.config.deps.get(dep_id)
            if spec is None:
                self._dep_vaults[dep_id] = None
            else:
                try:
                    root = resolver_for(spec).resolve(self._vault.root, dep_id)
                    self._dep_vaults[dep_id] = Vault.load(root)
                except (FileNotFoundError, ValueError):
                    self._dep_vaults[dep_id] = None
        return self._dep_vaults[dep_id]


def lint_vault(vault: Vault) -> list[Finding]:
    findings: list[Finding] = []

    for err in vault.load_errors:
        findings.append(Finding("LOAD", LEVEL_ERROR, err.path, err.message))

    validator = card_validator()
    kinds = vault.enabled_kinds()
    predicates = vault.enabled_predicates()
    threshold = vault.config.low_confidence_threshold
    fed = _FederationContext(vault)

    for card in vault.cards.values():
        findings.extend(_lint_schema(card, vault, validator))
        findings.extend(_lint_ids(card))
        findings.extend(_lint_kind(card, kinds))
        findings.extend(_lint_claims(card, vault, threshold))
        findings.extend(_lint_links(card, vault, predicates, fed))

    findings.extend(_lint_refs(vault))
    findings.extend(_lint_deps_lock(vault, fed))
    return findings


def _lint_deps_lock(vault: Vault, fed: _FederationContext) -> list[Finding]:
    """L-FED-3：声明了 deps 就必须有一致的 lock（升级依赖 = 改 rev + 重 sync）。"""
    out: list[Finding] = []
    for dep_id in sorted(vault.config.deps):
        spec = vault.config.deps[dep_id]
        entry = fed.lock.get(dep_id)
        if entry is None:
            out.append(
                Finding(
                    "L-FED-3",
                    LEVEL_ERROR,
                    "vault.yaml",
                    f"依赖 {dep_id} 未锁定（先 vault deps sync 生成 vault.lock）",
                )
            )
            continue
        if spec.git is not None and spec.rev != entry.get("resolved_rev"):
            out.append(
                Finding(
                    "L-FED-3",
                    LEVEL_ERROR,
                    "vault.yaml",
                    f"依赖 {dep_id} 的 rev={spec.rev} 与 lock "
                    f"resolved_rev={entry.get('resolved_rev')} 不一致（重新 vault deps sync）",
                )
            )
    return out


def _lint_schema(
    card: Card, vault: Vault, validator: jsonschema.Draft202012Validator
) -> list[Finding]:
    doc = frontmatter.load_file(vault.root / card.path)
    payload = frontmatter.jsonable(doc.meta)
    out = []
    for error in validator.iter_errors(payload):
        where = "/".join(str(p) for p in error.absolute_path) or "<frontmatter>"
        out.append(Finding("SCHEMA", LEVEL_ERROR, card.path, f"{where}: {error.message}"))
    return out


def _lint_ids(card: Card) -> list[Finding]:
    out = []
    if FEDERATION_SEPARATOR in card.meta.id:
        out.append(
            Finding(
                "L-ID-1",
                LEVEL_ERROR,
                card.path,
                f"本地卡片 id 不得包含保留分隔符 '{FEDERATION_SEPARATOR}'：{card.meta.id}",
            )
        )
    claim_ids = [c.id for c in card.meta.claims]
    if len(claim_ids) != len(set(claim_ids)):
        out.append(Finding("L-ID-1", LEVEL_ERROR, card.path, "claim id 在卡内重复"))
    if len(card.meta.summary) > 80:
        out.append(
            Finding(
                "L-SUM-1",
                LEVEL_ERROR,
                card.path,
                f"summary 超长（{len(card.meta.summary)} > 80）",
            )
        )
    return out


def _lint_kind(card: Card, kinds: set[str]) -> list[Finding]:
    if card.meta.kind in kinds:
        return []
    return [
        Finding(
            "L-PACK-1",
            LEVEL_ERROR,
            card.path,
            f"kind '{card.meta.kind}' 不在启用 Pack 词表内（可用：{sorted(kinds)}）",
        )
    ]


def _lint_claims(card: Card, vault: Vault, threshold: float) -> list[Finding]:
    out = []
    for claim in card.meta.claims:
        for span in claim.sources:
            if span.source not in vault.sources:
                out.append(
                    Finding(
                        "L-PROV-1",
                        LEVEL_ERROR,
                        card.path,
                        f"claim {claim.id} 引用的源不存在：{span.source}",
                    )
                )
                continue
            try:
                resolved = spanhash.resolve(vault, span)
            except spanhash.SpanError as e:
                out.append(
                    Finding("L-PROV-2", LEVEL_ERROR, card.path, f"claim {claim.id}: {e}")
                )
                continue
            actual = spanhash.sha256_text(resolved.text)
            if actual != span.span_sha256:
                out.append(
                    Finding(
                        "L-PROV-2",
                        LEVEL_ERROR,
                        card.path,
                        f"claim {claim.id} 的 span 哈希不一致（引用造假或源漂移）："
                        f"记录 {span.span_sha256[:12]}… 实算 {actual[:12]}…",
                    )
                )
            hits = security.scan_text(resolved.text)
            if hits:
                out.append(
                    Finding(
                        "L-SEC-1",
                        LEVEL_WARN,
                        card.path,
                        f"claim {claim.id} 引用的源区段命中注入模式"
                        f"（{security.RULES_VERSION}: {', '.join(hits)}）"
                        "，可疑内容不得进入验证链",
                    )
                )
            relpath, _ = spanhash.parse_loc(span.loc)
            confidence = vault.extraction_confidence(span.source, relpath)
            if confidence is not None and confidence < threshold and not claim.low_confidence:
                out.append(
                    Finding(
                        "L-PROV-4",
                        LEVEL_WARN,
                        card.path,
                        f"claim {claim.id} 的支撑源抽取置信度 {confidence} < {threshold}"
                        "，必须标注 low_confidence: true",
                    )
                )
    return out


_BIB_KEY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,")


def _lint_refs(vault: Vault) -> list[Finding]:
    """L-REF-1 结构切片：refs/ 白名单自身完整——bib 每条都有验证状态登记。

    交付物侧「引用只准来自已验证条目」的完整核对随导出器（M4）落地。
    """
    refs_dir = vault.root / "refs"
    bib = refs_dir / "references.bib"
    status_file = refs_dir / "status.yaml"
    if not bib.is_file():
        return []
    out = []
    keys = _BIB_KEY_RE.findall(bib.read_text(encoding="utf-8"))
    status: dict[str, Any] = {}
    if status_file.is_file():
        try:
            loaded = yaml.safe_load(status_file.read_text(encoding="utf-8")) or {}
            if not isinstance(loaded, dict):
                raise ValueError("status.yaml 必须是映射")
            status = loaded
        except (yaml.YAMLError, ValueError) as e:
            return [Finding("L-REF-1", LEVEL_ERROR, "refs/status.yaml", f"解析失败：{e}")]
    for key in keys:
        entry = status.get(key)
        if entry is None:
            out.append(
                Finding(
                    "L-REF-1",
                    LEVEL_ERROR,
                    "refs/references.bib",
                    f"引用 {key} 未在 refs/status.yaml 登记验证状态",
                )
            )
        elif not (isinstance(entry, dict) and entry.get("verified") is True):
            out.append(
                Finding(
                    "L-REF-1",
                    LEVEL_WARN,
                    "refs/status.yaml",
                    f"引用 {key} 尚未通过验证（verified != true），交付物不得引用",
                )
            )
    return out


def _lint_links(
    card: Card, vault: Vault, predicates: set[str], fed: _FederationContext
) -> list[Finding]:
    out = []
    for link in card.meta.links:
        if link.predicate not in predicates:
            out.append(
                Finding(
                    "L-LINK-1",
                    LEVEL_ERROR,
                    card.path,
                    f"链接谓词 '{link.predicate}' 不在受控词表内（可用：{sorted(predicates)}）",
                )
            )
        if FEDERATION_SEPARATOR in link.to:
            dep_id, target_id = link.to.split(FEDERATION_SEPARATOR, 1)
            if dep_id not in vault.config.deps:
                out.append(
                    Finding(
                        "L-FED-1",
                        LEVEL_ERROR,
                        card.path,
                        f"跨库引用 '{link.to}' 的依赖 {dep_id} 未在 vault.yaml 的 deps 声明",
                    )
                )
                continue
            if dep_id not in fed.lock:
                out.append(
                    Finding(
                        "L-FED-3",
                        LEVEL_ERROR,
                        card.path,
                        f"跨库引用 '{link.to}' 的依赖未锁定（先 vault deps sync）",
                    )
                )
                continue
            dep_vault = fed.dep_vault(dep_id)
            if dep_vault is None:
                out.append(
                    Finding(
                        "L-FED-3",
                        LEVEL_ERROR,
                        card.path,
                        f"依赖 {dep_id} 无法解析到本地（缓存缺失或路径失效）",
                    )
                )
                continue
            target_card = dep_vault.cards.get(target_id)
            if target_card is None:
                out.append(
                    Finding(
                        "L-FED-1",
                        LEVEL_ERROR,
                        card.path,
                        f"跨库引用目标在上游不存在：{link.to}",
                    )
                )
                continue
            if target_card.meta.status in TERMINAL_STATUSES:
                out.append(
                    Finding(
                        "L-FED-2",
                        LEVEL_WARN,
                        card.path,
                        f"跨库引用 {link.to} 指向终态上游卡"
                        f"（status={target_card.meta.status}）——考虑本地替代或移除引用",
                    )
                )
            continue
        target = vault.cards.get(link.to)
        if target is None:
            out.append(
                Finding(
                    "L-LINK-1",
                    LEVEL_ERROR,
                    card.path,
                    f"链接目标卡不存在：{link.to}",
                )
            )
            continue
        if (
            card.meta.status == "active"
            and target.meta.status in TERMINAL_STATUSES
            and link.predicate not in KERNEL_PREDICATES
        ):
            out.append(
                Finding(
                    "L-LIFE-1",
                    LEVEL_ERROR,
                    card.path,
                    f"active 卡不得引用终态卡 {link.to}（status={target.meta.status}）",
                )
            )
    return out


def has_errors(findings: list[Finding]) -> bool:
    return any(f.level == LEVEL_ERROR for f in findings)
