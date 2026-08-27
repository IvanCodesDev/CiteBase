"""Vault 联邦（M5，storage-and-versioning §5）：知识即依赖。

像声明包依赖一样声明知识库依赖：git 锁定到 rev（不存在浮动 latest）或本地路径；
``vault deps sync`` 解析依赖并写 ``vault.lock``（resolved_rev + 卡片树内容哈希 +
逐卡哈希——升级依赖的 PR diff 直接显示影响面）。

四条不变量（实现必须守住）：
1. 出处链跨库仍可验证——quote 在依赖库的锁定内容上重算 span 哈希；
2. 上游更新不静默传播——升级 = 改 rev/重 sync = 一次 PR，影响面在 sync 报告与 lock diff；
3. 治理不跨库——裁决/复核动词只作用于本库；上游失效在本库表现为「依赖过期」提示；
4. 联邦是可选层——不声明 deps 的 vault 行为与 M0 完全一致。

只支持一层依赖（不解析传递依赖，防依赖地狱，风险 R6）。
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from cardvault import retrieve
from cardvault.model import FEDERATION_SEPARATOR, Card, DepSpec
from cardvault.vault import Vault

LOCK_FILE = "vault.lock"
DEPS_CACHE_DIR = "_deps"
PATH_DEP_REV = "local-path"


class FederationError(ValueError):
    """依赖声明/解析/锁定的结构性错误。"""


# ---------- 引用解析 ----------


def split_ref(ref: str) -> tuple[str | None, str]:
    """``dep::card-x`` → (dep, card-x)；无前缀 → (None, ref)。"""
    if FEDERATION_SEPARATOR in ref:
        dep_id, local = ref.split(FEDERATION_SEPARATOR, 1)
        return dep_id, local
    return None, ref


def qualify(dep_id: str, card_id: str) -> str:
    return f"{dep_id}{FEDERATION_SEPARATOR}{card_id}"


# ---------- 解析器（VaultResolver 端口实现） ----------


def _run_git(args: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise FederationError(
            f"git {' '.join(args)} 失败：{result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout.strip()


class PathVaultResolver:
    """本地路径依赖：直接指向目录（示例、单仓多库、离线测试）。"""

    name = "path"

    def __init__(self, spec: DepSpec) -> None:
        assert spec.path is not None
        self._path = spec.path

    def resolve(self, vault_root: Path, dep_id: str) -> Path:
        target = (vault_root / self._path).resolve()
        if not (target / "vault.yaml").is_file():
            raise FileNotFoundError(f"依赖 {dep_id} 的路径不是一个 vault：{target}")
        return target

    def resolved_rev(self, vault_root: Path, dep_id: str) -> str:
        return PATH_DEP_REV


class GitVaultResolver:
    """git 依赖：克隆/检出锁定 rev 到 ``_deps/<dep-id>/``（鉴权交给 git 凭据体系）。"""

    name = "git"

    def __init__(self, spec: DepSpec) -> None:
        assert spec.git is not None and spec.rev
        self._url = spec.git
        self._rev = spec.rev

    def _cache(self, vault_root: Path, dep_id: str) -> Path:
        return vault_root / DEPS_CACHE_DIR / dep_id

    def resolve(self, vault_root: Path, dep_id: str) -> Path:
        cache = self._cache(vault_root, dep_id)
        if not (cache / ".git").exists():
            cache.parent.mkdir(parents=True, exist_ok=True)
            _run_git(["clone", "--quiet", self._url, str(cache)])
        try:
            _run_git(["checkout", "--quiet", "--detach", self._rev], cwd=cache)
        except FederationError:
            _run_git(["fetch", "--quiet", "origin"], cwd=cache)
            _run_git(["checkout", "--quiet", "--detach", self._rev], cwd=cache)
        if not (cache / "vault.yaml").is_file():
            raise FederationError(f"依赖 {dep_id} 在 rev {self._rev} 下不是一个 vault")
        return cache

    def resolved_rev(self, vault_root: Path, dep_id: str) -> str:
        return _run_git(["rev-parse", "HEAD"], cwd=self._cache(vault_root, dep_id))


def resolver_for(spec: DepSpec) -> PathVaultResolver | GitVaultResolver:
    return PathVaultResolver(spec) if spec.path is not None else GitVaultResolver(spec)


# ---------- 内容哈希与锁定 ----------


def _sha256_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _normalize_newlines(data: bytes) -> bytes:
    """锁哈希前把 CRLF 与孤立 CR 归一化为 LF。

    git 在 Windows 上（autocrlf）可能以 CRLF 检出上游库；若按原始字节哈希，
    同一内容在不同平台会得到不同哈希，``deps status`` 误报 stale。
    """
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def card_hashes(dep_root: Path) -> dict[str, str]:
    """依赖库逐卡内容哈希（key = 卡 id；文件名即 slug，id 从 frontmatter 加载）。

    哈希按 LF 归一化后的字节计算（CRLF/孤立 CR → LF），使锁文件对检出时的
    换行符不敏感——同一 rev 在任意平台重算结果一致（跨平台可复现）。
    """
    dep_vault = Vault.load(dep_root)
    out: dict[str, str] = {}
    for card_id in sorted(dep_vault.cards):
        card = dep_vault.cards[card_id]
        raw = (dep_root / card.path).read_bytes()
        out[card_id] = _sha256_bytes(_normalize_newlines(raw))
    return out


def root_hash(hashes: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for card_id in sorted(hashes):
        digest.update(card_id.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashes[card_id].encode("ascii"))
        digest.update(b"\n")
    return f"sha256:{digest.hexdigest()}"


def load_lock(vault_root: Path) -> dict[str, dict[str, Any]]:
    path = vault_root / LOCK_FILE
    if not path.is_file():
        return {}
    data: dict[str, dict[str, Any]] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data


def save_lock(vault_root: Path, lock: dict[str, dict[str, Any]]) -> None:
    (vault_root / LOCK_FILE).write_text(
        yaml.safe_dump(lock, sort_keys=True, allow_unicode=True),
        encoding="utf-8",
        newline="\n",
    )


# ---------- deps sync / status ----------


@dataclass
class DepImpact:
    dep_id: str
    added: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    #: 本库链接到「变更/移除上游卡」的卡（升级影响面）
    affected_local: list[str] = field(default_factory=list)


@dataclass
class SyncReport:
    synced: list[str] = field(default_factory=list)
    impacts: list[DepImpact] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "synced": self.synced,
            "impacts": [vars(i) for i in self.impacts],
        }


def _local_refs_into(vault: Vault, dep_id: str) -> dict[str, list[str]]:
    """本库对某依赖的全部引用：上游卡 id → 引用它的本地卡列表。"""
    refs: dict[str, list[str]] = {}
    for card in vault.cards.values():
        for link in card.meta.links:
            target_dep, target_card = split_ref(link.to)
            if target_dep == dep_id:
                refs.setdefault(target_card, []).append(card.meta.id)
    return refs


def deps_sync(vault_root: Path) -> SyncReport:
    vault = Vault.load(vault_root)
    report = SyncReport()
    if not vault.config.deps:
        return report
    old_lock = load_lock(vault_root)
    new_lock: dict[str, dict[str, Any]] = {}
    for dep_id in sorted(vault.config.deps):
        spec = vault.config.deps[dep_id]
        resolver = resolver_for(spec)
        dep_root = resolver.resolve(vault_root, dep_id)
        hashes = card_hashes(dep_root)
        new_lock[dep_id] = {
            "resolved_rev": resolver.resolved_rev(vault_root, dep_id),
            "root_hash": root_hash(hashes),
            "cards": hashes,
        }
        report.synced.append(dep_id)

        old_cards: dict[str, str] = dict(old_lock.get(dep_id, {}).get("cards", {}))
        impact = DepImpact(dep_id=dep_id)
        impact.added = sorted(set(hashes) - set(old_cards))
        impact.removed = sorted(set(old_cards) - set(hashes))
        impact.changed = sorted(
            cid for cid in set(hashes) & set(old_cards) if hashes[cid] != old_cards[cid]
        )
        touched = set(impact.changed) | set(impact.removed)
        if touched:
            refs = _local_refs_into(vault, dep_id)
            impact.affected_local = sorted(
                {local for cid in touched for local in refs.get(cid, [])}
            )
        if impact.added or impact.changed or impact.removed:
            report.impacts.append(impact)
    save_lock(vault_root, new_lock)
    return report


@dataclass
class DepStatus:
    dep_id: str
    state: str  # ok | needs_sync | missing_cache | stale
    detail: str = ""
    broken_refs: list[str] = field(default_factory=list)  # 本地卡 → 缺失上游卡
    terminal_refs: list[str] = field(default_factory=list)  # 本地卡 → 终态上游卡


@dataclass
class StatusReport:
    deps: list[DepStatus] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return all(
            d.state == "ok" and not d.broken_refs and not d.terminal_refs
            for d in self.deps
        )

    def to_dict(self) -> dict[str, Any]:
        return {"clean": self.clean, "deps": [vars(d) for d in self.deps]}


def deps_status(vault_root: Path) -> StatusReport:
    vault = Vault.load(vault_root)
    report = StatusReport()
    lock = load_lock(vault_root)
    for dep_id in sorted(vault.config.deps):
        spec = vault.config.deps[dep_id]
        entry = lock.get(dep_id)
        if entry is None:
            report.deps.append(
                DepStatus(dep_id, "needs_sync", "无 lock 条目（先 vault deps sync）")
            )
            continue
        if spec.git is not None and spec.rev != entry.get("resolved_rev"):
            report.deps.append(
                DepStatus(
                    dep_id,
                    "needs_sync",
                    f"vault.yaml rev={spec.rev} 与 lock "
                    f"resolved_rev={entry.get('resolved_rev')} 不一致",
                )
            )
            continue
        try:
            dep_root = resolver_for(spec).resolve(vault_root, dep_id)
        except (FileNotFoundError, FederationError) as e:
            report.deps.append(DepStatus(dep_id, "missing_cache", str(e)))
            continue
        live_hashes = card_hashes(dep_root)
        status = DepStatus(dep_id, "ok")
        if root_hash(live_hashes) != entry.get("root_hash"):
            status.state = "stale"
            status.detail = "依赖内容与 lock 不一致（上游已变更或缓存被改）：重新 sync 并评审影响面"
        dep_vault = Vault.load(dep_root)
        for upstream_card, locals_ in sorted(_local_refs_into(vault, dep_id).items()):
            target = dep_vault.cards.get(upstream_card)
            if target is None:
                status.broken_refs.extend(
                    f"{local} → {qualify(dep_id, upstream_card)}" for local in locals_
                )
            elif target.meta.status in ("retired", "superseded"):
                status.terminal_refs.extend(
                    f"{local} → {qualify(dep_id, upstream_card)}"
                    f"（上游 {target.meta.status}）"
                    for local in locals_
                )
        report.deps.append(status)
    return report


# ---------- 依赖库加载与联邦读侧 ----------


def load_dep_vault(vault_root: Path, vault: Vault, dep_id: str) -> Vault:
    spec = vault.config.deps.get(dep_id)
    if spec is None:
        raise FederationError(f"未声明的依赖：{dep_id}（vault.yaml 的 deps 段）")
    if dep_id not in load_lock(vault_root):
        raise FederationError(f"依赖 {dep_id} 未锁定：先 vault deps sync")
    return Vault.load(resolver_for(spec).resolve(vault_root, dep_id))


def search_scoped(
    vault_root: Path,
    query: str,
    *,
    scope: list[str] | None = None,
    kind: str | None = None,
    tags: list[str] | None = None,
    as_of_text: str | None = None,
    limit: int = 10,
    include_suspect: bool = False,
) -> dict[str, Any]:
    """联邦检索：逐库走同一条漏斗，命中标注来源库；默认只搜本库。

    合并规则：先按跳级（exact > bm25 > graph）、self 优先、再按得分——BM25 得分
    只在库内可比，跨库排序以跳级为准（诚实取舍，不假装可比）。
    """
    from cardvault.backends import select_backend

    vault = Vault.load(vault_root)
    members = scope or ["self"]
    jump_rank = {"exact": 0, "bm25": 1, "graph": 2}
    merged_hits: list[tuple[int, int, float, dict[str, Any]]] = []
    tried: list[str] = []
    suggestion: str | None = None
    any_hit = False

    from cardvault import index as index_mod

    for order, member in enumerate(members):
        if member == "self":
            backend: Any = select_backend(vault)
        else:
            backend = index_mod.build(load_dep_vault(vault_root, vault, member))
        result = retrieve.search(
            backend,
            query,
            kind=kind,
            tags=tags,
            as_of=retrieve.parse_as_of(as_of_text),
            limit=limit,
            include_suspect=include_suspect,
        )
        tried.extend(f"{member}:{t}" for t in result.tried)
        if member == "self" and not result.hit:
            suggestion = result.suggestion
        if result.hit:
            any_hit = True
            for hit in result.hits:
                payload = hit.to_dict()
                payload["vault"] = member
                if member != "self":
                    payload["id"] = qualify(member, payload["id"])
                merged_hits.append(
                    (jump_rank.get(hit.jump, 9), order, -hit.score, payload)
                )

    merged_hits.sort(key=lambda item: (item[0], item[1], item[2], item[3]["id"]))
    hits = [payload for _, _, _, payload in merged_hits[:limit]]
    out: dict[str, Any] = {"hit": any_hit, "hits": hits, "tried": tried}
    if not any_hit:
        out["suggestion"] = suggestion or "库内无相关卡片；该查询可作为建卡线索记录"
    return out


def read_federated(vault_root: Path, ref: str) -> tuple[Vault, str] | None:
    """解析 ``dep::card`` 为（依赖库, 本地卡 id）；无前缀返回 None（走本库）。"""
    dep_id, card_id = split_ref(ref)
    if dep_id is None:
        return None
    vault = Vault.load(vault_root)
    return load_dep_vault(vault_root, vault, dep_id), card_id


def federated_read(vault_root: Path, ref: str) -> Card | None:
    """读取跨库卡（上游无此卡返回 None）。ref 必须带 ``dep::`` 前缀。"""
    pair = read_federated(vault_root, ref)
    if pair is None:
        raise FederationError(f"不是跨库引用：{ref}")
    dep_vault, card_id = pair
    return dep_vault.cards.get(card_id)


def federated_follow(
    vault_root: Path, ref: str, *, predicate: str | None = None
) -> dict[str, list[dict[str, str]]] | None:
    """跨库顺链跳读：邻居 id 加 ``dep::`` 前缀，保持可继续跳读；上游无此卡返回 None。"""
    from cardvault import index as index_mod

    pair = read_federated(vault_root, ref)
    if pair is None:
        raise FederationError(f"不是跨库引用：{ref}")
    dep_vault, card_id = pair
    dep_id, _ = split_ref(ref)
    assert dep_id is not None
    edges = retrieve.follow(index_mod.build(dep_vault), card_id, predicate=predicate)
    if edges is None:
        return None
    for edge_list in edges.values():
        for edge in edge_list:
            edge["card"] = qualify(dep_id, edge["card"])
    return edges


def federated_quote(vault_root: Path, ref: str) -> retrieve.QuoteResult | None:
    """跨库取引：span 哈希在依赖库锁定内容上重算（出处链跨库仍可验证，不变量 1）。

    ref 形如 ``dep::card-x#c1``；上游无此卡/论断返回 None。
    """
    pair = read_federated(vault_root, ref)
    if pair is None:
        raise FederationError(f"不是跨库引用：{ref}")
    dep_vault, local_ref = pair
    dep_id, _ = split_ref(ref)
    assert dep_id is not None
    result = retrieve.quote(dep_vault, local_ref)
    if result is None:
        return None
    result.card_id = qualify(dep_id, result.card_id)
    return result
