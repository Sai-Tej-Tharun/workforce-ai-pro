"""Module 1: Authentication (register, login/JWT, refresh, forgot/reset password, session validation) + user admin."""
import secrets, time
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import User, Employee, PasswordResetToken, ROLE_EMPLOYEE
from ..schemas import (RegisterIn, TokenOut, RefreshIn, ForgotIn, ResetIn, ChangePasswordIn, UserOut,
                       UserCreateIn, UserUpdateIn)
from ..security import (hash_password, verify_password, validate_password_strength, create_access_token,
                        create_refresh_token, decode_token, get_current_user, admin_only, hash_token,
                        throttle_check, throttle_fail, throttle_clear, client_ip, hr_admin, oauth2_scheme)
from ..services.common import audit

router = APIRouter(tags=["Auth"])


def _token_response(user: User) -> TokenOut:
    access, exp = create_access_token(user)
    refresh, _ = create_refresh_token(user)
    return TokenOut(access_token=access, refresh_token=refresh, expires_at=exp, user=UserOut.model_validate(user))


@router.post("/auth/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    """Public self-registration. Always creates an EMPLOYEE account (roles can only be elevated by an ADMIN)."""
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    err = validate_password_strength(body.password)
    if err:
        raise HTTPException(422, err)
    emp = db.scalar(select(Employee).where(Employee.email == email))
    linked = emp.id if emp and not db.scalar(select(User.id).where(User.employee_id == emp.id)) else None
    user = User(email=email, full_name=body.full_name.strip(), hashed_password=hash_password(body.password),
                role=ROLE_EMPLOYEE, employee_id=linked)
    db.add(user)
    db.commit()
    audit(db, user, "REGISTER", "user", user.id, request=request)
    return user


@router.post("/auth/login", response_model=TokenOut)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = form.username.lower().strip()
    key = f"{email}|{client_ip(request)}"
    throttle_check(key)
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(form.password, user.hashed_password):
        throttle_fail(key)
        audit(db, None, "LOGIN_FAILED", "user", email, request=request)
        raise HTTPException(401, "Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    if not user.is_active:
        raise HTTPException(403, "Account disabled")
    throttle_clear(key)
    user.last_login = datetime.utcnow()
    db.commit()
    audit(db, user, "LOGIN", "user", user.id, request=request)
    return _token_response(user)


@router.post("/auth/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token, expected="refresh")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(401, "User inactive or not found")
    return _token_response(user)


@router.get("/auth/session")
def session(user: User = Depends(get_current_user), token: str = Depends(oauth2_scheme)):
    """Session validation: confirms the token is valid and reports remaining lifetime."""
    payload = decode_token(token)
    remaining = int(payload["exp"] - time.time())
    return {"valid": True, "user": UserOut.model_validate(user), "expires_in_seconds": max(remaining, 0)}


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/auth/forgot-password")
def forgot_password(body: ForgotIn, request: Request, db: Session = Depends(get_db)):
    """Always returns 200 (no account enumeration). In dev, the token is echoed back instead of emailed."""
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    resp = {"message": "If the account exists, a reset link has been sent."}
    if user and user.is_active:
        token = secrets.token_urlsafe(32)
        db.add(PasswordResetToken(user_id=user.id, token_hash=hash_token(token),
                                  expires_at=datetime.utcnow() + timedelta(minutes=settings.RESET_TOKEN_MINUTES)))
        db.commit()
        audit(db, user, "PASSWORD_RESET_REQUEST", "user", user.id, request=request)
        if settings.EXPOSE_RESET_TOKEN:
            resp["dev_reset_token"] = token
    return resp


@router.post("/auth/reset-password")
def reset_password(body: ResetIn, request: Request, db: Session = Depends(get_db)):
    rec = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(body.token)))
    if not rec or rec.used or rec.expires_at < datetime.utcnow():
        raise HTTPException(400, "Reset token is invalid or expired")
    err = validate_password_strength(body.new_password)
    if err:
        raise HTTPException(422, err)
    user = db.get(User, rec.user_id)
    user.hashed_password = hash_password(body.new_password)
    rec.used = True
    db.commit()
    audit(db, user, "PASSWORD_RESET", "user", user.id, request=request)
    return {"message": "Password updated"}


@router.post("/auth/change-password")
def change_password(body: ChangePasswordIn, request: Request, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(400, "Current password is incorrect")
    err = validate_password_strength(body.new_password)
    if err:
        raise HTTPException(422, err)
    user.hashed_password = hash_password(body.new_password)
    db.commit()
    audit(db, user, "PASSWORD_CHANGE", "user", user.id, request=request)
    return {"message": "Password changed"}


# ------------------- user administration (ADMIN) -------------------
@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(hr_admin)):
    return db.scalars(select(User).order_by(User.id)).all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreateIn, request: Request, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    if db.scalar(select(User.id).where(User.email == body.email.lower())):
        raise HTTPException(409, "Email already registered")
    err = validate_password_strength(body.password)
    if err:
        raise HTTPException(422, err)
    user = User(email=body.email.lower(), full_name=body.full_name, hashed_password=hash_password(body.password),
                role=body.role, employee_id=body.employee_id)
    db.add(user)
    db.commit()
    audit(db, admin, "CREATE", "user", user.id, {"role": body.role}, request)
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdateIn, request: Request, db: Session = Depends(get_db),
                admin: User = Depends(admin_only)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    data = body.model_dump(exclude_unset=True)
    if user.id == admin.id and (data.get("is_active") is False or data.get("role", "ADMIN") != "ADMIN"):
        raise HTTPException(400, "You cannot demote or deactivate yourself")
    changes = {k: [str(getattr(user, k)), str(v)] for k, v in data.items() if getattr(user, k) != v}
    for k, v in data.items():
        setattr(user, k, v)
    db.commit()
    audit(db, admin, "UPDATE", "user", user.id, changes, request)
    return user
