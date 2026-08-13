from __future__ import annotations

import os
import shlex
import subprocess

from dataclasses import dataclass
from pathlib import Path

from services.measurements import (
    load_engine_measurements,
)


@dataclass
class ReconstructionResult:
    measurements: dict[
        str,
        float | None,
    ]
    confidence: float | None


def run_reconstruction(
    *,
    front_photo: Path,
    side_photo: Path,
    height_cm: float,
    output_glb: Path,
    session_dir: Path,
) -> ReconstructionResult:
    """
    Adapter for the actual 3D reconstruction engine.

    The backend does NOT generate a fake mannequin.

    Configure DIGITAL_TWIN_ENGINE_COMMAND with
    placeholders:

      {front}
      {side}
      {height}
      {output}
      {session}

    Example concept:

      python engine/run.py
        --front "{front}"
        --side "{side}"
        --height "{height}"
        --output "{output}"
        --session "{session}"

    The configured engine must create a real .glb
    file at {output}.

    Optionally it can write:
      {session}/measurements.json
    """

    command_template = (
        os.getenv(
            "DIGITAL_TWIN_ENGINE_COMMAND",
            "",
        ).strip()
    )

    if not command_template:
        raise RuntimeError(
            "No reconstruction engine is configured. "
            "Set DIGITAL_TWIN_ENGINE_COMMAND."
        )

    output_glb.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = (
        command_template
        .replace(
            "{front}",
            str(
                front_photo.resolve()
            ),
        )
        .replace(
            "{side}",
            str(
                side_photo.resolve()
            ),
        )
        .replace(
            "{height}",
            str(height_cm),
        )
        .replace(
            "{output}",
            str(
                output_glb.resolve()
            ),
        )
        .replace(
            "{session}",
            str(
                session_dir.resolve()
            ),
        )
    )

    timeout_seconds = int(
        os.getenv(
            "DIGITAL_TWIN_ENGINE_TIMEOUT_SECONDS",
            "900",
        )
    )

    completed = (
        subprocess.run(
            shlex.split(
                command
            ),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    )

    if (
        completed.returncode
        != 0
    ):
        stderr = (
            completed.stderr
            or completed.stdout
            or "Unknown reconstruction error."
        )

        raise RuntimeError(
            "Reconstruction engine failed: "
            + stderr[-3000:]
        )

    if (
        not output_glb.exists()
    ):
        raise RuntimeError(
            "Reconstruction engine completed but did not create the GLB avatar."
        )

    if (
        output_glb.stat().st_size
        < 1024
    ):
        raise RuntimeError(
            "Generated GLB is unexpectedly small."
        )

    (
        measurements,
        confidence,
    ) = (
        load_engine_measurements(
            session_dir,
            height_cm,
        )
    )

    return (
        ReconstructionResult(
            measurements=measurements,
            confidence=confidence,
        )
    )
