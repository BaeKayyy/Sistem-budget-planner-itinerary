from passlib.context import CryptContext


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password for safe storage."""
    # Passwords must never be stored as plaintext. A bcrypt hash protects users
    # even if stored account data is exposed later.
    return password_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    return password_context.verify(plain_password, hashed_password)
