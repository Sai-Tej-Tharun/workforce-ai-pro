"""Password hashing, JWT handling, RBAC dependencies, login throttling."""
import hashlib, hmac, os, re, secrets, time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import jwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User, ROLE_ADMIN, ROLE_HR, ROLE_MANAGER, ROLE_EMPLOYEE

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
_ITER = 210_000


# ---------- passwords ----------
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITER)
    return f"pbkdf2_sha256${_ITER}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, digest = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(dk.hex(), digest)
    except Exception:
        return False


def validate_password_strength(password: str) -> Optional[str]:
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must contain letters and digits"
    return None


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---------- JWT ----------
def _make_token(sub: str, kind: str, expires: timedelta, extra: Optional[dict] = None) -> tuple[str, datetime]:
    exp = datetime.now(timezone.utc) + expires
    payload = {"sub": sub, "type": kind, "exp": exp, "iat": datetime.now(timezone.utc), "jti": secrets.token_hex(8)}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM), exp


def create_access_token(user: User):
    return _make_token(str(user.id), "access", timedelta(minutes=settings.ACCESS_TOKEN_MINUTES), {"role": user.role})


def create_refresh_token(user: User):
    return _make_token(str(user.id), "refresh", timedelta(days=settings.REFRESH_TOKEN_DAYS))


def decode_token(token: str, expected: str = "access") -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired", headers={"WWW-Authenticate": "Bearer"})
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token", headers={"WWW-Authenticate": "Bearer"})
    if payload.get("type") != expected:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type")
    return payload


def user_from_token(db: Session, token: str) -> User:
    payload = decode_token(token)
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User inactive or not found")
    return user


# ---------- dependencies ----------
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    return user_from_token(db, token)


def require_roles(*roles: str) -> Callable:
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role: {', '.join(roles)}")
        return user
    return checker


admin_only = require_roles(ROLE_ADMIN)
hr_admin = require_roles(ROLE_ADMIN, ROLE_HR)
staff = require_roles(ROLE_ADMIN, ROLE_HR, ROLE_MANAGER)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ---------- login throttling (in-memory; use Redis in multi-node deployments) ----------
_attempts: dict[str, deque] = defaultdict(deque)
WINDOW, MAX_ATTEMPTS = 900, 8


def throttle_check(key: str):
    now = time.time()
    q = _attempts[key]
    while q and now - q[0] > WINDOW:
        q.popleft()
    if len(q) >= MAX_ATTEMPTS:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed login attempts. Try again later.")


def throttle_fail(key: str):
    _attempts[key].append(time.time())


def throttle_clear(key: str):
    _attempts.pop(key, None)


def reset_throttle():
    _attempts.clear()
