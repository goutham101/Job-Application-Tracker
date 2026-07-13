import pytest

from app.sm2 import sm2_update


def test_lapse_resets_interval_and_repetitions_but_not_easiness():
    result = sm2_update(easiness=2.5, interval_days=10, repetitions=3, quality=2)
    assert result.interval_days == 1
    assert result.repetitions == 0
    assert result.easiness == 2.5  # unchanged on lapse — the plan's explicit rule


def test_first_successful_review():
    result = sm2_update(easiness=2.5, interval_days=0, repetitions=0, quality=5)
    assert result.interval_days == 1
    assert result.repetitions == 1
    assert result.easiness == pytest.approx(2.6)


def test_second_successful_review_uses_six_days():
    result = sm2_update(easiness=2.36, interval_days=1, repetitions=1, quality=4)
    assert result.interval_days == 6
    assert result.repetitions == 2
    assert result.easiness == pytest.approx(2.36)


def test_third_plus_review_multiplies_by_easiness_rounded_up():
    result = sm2_update(easiness=2.0, interval_days=6, repetitions=2, quality=4)
    assert result.interval_days == 12  # ceil(6 * 2.0)
    assert result.repetitions == 3


def test_easiness_floors_at_one_point_three():
    result = sm2_update(easiness=1.3, interval_days=10, repetitions=5, quality=3)
    assert result.easiness == 1.3
    assert result.interval_days == 13  # ceil(10 * 1.3)


def test_quality_out_of_range_rejected():
    with pytest.raises(ValueError):
        sm2_update(easiness=2.5, interval_days=1, repetitions=0, quality=6)
