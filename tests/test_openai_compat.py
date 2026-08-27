from __future__ import annotations

import pytest
from cardvault.compiler.openai_compat import (
    LlmUnavailableError,
    OpenAICompatProvider,
    build_chat_payload,
    numbered,
    parse_conflicts,
    parse_drafts,
    render_contradict_user,
    render_propose_user,
    strip_fences,
)
from cardvault.model import CardKindDef, LlmSettings, Pack
from cardvault.ports import CardDigest, ContradictRequest, PromptSpec, ProposeRequest

PROMPT = PromptSpec(id="propose.v1.prompt.md", sha256="0" * 64, text="system prompt")

SETTINGS = LlmSettings(base_url="https://api.example.com/v1", model="test-model")


def _propose_request() -> ProposeRequest:
    pack = Pack(
        name="generic",
        version="0.1.0",
        card_kinds=[CardKindDef(kind="concept", body_sections=["是什么", "关联"])],
        link_predicates=["related_to"],
    )
    return ProposeRequest(
        source_id="src-notes",
        derivatives={"extracted/text.md": "第一行\n第二行"},
        pack=pack,
        existing=[
            CardDigest(
                id="card-concept-alpha",
                kind="concept",
                name="Alpha",
                aliases=["A"],
                summary="示例。",
            )
        ],
        prompt=PROMPT,
    )


def test_numbered() -> None:
    assert numbered("a\nb") == "L1|a\nL2|b"


def test_strip_fences() -> None:
    assert strip_fences('{"x": 1}') == '{"x": 1}'
    assert strip_fences('```json\n{"x": 1}\n```') == '{"x": 1}'
    assert strip_fences("```\n{}\n```") == "{}"


def test_build_chat_payload_shape() -> None:
    payload = build_chat_payload(SETTINGS, "sys", "user")
    assert payload["model"] == "test-model"
    assert payload["temperature"] == 0.0
    assert payload["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in payload["messages"]] == ["system", "user"]


def test_render_propose_user_contains_everything() -> None:
    text = render_propose_user(_propose_request())
    assert "L1|第一行" in text
    assert "concept: 是什么 / 关联" in text
    assert "related_to" in text
    assert "card-concept-alpha" in text
    assert '{"cards": [...]}' in text


def test_render_contradict_user() -> None:
    request = ContradictRequest(
        existing_id="card-concept-alpha",
        existing_claims=[("c1", "旧论断")],
        draft_claims=[("c1", "新论断")],
        prompt=PROMPT,
    )
    text = render_contradict_user(request)
    assert "card-concept-alpha" in text
    assert "c1: 旧论断" in text
    assert "c1: 新论断" in text


def test_parse_drafts() -> None:
    span = '{"source": "src-a", "loc": "extracted/text.md#L1-L1"}'
    content = (
        '{"cards": [{"kind": "concept", "name": "X", "summary": "s", "body": "b",'
        f' "claims": [{{"text": "t", "spans": [{span}]}}]}}]}}'
    )
    drafts = parse_drafts(content)
    assert drafts[0].name == "X"
    assert drafts[0].claims[0].spans[0].loc == "extracted/text.md#L1-L1"
    fenced = f"```json\n{content}\n```"
    assert parse_drafts(fenced)[0].name == "X"


def test_parse_drafts_rejects_bad_shape() -> None:
    with pytest.raises(ValueError, match="cards"):
        parse_drafts('{"foo": []}')


def test_parse_conflicts() -> None:
    pairs = parse_conflicts('{"conflicts": [{"existing_claim": "c1", "draft_claim": "c2"}]}')
    assert pairs[0].existing_claim == "c1"
    assert pairs[0].draft_claim == "c2"
    with pytest.raises(ValueError, match="conflicts"):
        parse_conflicts("[]")


def test_from_settings_requires_config_and_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(LlmUnavailableError, match="base_url"):
        OpenAICompatProvider.from_settings(None)
    with pytest.raises(LlmUnavailableError, match="base_url"):
        OpenAICompatProvider.from_settings(LlmSettings())
    monkeypatch.delenv("CARDVAULT_API_KEY", raising=False)
    with pytest.raises(LlmUnavailableError, match="CARDVAULT_API_KEY"):
        OpenAICompatProvider.from_settings(SETTINGS)
    monkeypatch.setenv("CARDVAULT_API_KEY", "sk-test")
    provider = OpenAICompatProvider.from_settings(SETTINGS)
    described = provider.describe()
    assert described["name"] == "test-model"
    assert described["base_url"] == "https://api.example.com/v1"
