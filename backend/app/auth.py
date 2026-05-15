import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext
from pymongo.errors import PyMongoError

from .database import MongoDBConnectionError, get_database
from .models import LoginRequest, TokenResponse, User, UserRegister


BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BACKEND_DIR / ".env"
USERS_COLLECTION = "users"

load_dotenv(ENV_PATH)

router = APIRouter(prefix="/auth", tags=["Authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def users_collection():
    try:
        return get_database()[USERS_COLLECTION]
    except MongoDBConnectionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def get_jwt_setting(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise HTTPException(status_code=500, detail=f"Missing JWT setting: {name}")
    return value


def create_access_token(data: dict) -> str:
    if not data.get("sub"):
        raise HTTPException(status_code=500, detail="Token subject is required.")

    expire_minutes = int(get_jwt_setting("ACCESS_TOKEN_EXPIRE_MINUTES"))
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)

    return jwt.encode(
        payload,
        get_jwt_setting("SECRET_KEY"),
        algorithm=os.getenv("ALGORITHM", "HS256"),
    )


def verify_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            get_jwt_setting("SECRET_KEY"),
            algorithms=[os.getenv("ALGORITHM", "HS256")],
        )
    except ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is missing a user id.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


def serialize_user(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "username": user["username"],
        "email": user["email"],
    }


def get_user_by_email(email: str) -> dict | None:
    try:
        return users_collection().find_one({"email": email.strip().lower()})
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read user: {exc}") from exc


def get_user_by_id(user_id: str) -> dict | None:
    try:
        object_id = ObjectId(user_id)
    except InvalidId:
        return None

    try:
        return users_collection().find_one({"_id": object_id})
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read user: {exc}") from exc


def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    payload = verify_access_token(token)
    user = get_user_by_id(payload["sub"])

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user was not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return User(**serialize_user(user))


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserRegister) -> User:
    email = str(user_data.email).strip().lower()

    if get_user_by_email(email):
        raise HTTPException(status_code=409, detail="Email is already registered.")

    user_document = {
        "username": user_data.username.strip(),
        "email": email,
        "hashed_password": hash_password(user_data.password),
        "created_at": datetime.now(timezone.utc),
    }

    try:
        result = users_collection().insert_one(user_document)
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create user: {exc}") from exc

    user_document["_id"] = result.inserted_id
    return User(**serialize_user(user_document))


@router.post("/login", response_model=TokenResponse)
def login_user(credentials: LoginRequest) -> TokenResponse:
    user = get_user_by_email(str(credentials.email))

    if not user or not verify_password(credentials.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token({"sub": str(user["_id"])})
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=User)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user
