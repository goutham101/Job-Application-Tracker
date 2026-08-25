import os
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

# Deployed with no auth, every route in app/main.py lets any visitor with the
# URL read, create, or delete tracker data. Setting API_KEY requires a
# matching X-API-Key header on every request; leaving it unset keeps local
# dev/tests working exactly as before.
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(provided: str | None = Security(_api_key_header)) -> None:
    expected = os.environ.get("API_KEY")
    if not expected:
        return
    if provided is None or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
