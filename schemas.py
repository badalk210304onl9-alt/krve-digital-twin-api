from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


SessionStatus = Literal[
    "queued",
    "processing",
    "completed",
    "failed",
]


class Measurements(
    BaseModel
):
    heightCm: float | None = None
    shoulderCm: float | None = None
    chestCm: float | None = None
    waistCm: float | None = None
    hipCm: float | None = None
    inseamCm: float | None = None
    torsoCm: float | None = None


class HealthResponse(
    BaseModel
):
    success: bool
    service: str
    version: str
    engineConfigured: bool


class ReconstructionCreateResponse(
    BaseModel
):
    success: bool
    sessionId: str
    status: SessionStatus
    avatarUrl: str | None = None
    measurements: Measurements | None = None
    confidence: float | None = None
    message: str | None = None


class ReconstructionSessionResponse(
    ReconstructionCreateResponse
):
    error: str | None = None
