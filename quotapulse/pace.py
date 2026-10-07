"""Burn-rate forecast from recent usage history."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass(frozen=True)
class Forecast:
    rate_pct_per_hour: Optional[float]
    reaches_threshold_at: Optional[float]


def forecast(
    points: Sequence[tuple[float, float]],
    threshold: float,
    now: float,
    window_s: float = 1800.0,
) -> Forecast:
    """Estimate the burn rate and when usage will reach `threshold`.

    `points` are (timestamp, used_pct) pairs in time order. A drop in used_pct
    means old usage aged out of the rolling window or the window reset, so only
    points after the last drop are used. Needs two points in the last `window_s`.
    """
    recent = [(t, u) for t, u in _after_last_drop(points) if now - t <= window_s]
    if len(recent) < 2:
        return Forecast(None, None)

    rate = _slope(recent) * 3600.0
    if rate <= 0:
        return Forecast(rate, None)

    current = recent[-1][1]
    if current >= threshold:
        return Forecast(rate, now)

    seconds_left = (threshold - current) / (rate / 3600.0)
    return Forecast(rate, now + seconds_left)


def _after_last_drop(points: Sequence[tuple[float, float]]) -> Sequence[tuple[float, float]]:
    start = 0
    for i in range(1, len(points)):
        if points[i][1] < points[i - 1][1]:
            start = i
    return points[start:]


def _slope(points: Sequence[tuple[float, float]]) -> float:
    """Least-squares slope of used_pct per second."""
    n = len(points)
    mean_t = sum(t for t, _ in points) / n
    mean_u = sum(u for _, u in points) / n
    var = sum((t - mean_t) ** 2 for t, _ in points)
    if var == 0:
        return 0.0
    cov = sum((t - mean_t) * (u - mean_u) for t, u in points)
    return cov / var
