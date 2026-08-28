"""L2 索引：从卡片文件重建目录、别名表、链接图与加权倒排。

索引是纯生成物：幂等、确定性序列化、永不手改；``check`` 逐字节比对重建结果与
落盘文件（L-IDX-1）。M0 后端为进程内数据结构 + JSON 落盘；加速后端经 IndexBackend
端口替换时，本模块的产物语义不变。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from citebase.vault import Vault

INDEX_DIR = "_index"
INDEX_FILES = ("catalog.json", "aliases.json", "links.json", "inverted.json", "meta.json")

#: 字段权重：命中「名称/别名」远比命中正文摘要重要。
FIELD_WEIGHTS: dict[str, int] = {
    "name": 4,
    "aliases": 4,
    "tags": 3,
    "summary": 2,
    "claims": 1,
}

_ASCII_RE = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*")
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """轻量分词：ASCII 词 + CJK 字符 bigram（单字 run 保留单字）。零依赖。"""
    lowered = text.lower()
    tokens = _ASCII_RE.findall(lowered)
    for run in _CJK_RE.findall(lowered):
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
    return tokens


def _card_field_texts(card_meta: dict[str, Any]) -> dict[str, list[str]]:
    return {
        "name": [card_meta["name"]],
        "aliases": list(card_meta.get("aliases", [])),
        "tags": list(card_meta.get("tags", [])),
        "summary": [card_meta["summary"]],
        "claims": [c["text"] for c in card_meta.get("claims", [])],
    }


def build(vault: Vault) -> dict[str, Any]:
    """构建全部索引结构（内存形态，可直接序列化）。"""
    catalog: dict[str, Any] = {}
    aliases: dict[str, list[str]] = {}
    links_out: dict[str, list[dict[str, str]]] = {}
    links_in: dict[str, list[dict[str, str]]] = {}
    inverted: dict[str, dict[str, int]] = {}
    doclen: dict[str, int] = {}

    for card_id in sorted(vault.cards):
        card = vault.cards[card_id]
        meta = card.meta
        catalog[card_id] = {
            "name": meta.name,
            "kind": meta.kind,
            "summary": meta.summary,
            "status": meta.status,
            "tags": list(meta.tags),
            "aliases": list(meta.aliases),
            "injection_risk": meta.injection_risk,
            "path": card.path,
            "claims": [
                {
                    "id": c.id,
                    "text": c.text,
                    "status": c.status,
                    "valid_from": c.valid_from.isoformat() if c.valid_from else None,
                    "valid_until": c.valid_until.isoformat() if c.valid_until else None,
                }
                for c in meta.claims
            ],
        }
        for alias in [meta.name, *meta.aliases]:
            key = alias.casefold()
            aliases.setdefault(key, [])
            if card_id not in aliases[key]:
                aliases[key].append(card_id)
        if meta.links:
            links_out[card_id] = [{"predicate": ln.predicate, "to": ln.to} for ln in meta.links]
            for ln in meta.links:
                links_in.setdefault(ln.to, []).append(
                    {"predicate": ln.predicate, "from": card_id}
                )

        weighted_tf: dict[str, int] = {}
        total = 0
        field_texts = _card_field_texts(catalog[card_id])
        for fieldname, texts in field_texts.items():
            weight = FIELD_WEIGHTS[fieldname]
            for text in texts:
                for token in tokenize(text):
                    weighted_tf[token] = weighted_tf.get(token, 0) + weight
                    total += weight
        doclen[card_id] = total
        for token, tf in weighted_tf.items():
            inverted.setdefault(token, {})[card_id] = tf

    n_docs = len(catalog)
    avgdl = (sum(doclen.values()) / n_docs) if n_docs else 0.0
    return {
        "catalog": catalog,
        "aliases": {k: sorted(v) for k, v in aliases.items()},
        "links": {"out": links_out, "in": links_in},
        "inverted": inverted,
        "meta": {
            "schema": "citebase-index/0.1",
            "cards": n_docs,
            "avgdl": round(avgdl, 6),
            "doclen": doclen,
            "field_weights": FIELD_WEIGHTS,
        },
    }


def _dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=1) + "\n"


def _files_payload(index: dict[str, Any]) -> dict[str, str]:
    return {
        "catalog.json": _dump(index["catalog"]),
        "aliases.json": _dump(index["aliases"]),
        "links.json": _dump(index["links"]),
        "inverted.json": _dump(index["inverted"]),
        "meta.json": _dump(index["meta"]),
    }


def write(vault_root: Path, index: dict[str, Any]) -> list[str]:
    """落盘 ``_index/``，返回写入的相对文件名。"""
    out_dir = vault_root / INDEX_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = _files_payload(index)
    for name, text in payload.items():
        (out_dir / name).write_text(text, encoding="utf-8", newline="\n")
    return list(payload)


def check(vault_root: Path, index: dict[str, Any]) -> list[str]:
    """L-IDX-1：重建结果与落盘文件逐字节一致。返回不一致清单（空 = 通过）。"""
    problems: list[str] = []
    out_dir = vault_root / INDEX_DIR
    payload = _files_payload(index)
    for name, expected in payload.items():
        file = out_dir / name
        if not file.is_file():
            problems.append(f"{INDEX_DIR}/{name}: 缺失（先运行 vault index）")
            continue
        actual = file.read_text(encoding="utf-8")
        if actual != expected:
            problems.append(f"{INDEX_DIR}/{name}: 与重建结果不一致（索引过期或被手改）")
    return problems
