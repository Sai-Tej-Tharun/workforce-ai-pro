"""Module 20: Audit logs & activity tracking (user activity, system audit, change history)."""
from datetime import date, datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog, User
from ..security import hr_admin, get_current_user

router = APIRouter(prefix="/audit", tags=["Audit Logs"])


def _row(a: AuditLog) -> dict:
    return {"id": a.id, "user_id": a.user_id, "user_email": a.user_email, "action": a.action, "entity": a.entity,
            "entity_id": a.entity_id, "changes": a.changes, "ip_address": a.ip_address, "created_at": a.created_at}


@router.get("")
def list_logs(user_id: Optional[int] = None, action: Optional[str] = None, entity: Optional[str] = None,
              search: Optional[str] = None, date_from: Optional[date] = None, date_to: Optional[date] = None,
              page: int = Query(1, ge=1), size: int = Query(25, ge=1, le=200), db: Session = Depends(get_db), _: User = Depends(hr_admin)):
    q = select(AuditLog)
    if user_id: q = q.where(AuditLog.user_id == user_id)
    if action: q = q.where(AuditLog.action == action.upper())
    if entity: q = q.where(AuditLog.entity == entity)
    if search: q = q.where(AuditLog.user_email.like(f"%{search}%") | AuditLog.entity_id.like(f"%{search}%"))
    if date_from: q = q.where(AuditLog.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to: q = q.where(AuditLog.created_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(AuditLog.id.desc()).offset((page - 1) * size).limit(size)).all()
    return {"items": [_row(a) for a in rows], "total": total, "page": page, "size": size}


@router.get("/history/{entity}/{entity_id}")
def change_history(entity: str, entity_id: str, db: Session = Depends(get_db), _: User = Depends(hr_admin)):
    """Change monitoring: every recorded change for one record."""
    rows = db.scalars(select(AuditLog).where(AuditLog.entity == entity, AuditLog.entity_id == entity_id).order_by(AuditLog.id.desc()).limit(200)).all()
    return [_row(a) for a in rows]


@router.get("/summary")
def summary(days: int = Query(7, ge=1, le=90), db: Session = Depends(get_db), _: User = Depends(hr_admin)):
    since = datetime.utcnow() - timedelta(days=days)
    by_action = db.execute(select(AuditLog.action, func.count()).where(AuditLog.created_at >= since).group_by(AuditLog.action).order_by(func.count().desc())).all()
    by_user = db.execute(select(AuditLog.user_email, func.count()).where(AuditLog.created_at >= since, AuditLog.user_email.is_not(None)).group_by(AuditLog.user_email).order_by(func.count().desc()).limit(10)).all()
    failed = db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "LOGIN_FAILED", AuditLog.created_at >= since))
    return {"days": days, "by_action": [{"action": a, "count": n} for a, n in by_action],
            "top_users": [{"user": u, "count": n} for u, n in by_user], "failed_logins": failed}


@router.get("/my-activity")
def my_activity(limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.id.desc()).limit(limit)).all()
    return [_row(a) for a in rows]
