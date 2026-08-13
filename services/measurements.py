from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SUPPORTED_KEYS = {
    "heightCm",
    "shoulderCm",
    "chestCm",
    "waistCm",
    "hipCm",
    "inseamCm",
    "torsoCm",
}


def load_engine_measurements(
    session_dir: Path,
    fallback_height_cm: float,
) -> tuple[
    dict[str, float | None],
    float | None,
]:
    """
    The real reconstruction engine can write:

      <session_dir>/measurements.json

    Example:
    {
      "heightCm": 170,
      "shoulderCm": 43.2,
      "chestCm": 94.1,
      "waistCm": 80.4,
      "hipCm": 96.0,
      "inseamCm": 78.8,
      "torsoCm": 53.1,
      "confidence": 0.86
    }

    This service deliberately does NOT invent
    measurements when the engine did not
    calculate them.
    """

    path = (
        session_dir
        / "measurements.json"
    )

    if not path.exists():
        return (
            {
                "heightCm": (
                    fallback_height_cm
                ),
                "shoulderCm": None,
                "chestCm": None,
                "waistCm": None,
                "hipCm": None,
                "inseamCm": None,
                "torsoCm": None,
            },
            None,
        )

    raw: dict[str, Any] = (
        json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    )

    output: dict[
        str,
        float | None,
    ] = {}

    for key in SUPPORTED_KEYS:
        value = raw.get(
            key
        )

        if value is None:
            output[key] = (
                None
            )
            continue

        try:
            output[key] = (
                float(value)
            )
        except (
            TypeError,
            ValueError,
        ):
            output[key] = (
                None
            )

    if (
        output.get(
            "heightCm"
        )
        is None
    ):
        output["heightCm"] = (
            fallback_height_cm
        )

    confidence = raw.get(
        "confidence"
    )

    try:
        parsed_confidence = (
            float(confidence)
            if confidence
            is not None
            else None
        )
    except (
        TypeError,
        ValueError,
    ):
        parsed_confidence = (
            None
        )

    return (
        output,
        parsed_confidence,
    )
