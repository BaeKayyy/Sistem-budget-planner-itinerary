import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError


BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BACKEND_DIR / ".env"

load_dotenv(ENV_PATH)

_client: MongoClient | None = None
_database: Database | None = None


class MongoDBConnectionError(RuntimeError):
    """Raised when MongoDB cannot be configured or reached."""


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise MongoDBConnectionError(f"Missing environment variable: {name}")
    return value


def get_mongo_client() -> MongoClient:
    global _client

    if _client is not None:
        return _client

    try:
        _client = MongoClient(
            get_required_env("MONGODB_URL"),
            serverSelectionTimeoutMS=5000,
        )
        _client.admin.command("ping")
    except ServerSelectionTimeoutError as exc:
        raise MongoDBConnectionError("MongoDB is not reachable.") from exc
    except PyMongoError as exc:
        raise MongoDBConnectionError(f"MongoDB connection failed: {exc}") from exc

    return _client


def get_database() -> Database:
    global _database

    if _database is None:
        _database = get_mongo_client()[get_required_env("DATABASE_NAME")]

    return _database


def get_database_status() -> dict:
    database_name = get_required_env("DATABASE_NAME")
    get_mongo_client().admin.command("ping")
    return {"connected": True, "database_name": database_name}


def close_mongo_connection() -> None:
    global _client, _database

    if _client is not None:
        _client.close()

    _client = None
    _database = None
