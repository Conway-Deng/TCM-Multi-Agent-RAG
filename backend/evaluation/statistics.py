from __future__ import annotations

import math
import random
import statistics


def bootstrap_ci(values: list[float], *, seed: int = 20260815, samples: int = 2000, confidence: float = 0.95) -> tuple[float, float] | None:
    if len(values) < 2:
        return None
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choice(values) for _ in values) for _ in range(samples))
    alpha = (1 - confidence) / 2
    return means[int(alpha * samples)], means[min(samples - 1, int((1 - alpha) * samples))]


def summarize(values: list[float]) -> dict[str, float | int | list[float] | None]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "standard_deviation": None, "bootstrap_ci_95": None}
    interval = bootstrap_ci(values)
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "standard_deviation": statistics.stdev(values) if len(values) > 1 else 0.0,
        "bootstrap_ci_95": list(interval) if interval else None,
    }


def paired_comparison(left: list[float], right: list[float]) -> dict[str, float | int | None]:
    pairs = list(zip(left, right))
    differences = [b - a for a, b in pairs]
    if not differences:
        return {"pairs": 0, "mean_difference": None, "standardized_effect": None}
    standard_deviation = statistics.stdev(differences) if len(differences) > 1 else 0.0
    effect = statistics.fmean(differences) / standard_deviation if standard_deviation else None
    return {"pairs": len(pairs), "mean_difference": statistics.fmean(differences), "standardized_effect": effect}
