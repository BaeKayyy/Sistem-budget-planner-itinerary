from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.auth import (
    JWTConfigurationError,
    JWTTokenError,
    create_access_token,
    verify_access_token,
)
from app.models.user import TokenResponse, UserLogin, UserRegister, UserResponse
from app.services.auth_service import (
    AuthServiceError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
    authenticate_user,
    create_user,
    get_user_by_id,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme)) -> UserResponse:
    try:
        payload = verify_access_token(token)
    except JWTTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except JWTConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    user_id = payload["sub"]

    try:
        user = get_user_by_id(user_id)
    except AuthServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user was not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserResponse(
        id=str(user["_id"]),
        username=user["username"],
        email=user["email"],
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    description="Create a new user account.",
)
def register_user(user_data: UserRegister) -> UserResponse:
    try:
        user = create_user(user_data)
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except AuthServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return UserResponse(**user)


@router.post(
    "/login",
    response_model=TokenResponse,
    description="Authenticate a user and return a bearer access token.",
)
def login_user(credentials: UserLogin) -> TokenResponse:
    try:
        user = authenticate_user(
            email=str(credentials.email),
            password=credentials.password,
        )
        access_token = create_access_token({"sub": user["id"]})
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except JWTConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except AuthServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return TokenResponse(access_token=access_token, token_type="bearer")


@router.get(
    "/me",
    response_model=UserResponse,
    description="Return the currently authenticated user.",
)
def read_current_user(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    return current_user
