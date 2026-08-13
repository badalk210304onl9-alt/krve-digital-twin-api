from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from schemas import (
    HealthResponse,
    ReconstructionCreateResponse,
    ReconstructionSessionResponse,
)
from services.reconstruction import run_reconstruction
from services.storage import (
    SessionStore,
    ensure_storage,
    public_avatar_url,
)


APP_NAME = "KRVE Digital Twin API"
APP_VERSION = "0.1.0"

DATA_ROOT = Path(
    os.getenv(
        "DIGITAL_TWIN_DATA_ROOT",
        "./data",
    )
).resolve()

API_KEY = os.getenv(
    "DIGITAL_TWIN_API_KEY",
    "",
).strip()

PUBLIC_BASE_URL = os.getenv(
    "DIGITAL_TWIN_PUBLIC_BASE_URL",
    "",
).strip().rstrip("/")

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "DIGITAL_TWIN_ALLOWED_ORIGINS",
        "http://localhost:3000",
    ).split(",")
    if origin.strip()
]

MAX_IMAGE_BYTES = int(
    os.getenv(
        "DIGITAL_TWIN_MAX_IMAGE_BYTES",
        str(12 * 1024 * 1024),
    )
)

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

ensure_storage(DATA_ROOT)

store = SessionStore(DATA_ROOT)

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

generated_dir = DATA_ROOT / "generated"
generated_dir.mkdir(
    parents=True,
    exist_ok=True,
)

app.mount(
    "/generated",
    StaticFiles(
        directory=str(
            generated_dir
        )
    ),
    name="generated",
)


def require_api_key(
    authorization: Annotated[
        str | None,
        Header(),
    ] = None,
) -> None:
    """
    If DIGITAL_TWIN_API_KEY is empty,
    auth is disabled for local development.

    In production set DIGITAL_TWIN_API_KEY
    and call with:
      Authorization: Bearer <key>
    """

    if not API_KEY:
        return

    expected = (
        f"Bearer {API_KEY}"
    )

    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized.",
        )


async def validate_upload(
    file: UploadFile,
    label: str,
) -> bytes:
    if (
        file.content_type
        not in ALLOWED_IMAGE_TYPES
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{label} must be JPG, PNG or WEBP."
            ),
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} is empty.",
        )

    if (
        len(content)
        > MAX_IMAGE_BYTES
    ):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"{label} is too large."
            ),
        )

    return content


@app.get(
    "/health",
    response_model=HealthResponse,
)
async def health() -> HealthResponse:
    return HealthResponse(
        success=True,
        service=APP_NAME,
        version=APP_VERSION,
        engineConfigured=bool(
            os.getenv(
                "DIGITAL_TWIN_ENGINE_COMMAND",
                "",
            ).strip()
        ),
    )


@app.post(
    "/v1/reconstruct",
    response_model=ReconstructionCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[
        Depends(
            require_api_key
        )
    ],
)
async def create_reconstruction(
    request: Request,
    background_tasks: BackgroundTasks,
    frontPhoto: Annotated[
        UploadFile,
        File(...),
    ],
    sidePhoto: Annotated[
        UploadFile,
        File(...),
    ],
    heightCm: Annotated[
        float,
        Form(...),
    ],
) -> ReconstructionCreateResponse:
    if (
        heightCm < 120
        or heightCm > 220
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "heightCm must be between 120 and 220."
            ),
        )

    front_bytes = (
        await validate_upload(
            frontPhoto,
            "Front photo",
        )
    )

    side_bytes = (
        await validate_upload(
            sidePhoto,
            "Side photo",
        )
    )

    session = store.create_session(
        height_cm=heightCm,
    )

    front_path = (
        store.save_input_image(
            session_id=session.sessionId,
            logical_name="front",
            original_filename=(
                frontPhoto.filename
                or "front.jpg"
            ),
            content=front_bytes,
        )
    )

    side_path = (
        store.save_input_image(
            session_id=session.sessionId,
            logical_name="side",
            original_filename=(
                sidePhoto.filename
                or "side.jpg"
            ),
            content=side_bytes,
        )
    )

    store.update_session(
        session.sessionId,
        {
            "status": "queued",
            "frontPhotoPath": str(
                front_path
            ),
            "sidePhotoPath": str(
                side_path
            ),
        },
    )

    background_tasks.add_task(
        process_session,
        session.sessionId,
        front_path,
        side_path,
        heightCm,
    )

    return ReconstructionCreateResponse(
        success=True,
        sessionId=session.sessionId,
        status="queued",
        avatarUrl=None,
        measurements=None,
        confidence=None,
        message=(
            "Digital Twin reconstruction queued."
        ),
    )


@app.get(
    "/v1/sessions/{session_id}",
    response_model=ReconstructionSessionResponse,
    dependencies=[
        Depends(
            require_api_key
        )
    ],
)
async def get_session(
    session_id: str,
    request: Request,
) -> ReconstructionSessionResponse:
    session = store.get_session(
        session_id
    )

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )

    avatar_url = None

    if session.avatarPath:
        avatar_url = (
            public_avatar_url(
                request=request,
                public_base_url=PUBLIC_BASE_URL,
                avatar_path=Path(
                    session.avatarPath
                ),
                data_root=DATA_ROOT,
            )
        )

    return ReconstructionSessionResponse(
        success=True,
        sessionId=session.sessionId,
        status=session.status,
        avatarUrl=avatar_url,
        measurements=session.measurements,
        confidence=session.confidence,
        message=session.message,
        error=session.error,
    )


def process_session(
    session_id: str,
    front_path: Path,
    side_path: Path,
    height_cm: float,
) -> None:
    store.update_session(
        session_id,
        {
            "status": "processing",
            "message": (
                "Reconstruction engine started."
            ),
            "error": None,
        },
    )

    output_path = (
        generated_dir
        / f"{session_id}.glb"
    )

    try:
        result = run_reconstruction(
            front_photo=front_path,
            side_photo=side_path,
            height_cm=height_cm,
            output_glb=output_path,
            session_dir=(
                store.session_dir(
                    session_id
                )
            ),
        )

        store.update_session(
            session_id,
            {
                "status": "completed",
                "avatarPath": str(
                    output_path
                ),
                "measurements": (
                    result.measurements
                ),
                "confidence": (
                    result.confidence
                ),
                "message": (
                    "Digital Twin ready."
                ),
                "error": None,
            },
        )

    except Exception as exc:
        store.update_session(
            session_id,
            {
                "status": "failed",
                "avatarPath": None,
                "message": (
                    "Digital Twin reconstruction failed."
                ),
                "error": str(exc),
            },
        )


@app.exception_handler(
    HTTPException
)
async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": (
                exc.detail
                if isinstance(
                    exc.detail,
                    str,
                )
                else "Request failed."
            ),
        },
    )
