from __future__ import annotations

from typing import Any

from citebase.compiler.review import review_rate, sample_size
from citebase.model import ReviewSettings

SETTINGS = ReviewSettings()


def good_batch(n: int = 2) -> dict[str, Any]:
    return {
        "run_id": "r",
        "sent_review": n,
        "auto_approved": 0,
        "machine_rejected": 0,
        "approved": n,
        "rejected": 0,
    }


def test_new_source_reviews_everything() -> None:
    assert review_rate([], SETTINGS) == 1.0


def test_single_good_batch_not_enough_to_step_down() -> None:
    assert review_rate([good_batch()], SETTINGS) == 1.0


def test_ladder_steps_down_with_streak() -> None:
    assert review_rate([good_batch(), good_batch()], SETTINGS) == 0.5
    assert review_rate([good_batch()] * 3, SETTINGS) == 0.25
    assert review_rate([good_batch()] * 4, SETTINGS) == 0.1
    assert review_rate([good_batch()] * 9, SETTINGS) == 0.1  # 封底


def test_bad_reject_rate_resets_to_full_review() -> None:
    bad = {
        "run_id": "r",
        "sent_review": 2,
        "auto_approved": 0,
        "machine_rejected": 2,
        "approved": 1,
        "rejected": 1,
    }  # 总驳回率 3/4 > 0.3
    assert review_rate([good_batch(), good_batch(), bad], SETTINGS) == 1.0


def test_incomplete_batch_is_ignored() -> None:
    incomplete = {
        "run_id": "r",
        "sent_review": 3,
        "auto_approved": 0,
        "machine_rejected": 0,
        "approved": 1,
        "rejected": 0,
    }
    assert review_rate([incomplete], SETTINGS) == 1.0
    assert review_rate([good_batch(), good_batch(), incomplete], SETTINGS) == 0.5


def test_broken_streak_resets_ladder() -> None:
    mediocre = {
        "run_id": "r",
        "sent_review": 10,
        "auto_approved": 30,
        "machine_rejected": 0,
        "approved": 8,
        "rejected": 2,
    }  # 通过率 0.8 < 0.9，总驳回率 2/40 ≤ 0.3
    assert review_rate([good_batch(), good_batch(), mediocre], SETTINGS) == 1.0


def test_sample_size() -> None:
    assert sample_size(1.0, 4) == 4
    assert sample_size(0.5, 3) == 2
    assert sample_size(0.0, 5) == 0
    assert sample_size(0.1, 1) == 1  # 向上取整：再低的抽样率也至少抽一张
    assert sample_size(0.5, 0) == 0
