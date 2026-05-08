import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError


class MongoDBConnectionError(RuntimeError):
    """Raised when MongoDB configuration or connection fails."""


BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BACKEND_DIR / ".env"

load_dotenv(ENV_PATH)

_mongo_client: MongoClient | None = None
_database: Database | None = None


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise MongoDBConnectionError(
            f"Missing environment variable: {name}. Add it to {ENV_PATH}."
        )

    return value


def get_mongo_client() -> MongoClient:
    global _mongo_client

    if _mongo_client is not None:
        return _mongo_client

    mongodb_url = _get_required_env("MONGODB_URL")

    try:
        client = MongoClient(mongodb_url, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
    except ServerSelectionTimeoutError as exc:
        raise MongoDBConnectionError(
            "Failed to connect to MongoDB. Check MONGODB_URL and make sure MongoDB is running."
        ) from exc
    except PyMongoError as exc:
        raise MongoDBConnectionError(f"MongoDB connection failed: {exc}") from exc

    _mongo_client = client
    return _mongo_client


def get_database() -> Database:
    global _database

    if _database is not None:
        return _database

    database_name = _get_required_env("DATABASE_NAME")
    _database = get_mongo_client()[database_name]

    return _database


def get_database_status() -> dict:
    database_name = _get_required_env("DATABASE_NAME")
    get_mongo_client().admin.command("ping")

    return {
        "connected": True,
        "database_name": database_name,
    }


def close_mongo_connection() -> None:
    global _mongo_client, _database

    if _mongo_client is not None:
        _mongo_client.close()

    _mongo_client = None
    _database = None
