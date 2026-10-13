"""One fixed, single-factor robust motion estimator; inherited gates remain intact."""

from __future__ import annotations

from statistics import median
from types import FunctionType
from typing import Any, Literal

from amidst.engineering.perception import Measurement, PerceptionResult
from amidst.research_accuracy import pixel

Strategy = Literal["BASELINE", "ROBUST_THREE_CLEAN"]
STRATEGIES: tuple[Strategy, ...] = ("BASELINE", "ROBUST_THREE_CLEAN")


def clean_window(history: list[Measurement], config: pixel.PixelContinuityConfig) -> bool:
    rows = history[-3:]
    return (
        len(rows) == 3
        and all(
            row.status == "DETECTED" and row.local_alternative_count == 0 and row.uncertainty <= 0.4
            for row in rows
        )
        and all(
            0 < right.timestamp - left.timestamp <= config.max_gap_s
            for left, right in zip(rows, rows[1:], strict=False)
        )
    )


def robust_prediction(
    history: list[Measurement],
    timestamp: float,
    config: pixel.PixelContinuityConfig,
) -> tuple[float, float] | None:
    if not config.use_velocity or not clean_window(history, config):
        return None
    rows = history[-3:]
    velocity = tuple(
        float(
            median(
                (right.contact_pixel[channel] - left.contact_pixel[channel])
                / (right.timestamp - left.timestamp)
                for index, left in enumerate(rows)
                for right in rows[index + 1 :]
            )
        )
        for channel in (0, 1)
    )
    dt = timestamp - rows[-1].timestamp
    return (
        rows[-1].contact_pixel[0] + velocity[0] * dt,
        rows[-1].contact_pixel[1] + velocity[1] * dt,
    )


def reassociate(
    perception: PerceptionResult,
    config: pixel.PixelContinuityConfig,
    *,
    strategy: Strategy = "ROBUST_THREE_CLEAN",
) -> PerceptionResult:
    functions = local_functions(strategy)
    result: PerceptionResult = functions["reassociate_perception_v2"](perception, config=config)
    return result


def local_functions(strategy: Strategy) -> dict[str, Any]:
    """Clone only function globals; the inherited module is never mutated.

    Both normal execution and trace instrumentation use this private dictionary,
    so concurrent calls and exceptions cannot alter the original pixel pipeline.
    """
    if strategy not in STRATEGIES:
        raise ValueError("REPAIR05_STRATEGY_DENIED")
    functions = dict(vars(pixel))
    original = pixel._prediction

    def prediction(
        history: list[Measurement],
        timestamp: float,
        config: pixel.PixelContinuityConfig,
    ) -> tuple[float, float]:
        return robust_prediction(history, timestamp, config) or original(history, timestamp, config)

    functions["_prediction"] = prediction if strategy == "ROBUST_THREE_CLEAN" else original
    for name in ("_candidates", "reassociate_perception_v2"):
        inherited = getattr(pixel, name)
        cloned = FunctionType(
            inherited.__code__, functions, inherited.__name__, inherited.__defaults__
        )
        cloned.__kwdefaults__ = inherited.__kwdefaults__
        functions[name] = cloned
    return functions
