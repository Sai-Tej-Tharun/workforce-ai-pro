"""Shared helpers: audit logging, notifications, RBAC scoping, tiny TTL cache."""
import time
from functools import wraps
from typing import Optional, Any
from fastapi import HTTPException, Request
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session

from ..models import (AuditLog, Notification, User, Employee, Prediction, ROLE_ADMIN, ROLE_HR,
                      ROLE_MANAGER, ROLE_EMPLOYEE, ActivityEvent)
from ..ws import manager


# ---------------- audit (Module 20) ----------------
def audit(db: Session, user: Optional[User], action: str, entity: str, entity_id: Any = None,
          changes: Optional[dict] = None, request: Optional[Request] = None, commit: bool = True):
    db.add(AuditLog(user_id=user.id if user else None, user_email=user.email if user else None,
                    action=action, entity=entity, entity_id=str(entity_id) if entity_id is not None else None,
                    changes=changes, ip_address=request.client.host if request and request.client else None))
    if commit:
        db.commit()


def diff(obj, data: dict) -> dict:
    """{field: [old, new]} for fields that actually change."""
    out = {}
    for k, v in data.items():
        old = getattr(obj, k, None)
        if old != v:
            out[k] = [str(old) if old is not None else None, str(v) if v is not None else None]
    return out


# ---------------- notifications (Module 7 / 17) ----------------
def notify(db: Session, user_ids: list[int], title: str, message: str, category: str = "system",
           priority: str = "low", link: Optional[str] = None, commit: bool = False):
    rows = []
    for uid in set(user_ids):
        n = Notification(user_id=uid, title=title, message=message, category=category, priority=priority, link=link)
        db.add(n)
        rows.append(n)
    db.flush()
    for n in rows:
        manager.publish_user(n.user_id, {"type": "notification", "data": {
            "id": n.id, "title": n.title, "message": n.message, "category": n.category,
            "priority": n.priority, "link": n.link, "created_at": n.created_at.isoformat() + "Z"}})
    if commit:
        db.commit()


def user_ids_by_role(db: Session, *roles: str) -> list[int]:
    return list(db.scalars(select(User.id).where(User.role.in_(roles), User.is_active == True)))  # noqa: E712


def emit_activity(db: Session, employee_id: Optional[int], event_type: str, description: str,
                  severity: str = "info", payload: Optional[dict] = None):
    ev = ActivityEvent(employee_id=employee_id, event_type=event_type, description=description,
                       severity=severity, payload=payload)
    db.add(ev)
    db.flush()
    name = None
    if employee_id:
        e = db.get(Employee, employee_id)
        name = e.full_name if e else None
    manager.publish_roles((ROLE_ADMIN, ROLE_HR, ROLE_MANAGER), {"type": "activity", "data": {
        "id": ev.id, "employee_id": employee_id, "employee_name": name, "event_type": event_type,
        "description": description, "severity": severity, "created_at": ev.created_at.isoformat() + "Z"}})
    return ev


# ---------------- RBAC scoping (Module 26) ----------------
def employee_scope_filter(user: User):
    """SQLAlchemy condition limiting which employees a user may see; None = unrestricted."""
    if user.role in (ROLE_ADMIN, ROLE_HR):
        return None
    if user.employee_id is None:
        return Employee.id == -1
    if user.role == ROLE_MANAGER:
        return or_(Employee.manager_id == user.employee_id, Employee.id == user.employee_id)
    return Employee.id == user.employee_id


def ensure_employee_access(db: Session, user: User, employee_id: int):
    cond = employee_scope_filter(user)
    if cond is None:
        return
    ok = db.scalar(select(func.count()).select_from(Employee).where(Employee.id == employee_id, cond))
    if not ok:
        raise HTTPException(403, "You do not have access to this employee")


def team_employee_ids(db: Session, user: User) -> Optional[list[int]]:
    cond = employee_scope_filter(user)
    if cond is None:
        return None
    return list(db.scalars(select(Employee.id).where(cond)))


# ---------------- latest predictions ----------------
def latest_predictions(db: Session, employee_ids: Optional[list[int]] = None) -> dict[int, Prediction]:
    sub = select(func.max(Prediction.id).label("pid")).group_by(Prediction.employee_id)
    if employee_ids is not None:
        if not employee_ids:
            return {}
        sub = sub.where(Prediction.employee_id.in_(employee_ids))
    rows = db.scalars(select(Prediction).where(Prediction.id.in_(sub.scalar_subquery())))
    return {p.employee_id: p for p in rows}


# ---------------- tiny TTL cache (swap for Redis when horizontally scaling) ----------------
_cache: dict = {}


def ttl_cache(seconds: int = 20):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, cache_key: str = "", **kwargs):
            key = (fn.__name__, cache_key)
            hit = _cache.get(key)
            if hit and time.time() - hit[0] < seconds:
                return hit[1]
            val = fn(*args, **kwargs)
            _cache[key] = (time.time(), val)
            return val
        return wrapper
    return deco


def clear_cache():
    _cache.clear()
