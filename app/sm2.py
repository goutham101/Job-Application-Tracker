import math
from dataclasses import dataclass


@dataclass
class SM2State:
    easiness: float
    interval_days: int
    repetitions: int


def sm2_update(easiness: float, interval_days: int, repetitions: int, quality: int) -> SM2State:
    """Canonical SM-2. On a lapse (quality < 3), easiness is left unchanged —
    many implementations get this wrong; the spec only updates it on a pass."""
    if not 0 <= quality <= 5:
        raise ValueError("quality must be between 0 and 5")

    if quality < 3:
        return SM2State(easiness=easiness, interval_days=1, repetitions=0)

    if repetitions == 0:
        new_interval = 1
    elif repetitions == 1:
        new_interval = 6
    else:
        new_interval = math.ceil(interval_days * easiness)

    new_easiness = easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_easiness = max(1.3, new_easiness)

    return SM2State(easiness=new_easiness, interval_days=new_interval, repetitions=repetitions + 1)
