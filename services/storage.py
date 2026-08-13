from __future__ import annotations

import json
import mimetypes
import re
import uuid

from dataclasses import (
    asdict,
    dataclass,
)
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from typing import Any

from fastapi import Request


def utc_now_iso() -> str:
    return (
        datetime.now(
            timezone.utc
        )
        .isoformat()
    )


def ensure_storage(
    data_root: Path,
) -> None:
    (
        data_root
        / "sessions"
    ).mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        data_root
        / "generated"
    ).mkdir(
        parents=True,
        exist_ok=True,
    )


def safe_extension(
    filename: str,
) -> str:
    suffix = (
        Path(filename)
        .suffix.lower()
    )

    if suffix in {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    }:
        return suffix

    return ".jpg"


@dataclass
class SessionRecord:
    sessionId: str
    status: str
    heightCm: float
    createdAt: str
    updatedAt: str
    frontPhotoPath: str | None = None
    sidePhotoPath: str | None = None
    avatarPath: str | None = None
    measurements: dict[str, Any] | None = None
    confidence: float | None = None
    message: str | None = None
    error: str | None = None


class SessionStore:
    def __init__(
        self,
        data_root: Path,
    ):
        self.data_root = (
            data_root
        )

        ensure_storage(
            self.data_root
        )

    def session_dir(
        self,
        session_id: str,
    ) -> Path:
        clean_id = re.sub(
            r"[^a-zA-Z0-9_-]",
            "",
            session_id,
        )

        return (
            self.data_root
            / "sessions"
            / clean_id
        )

    def metadata_path(
        self,
        session_id: str,
    ) -> Path:
        return (
            self.session_dir(
                session_id
            )
            / "session.json"
        )

    def create_session(
        self,
        height_cm: float,
    ) -> SessionRecord:
        session_id = (
            "twin_"
            + uuid.uuid4().hex
        )

        now = (
            utc_now_iso()
        )

        record = (
            SessionRecord(
                sessionId=session_id,
                status="queued",
                heightCm=height_cm,
                createdAt=now,
                updatedAt=now,
                message=(
                    "Digital Twin session created."
                ),
            )
        )

        directory = (
            self.session_dir(
                session_id
            )
        )

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._write(
            record
        )

        return record

    def save_input_image(
        self,
        session_id: str,
        logical_name: str,
        original_filename: str,
        content: bytes,
    ) -> Path:
        directory = (
            self.session_dir(
                session_id
            )
            / "input"
        )

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        extension = (
            safe_extension(
                original_filename
            )
        )

        path = (
            directory
            / (
                logical_name
                + extension
            )
        )

        path.write_bytes(
            content
        )

        return path

    def get_session(
        self,
        session_id: str,
    ) -> SessionRecord | None:
        path = (
            self.metadata_path(
                session_id
            )
        )

        if not path.exists():
            return None

        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        return (
            SessionRecord(
                **data
            )
        )

    def update_session(
        self,
        session_id: str,
        updates: dict[str, Any],
    ) -> SessionRecord:
        current = (
            self.get_session(
                session_id
            )
        )

        if current is None:
            raise RuntimeError(
                "Session not found."
            )

        data = asdict(
            current
        )

        data.update(
            updates
        )

        data["updatedAt"] = (
            utc_now_iso()
        )

        record = (
            SessionRecord(
                **data
            )
        )

        self._write(
            record
        )

        return record

    def _write(
        self,
        record: SessionRecord,
    ) -> None:
        path = (
            self.metadata_path(
                record.sessionId
            )
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            json.dumps(
                asdict(record),
                indent=2,
            ),
            encoding="utf-8",
        )


def public_avatar_url(
    request: Request,
    public_base_url: str,
    avatar_path: Path,
    data_root: Path,
) -> str:
    generated_root = (
        data_root
        / "generated"
    ).resolve()

    resolved = (
        avatar_path.resolve()
    )

    try:
        relative = (
            resolved.relative_to(
                generated_root
            )
        )
    except ValueError as exc:
        raise RuntimeError(
            "Avatar path is outside generated storage."
        ) from exc

    base = (
        public_base_url
        or str(
            request.base_url
        ).rstrip("/")
    )

    return (
        f"{base}/generated/"
        f"{relative.as_posix()}"
    )
