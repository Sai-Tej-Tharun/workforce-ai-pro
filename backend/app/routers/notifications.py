"""Module 7: In-app notifications, read/unread, alert history (+ Module 17 alert queue)."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Notification, Alert, User
from ..schemas import NotificationOut, NotificationIn
from ..security import get_current_user, hr_admin, staff
from ..services.common import notify, audit

router = APIRouter(tags=["Notifications & Alerts"])
PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


@router.get("/notifications")
def list_notifications(unread_only: bool = False, category: Optional[str] = None, page: int = Query(1, ge=1),
                       size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = select(Notification).where(Notification.user_id == user.id)
    if unread_only: q = q.where(Notification.is_read == False)  # noqa: E712
    if category: q = q.where(Notification.category == category)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(Notification.id.desc()).offset((page - 1) * size).limit(size)).all()
    return {"items": [NotificationOut.model_validate(r) for r in rows], "total": total, "page": page, "size": size}


@router.get("/notifications/unread-count")
def unread_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.is_read == False))  # noqa: E712
    return {"unread": n}


@router.patch("/notifications/{nid}/read", response_model=NotificationOut)
def mark_read(nid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.get(Notification, nid)
    if not n or n.user_id != user.id:
        raise HTTPException(404, "Notification not found")
    n.is_read = True
    db.commit()
    return n


@router.post("/notifications/read-all")
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    res = db.execute(update(Notification).where(Notification.user_id == user.id, Notification.is_read == False).values(is_read=True))  # noqa: E712
    db.commit()
    return {"updated": res.rowcount}


@router.delete("/notifications/{nid}", status_code=204)
def delete_notification(nid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.get(Notification, nid)
    if not n or n.user_id != user.id:
        raise HTTPException(404, "Notification not found")
    db.delete(n)
    db.commit()


@router.post("/notifications/send", status_code=201)
def send_notification(body: NotificationIn, request: Request, db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    """Automated workforce notification: to one user or broadcast to all active users."""
    ids = [body.user_id] if body.user_id else list(db.scalars(select(User.id).where(User.is_active == True)))  # noqa: E712
    notify(db, ids, body.title, body.message, "system", body.priority, commit=True)
    audit(db, user, "BROADCAST" if not body.user_id else "NOTIFY", "notification", None, {"recipients": len(ids)}, request)
    return {"sent": len(ids)}


# ---------------- AI alert queue (Module 17) ----------------
@router.get("/alerts")
def list_alerts(status: Optional[str] = None, severity: Optional[str] = None, alert_type: Optional[str] = None,
                page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                db: Session = Depends(get_db), user: User = Depends(staff)):
    q = select(Alert)
    if status: q = q.where(Alert.status == status)
    if severity: q = q.where(Alert.severity == severity)
    if alert_type: q = q.where(Alert.alert_type == alert_type)
    if user.role == "MANAGER":
        from ..services.common import employee_scope_filter
        from ..models import Employee
        q = q.where(Alert.employee_id.in_(select(Employee.id).where(employee_scope_filter(user))))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(Alert.id.desc()).offset((page - 1) * size).limit(size)).unique().all()
    rows = sorted(rows, key=lambda a: (a.status == "resolved", PRIORITY_ORDER.get(a.severity, 9)))  # priority system
    items = [{"id": a.id, "employee_id": a.employee_id, "employee_name": a.employee.full_name if a.employee else None,
              "alert_type": a.alert_type, "severity": a.severity, "message": a.message, "status": a.status,
              "created_at": a.created_at, "resolved_at": a.resolved_at} for a in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.patch("/alerts/{aid}")
def update_alert(aid: int, body: dict, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    from datetime import datetime
    a = db.get(Alert, aid)
    if not a:
        raise HTTPException(404, "Alert not found")
    status = body.get("status")
    if status not in ("open", "acknowledged", "resolved"):
        raise HTTPException(422, "status must be open|acknowledged|resolved")
    a.status = status
    a.resolved_at = datetime.utcnow() if status == "resolved" else None
    db.commit()
    audit(db, user, "UPDATE", "alert", aid, {"status": status}, request)
    return {"id": a.id, "status": a.status}
