"""EvidenceEvent（M3）：解析校验、装载、规范化渲染、源登记与漂移联动。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cardvault.drift import run_drift
from cardvault.evidence import (
    EvidenceEvent,
    claim_loc,
    load_events,
    register_event_source,
    render_event_text,
    source_registered,
)
from cardvault.vault import Vault
from helpers import make_drift_vault, make_event, write_events
from pydantic import ValidationError


def test_event_model_enforces_schema() -> None:
    good = EvidenceEvent.model_validate(make_event(1, category="extrapolation", summary="外推背离"))
    assert good.event_id == "evt-2026-08-14-run-0001"

    with pytest.raises(ValidationError):  # event_id 格式非法
        EvidenceEvent.model_validate({**make_event(1), "event_id": "run-0001"})
    with pytest.raises(ValidationError):  # 额外字段拒绝
        EvidenceEvent.model_validate({**make_event(1), "extra": True})
    with pytest.raises(ValidationError):  # 自由文本限长（≤2000）
        EvidenceEvent.model_validate(
            make_event(1, category="x", summary="长" * 2001)
        )
    with pytest.raises(ValidationError):  # outcome.status 受控
        EvidenceEvent.model_validate({**make_event(1), "outcome": {"status": "maybe"}})


def test_load_events_skips_bad_lines_and_duplicates(tmp_path: Path) -> None:
    root, _ = make_drift_vault(tmp_path)
    good_a = make_event(1, category="a")
    good_b = make_event(2, category="b")
    path = write_events(root, [good_a, good_b])
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write("这不是 JSON\n")
        fh.write(json.dumps({**good_a, "ts": "2026-08-15T00:00:00Z"}) + "\n")  # 重复 id

    result = load_events(root)

    assert [le.event.event_id for le in result.events] == [
        "evt-2026-08-14-run-0001",
        "evt-2026-08-14-run-0002",
    ]
    assert len(result.invalid) == 1
    assert result.invalid[0]["line"] == 3
    assert result.duplicates == ["evt-2026-08-14-run-0001"]


def test_render_event_text_is_line_addressable() -> None:
    event = EvidenceEvent.model_validate(
        make_event(
            7,
            category="extrapolation",
            summary="第一行\n第二行  折叠成单行",
            cards=["card-method-x"],
        )
    )
    text, linemap = render_event_text(event)
    lines = text.splitlines()

    summary_line = lines[linemap["failure.summary"] - 1]
    assert summary_line == "failure.summary: 第一行 第二行 折叠成单行"
    assert claim_loc(event) == (
        f"extracted/event.txt#L{linemap['failure.summary']}-L{linemap['failure.summary']}"
    )

    no_failure = EvidenceEvent.model_validate(make_event(8, status="success"))
    _, nf_map = render_event_text(no_failure)
    assert claim_loc(no_failure) == (
        f"extracted/event.txt#L{nf_map['outcome.status']}-L{nf_map['outcome.status']}"
    )


def test_register_event_source_idempotent(tmp_path: Path) -> None:
    root, _ = make_drift_vault(tmp_path)
    write_events(root, [make_event(1, category="a", summary="现象")])
    loaded = load_events(root).events[0]

    assert register_event_source(root, loaded) is True
    assert register_event_source(root, loaded) is False
    assert source_registered(root, loaded.event.event_id)

    vault = Vault.load(root)
    meta = vault.sources[loaded.event.event_id]
    assert meta.adapter == "evidence"
    assert meta.uri == "evidence/2026-08.jsonl#L1"
    assert meta.revision.startswith("sha256:")


def test_drift_treats_registered_events_as_immutable(tmp_path: Path) -> None:
    root, _ = make_drift_vault(tmp_path)
    write_events(root, [make_event(1, category="a", summary="现象")])
    loaded = load_events(root).events[0]
    register_event_source(root, loaded)

    report = run_drift(root, apply=True)
    assert report.signals == []  # 事件不可变：不产生任何漂移信号

    original = root / "sources" / loaded.event.event_id / "originals" / "event.json"
    original.write_text("被篡改", encoding="utf-8")
    tampered = run_drift(root, apply=True)
    assert {s.kind for s in tampered.signals} == {"source_changed"}

    original.unlink()
    missing = run_drift(root, apply=True)
    assert {s.kind for s in missing.signals} == {"source_unreachable"}
