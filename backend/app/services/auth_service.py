from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from app.core.security import hash_password, verify_password
from app.database.mongodb import MongoDBConnectionError, get_database
from app.models.user import UserRegister


USERS_COLLECTION = "users"


class AuthServiceError(RuntimeError):
    """Raised when an authentication database operation fails."""


class UserAlreadyExistsError(AuthServiceError):
    """Raised when a registration email is already used."""


class InvalidCredentialsError(AuthServiceError):
    """Raised when login credentials are invalid."""


def _users_collection():
    try:
        return get_database()[USERS_COLLECTION]
    except MongoDBConnectionError as exc:
        raise AuthServiceError(str(exc)) from exc


def _serialize_user(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "username": user["username"],
        "email": user["email"],
    }


def get_user_by_email(email: str) -> dict | None:
    normalized_email = email.strip().lower()

    try:
        return _users_collection().find_one({"email": normalized_email})
    except PyMongoError as exc:
        raise AuthServiceError(f"Failed to fetch user by email: {exc}") from exc


def get_user_by_id(user_id: str) -> dict | None:
    try:
        object_id = ObjectId(user_id)
    except InvalidId:
        return None

    try:
        return _users_collection().find_one({"_id": object_id})
    except PyMongoError as exc:
        raise AuthServiceError(f"Failed to fetch user by id: {exc}") from exc


def create_user(user_data: UserRegister) -> dict:
    normalized_email = str(user_data.email).strip().lower()

    if get_user_by_email(normalized_email):
        raise UserAlreadyExistsError("Email is already registered.")

    user_document = {
        "username": user_data.username.strip(),
        "email": normalized_email,
        # Store only a password hash. Plaintext passwords must never be persisted.
        "hashed_password": hash_password(user_data.password),
        "created_at": datetime.now(timezone.utc),
    }

    try:
        result = _users_collection().insert_one(user_document)
    except PyMongoError as exc:
        raise AuthServiceError(f"Failed to create user: {exc}") from exc

    user_document["_id"] = result.inserted_id
    return _serialize_user(user_document)


def authenticate_user(email: str, password: str) -> dict:
    user = get_user_by_email(email)
    if not user:
        raise InvalidCredentialsError("Invalid email or password.")

    if not verify_password(password, user["hashed_password"]):
        raise InvalidCredentialsError("Invalid email or password.")

    return _serialize_user(user)
