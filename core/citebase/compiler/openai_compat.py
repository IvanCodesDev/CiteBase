"""OpenAI 兼容 LlmProvider：任意 /chat/completions 端点（密钥走环境变量）。

网络层薄到只有一个 POST；payload 构造与响应解析全部是纯函数，可离线测试。
LLM 不可用（未配置 / 无密钥）时按管线契约整批跳过，可离线重跑。
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from citebase.model import LlmSettings
from citebase.ports import (
    ConflictPair,
    ContradictDecision,
    ContradictRequest,
    DraftCard,
    MergeDecision,
    MergeRequest,
    ProposeRequest,
    ProposeResponse,
    TokenUsage,
)


class LlmUnavailableError(RuntimeError):
    """配置或密钥缺失：调用方应整批跳过编译而不是崩溃。"""


def numbered(text: str) -> str:
    return "\n".join(f"L{i}|{line}" for i, line in enumerate(text.splitlines(), start=1))


def strip_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        stripped = stripped[first_newline + 1 :] if first_newline != -1 else ""
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3]
    return stripped.strip()


def build_chat_payload(
    settings: LlmSettings, system: str, user: str
) -> dict[str, Any]:
    return {
        "model": settings.model,
        "temperature": settings.temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }


def render_propose_user(request: ProposeRequest) -> str:
    parts: list[str] = [f"# 源：{request.source_id}", ""]
    for relpath, text in request.derivatives.items():
        parts += [f"## 派生物 {relpath}（引用 loc 用行号区间）", "", numbered(text), ""]
    parts.append("## 启用卡类（kind → 正文分节）")
    for kind_def in request.pack.card_kinds:
        parts.append(f"- {kind_def.kind}: {' / '.join(kind_def.body_sections)}")
    parts.append("")
    parts.append(f"## 受控链接谓词：{', '.join(request.pack.link_predicates) or '（无）'}")
    parts.append("")
    if request.existing:
        parts.append("## 既有卡（id | kind | name | aliases）")
        for digest in request.existing:
            aliases = ", ".join(digest.aliases)
            parts.append(f"- {digest.id} | {digest.kind} | {digest.name} | {aliases}")
        parts.append("")
    parts.append("请输出 JSON：{\"cards\": [...]}")
    return "\n".join(parts)


def render_contradict_user(request: ContradictRequest) -> str:
    parts = [f"# 目标卡：{request.existing_id}", "", "## 既有论断"]
    parts += [f"- {cid}: {text}" for cid, text in request.existing_claims]
    parts += ["", "## 新草案论断"]
    parts += [f"- {cid}: {text}" for cid, text in request.draft_claims]
    parts += ["", "请输出 JSON：{\"conflicts\": [...]}"]
    return "\n".join(parts)


def parse_drafts(content: str) -> list[DraftCard]:
    from citebase.compiler.providers import draft_from_dict

    data = json.loads(strip_fences(content))
    cards = data.get("cards") if isinstance(data, dict) else None
    if not isinstance(cards, list):
        raise ValueError("LLM 输出缺少 cards 数组")
    return [draft_from_dict(item) for item in cards]


def parse_conflicts(content: str) -> list[ConflictPair]:
    data = json.loads(strip_fences(content))
    conflicts = data.get("conflicts") if isinstance(data, dict) else None
    if not isinstance(conflicts, list):
        raise ValueError("LLM 输出缺少 conflicts 数组")
    return [
        ConflictPair(
            existing_claim=str(item["existing_claim"]),
            draft_claim=str(item["draft_claim"]),
            topic=str(item.get("topic", "")),
        )
        for item in conflicts
    ]


def _parse_usage(data: dict[str, Any]) -> TokenUsage:
    usage = data.get("usage") or {}
    return TokenUsage(
        input_tokens=int(usage.get("prompt_tokens", 0)),
        output_tokens=int(usage.get("completion_tokens", 0)),
    )


class OpenAICompatProvider:
    name = "openai-compat"

    def __init__(self, settings: LlmSettings, api_key: str) -> None:
        self._settings = settings
        self._api_key = api_key

    @classmethod
    def from_settings(cls, settings: LlmSettings | None) -> OpenAICompatProvider:
        if settings is None or not settings.base_url or not settings.model:
            raise LlmUnavailableError(
                "vault.yaml 未配置 llm.base_url / llm.model——LLM 不可用，整批跳过，可离线重跑"
            )
        api_key = os.environ.get(settings.api_key_env, "")
        if not api_key:
            raise LlmUnavailableError(
                f"环境变量 {settings.api_key_env} 未设置——LLM 不可用，整批跳过，可离线重跑"
            )
        return cls(settings, api_key)

    def describe(self) -> dict[str, Any]:
        return {
            "provider": self._settings.provider,
            "name": self._settings.model,
            "temperature": self._settings.temperature,
            "base_url": self._settings.base_url,
        }

    def _chat(self, system: str, user: str) -> tuple[str, TokenUsage]:
        payload = build_chat_payload(self._settings, system, user)
        url = self._settings.base_url.rstrip("/") + "/chat/completions"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self._settings.timeout_seconds) as resp:
            data: dict[str, Any] = json.load(resp)
        content = str(data["choices"][0]["message"]["content"])
        return content, _parse_usage(data)

    def propose(self, request: ProposeRequest) -> ProposeResponse:
        content, usage = self._chat(request.prompt.text, render_propose_user(request))
        return ProposeResponse(drafts=parse_drafts(content), usage=usage)

    def merge_judge(self, request: MergeRequest) -> MergeDecision:
        return MergeDecision(verdict="unsure", reason="M1：并卡一律升级人工审核")

    def contradict_judge(self, request: ContradictRequest) -> ContradictDecision:
        content, usage = self._chat(request.prompt.text, render_contradict_user(request))
        return ContradictDecision(conflicts=parse_conflicts(content), usage=usage)
