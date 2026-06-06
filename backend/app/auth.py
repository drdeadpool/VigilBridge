import secrets
from typing import Annotated

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(name="X-Api-Key", auto_error=False)


def _require_key(provided: str | None, expected: str, purpose: str) -> None:
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{purpose} API key is not configured",
        )
    if provided is None or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


def require_ingest_key(
    provided: Annotated[str | None, Security(api_key_header)],
) -> None:
    _require_key(provided, settings.ingest_api_key, "Ingest")


def require_read_key(
    provided: Annotated[str | None, Security(api_key_header)],
) -> None:
    _require_key(provided, settings.read_api_key, "Read")
