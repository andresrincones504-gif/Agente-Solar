from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
from jose import JWTError, jwt
from app.core.config import get_settings

settings = get_settings()

# bcrypt directo: passlib 1.7 ya no se mantiene y con bcrypt 4.x llena los logs de avisos.
# Los hashes son los mismos ($2b$), así que las contraseñas guardadas siguen funcionando.
BCRYPT_MAX_BYTES = 72  # bcrypt solo usa los primeros 72 bytes; passlib también los recortaba


def _bytes(password: str) -> bytes:
    return password.encode("utf-8")[:BCRYPT_MAX_BYTES]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_bytes(plain_password), hashed_password.encode("utf-8"))
    except (ValueError, TypeError, AttributeError):
        return False  # hash vacío o con otro formato


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_bytes(password), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
