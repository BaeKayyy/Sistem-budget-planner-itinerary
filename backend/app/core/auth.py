import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from jose import ExpiredSignatureError, JWTError, jwt


class JWTConfigurationError(RuntimeError):
    """Raised when JWT environment configuration is missing or invalid."""


class JWTTokenError(RuntimeError):
    """Raised when a JWT cannot be verified."""


BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BACKEND_DIR / ".env"

load_dotenv(ENV_PATH)


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise JWTConfigurationError(
            f"Missing environment variable: {name}. Add it to {ENV_PATH}."
        )

    return value


def _get_access_token_expire_minutes() -> int:
    raw_value = _get_required_env("ACCESS_TOKEN_EXPIRE_MINUTES")

    try:
        expire_minutes = int(raw_value)
    except ValueError as exc:
        raise JWTConfigurationError(
            "ACCESS_TOKEN_EXPIRE_MINUTES must be a valid integer."
        ) from exc

    if expire_minutes <= 0:
        raise JWTConfigurationError(
            "ACCESS_TOKEN_EXPIRE_MINUTES must be greater than 0."
        )

    return expire_minutes


def create_token_payload(data: dict) -> dict:
    """Create a JWT payload with a required user identifier and expiration."""
    if not data.get("sub"):
        raise JWTTokenError("Token payload must include a user identifier in 'sub'.")

    expire_minutes = _get_access_token_expire_minutes()
    expire_at = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)

    payload = data.copy()
    # Expiration limits how long a stolen token can be reused.
    payload.update({"exp": expire_at})

    return payload


def create_access_token(data: dict) -> str:
    """Create a signed JWT access token."""
    secret_key = _get_required_env("SECRET_KEY")
    algorithm = os.getenv("ALGORITHM", "HS256")

    if algorithm != "HS256":
        raise JWTConfigurationError("Only HS256 is supported for access tokens.")

    payload = create_token_payload(data)
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def verify_access_token(token: str) -> dict:
    """Verify a JWT access token and return its decoded payload."""
    secret_key = _get_required_env("SECRET_KEY")
    algorithm = os.getenv("ALGORITHM", "HS256")

    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
    except ExpiredSignatureError as exc:
        raise JWTTokenError("Access token has expired.") from exc
    except JWTError as exc:
        raise JWTTokenError("Access token is invalid or malformed.") from exc

    if not payload.get("sub"):
        raise JWTTokenError("Access token is missing a user identifier.")

    return payload
