 from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=50,
        description="Unique display name for the user.",
        examples=["jogja_explorer"],
    )
    email: EmailStr = Field(
        description="Valid email address used for account identification.",
        examples=["user@example.com"],
    )


class UserRegister(UserBase):
    password: str = Field(
        min_length=8,
        description="Plain password submitted during registration.",
        examples=["strongpassword123"],
    )


class UserLogin(BaseModel):
    email: EmailStr = Field(
        description="Registered user email address.",
        examples=["user@example.com"],
    )
    password: str = Field(
        min_length=8,
        description="Plain password submitted during login.",
        examples=["strongpassword123"],
    )


class UserResponse(UserBase):
    id: str = Field(
        description="Public user identifier returned by the API.",
        examples=["665f1c2d8b4f5f0012a34567"],
    )

    # Passwords must never be returned by API responses.
    # Only hashed passwords should be stored later, and even hashes stay server-side.


class TokenResponse(BaseModel):
    access_token: str = Field(
        description="JWT access token used for authenticated requests.",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
    )
    token_type: str = Field(
        default="bearer",
        description="Authentication scheme for the access token.",
        examples=["bearer"],
    )
