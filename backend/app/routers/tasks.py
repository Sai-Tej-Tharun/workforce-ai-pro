"""Module 21: Workflow & task management (assign, track, status, due-date monitoring)."""
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Task, User, ROLE_ADMIN, ROLE_HR, ROLE_MANAGER
from ..schemas import TaskIn, TaskUpdate
from ..security import get_current_user, staff
from ..services.common import audit, notify

router = APIRouter(prefix="/tasks", tags=["Tasks & Workflow"])


def _out(t: Task) -> dict:
    return {"id": t.id, "title": t.title, "description": t.description, "assigned_to": t.assigned_to,
            "assignee_name": t.assignee.full_name if t.assignee else None, "created_by": t.created_by,
            "employee_id": t.employee_id, "employee_name": t.employee.full_name if t.employee else None,
            "priority": t.priority, "status": t.status, "due_date": t.due_date, "created_at": t.created_at,
            "completed_at": t.completed_at, "overdue": bool(t.due_date and t.due_date < date.today() and t.status in ("todo", "in_progress")),
            "due_soon": bool(t.due_date and 0 <= (t.due_date - date.today()).days <= 2 and t.status in ("todo", "in_progress"))}


@router.get("")
def list_tasks(status: Optional[str] = None, mine: bool = False, overdue: Optional[bool] = None, page: int = Query(1, ge=1),
               size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = select(Task)
    if user.role not in (ROLE_ADMIN, ROLE_HR) or mine:
        q = q.where(or_(Task.assigned_to == user.id, Task.created_by == user.id)) if not mine else q.where(Task.assigned_to == user.id)
    if status: q = q.where(Task.status == status)
    if overdue: q = q.where(Task.due_date < date.today(), Task.status.in_(["todo", "in_progress"]))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(Task.due_date.is_(None), Task.due_date, Task.id.desc()).offset((page - 1) * size).limit(size)).unique().all()
    return {"items": [_out(t) for t in rows], "total": total, "page": page, "size": size}


@router.get("/stats")
def stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = select(Task.status, func.count()).group_by(Task.status)
    if user.role not in (ROLE_ADMIN, ROLE_HR):
        q = q.where(or_(Task.assigned_to == user.id, Task.created_by == user.id))
    by = dict(db.execute(q).all())
    oq = select(func.count()).select_from(Task).where(Task.due_date < date.today(), Task.status.in_(["todo", "in_progress"]))
    if user.role not in (ROLE_ADMIN, ROLE_HR):
        oq = oq.where(or_(Task.assigned_to == user.id, Task.created_by == user.id))
    return {"todo": by.get("todo", 0), "in_progress": by.get("in_progress", 0), "done": by.get("done", 0),
            "cancelled": by.get("cancelled", 0), "overdue": db.scalar(oq)}


@router.post("", status_code=201)
def create(body: TaskIn, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    t = Task(**body.model_dump(), created_by=user.id)
    if body.due_date and body.due_date < date.today():
        raise HTTPException(422, "due_date cannot be in the past")
    db.add(t)
    db.flush()
    if t.assigned_to and t.assigned_to != user.id:
        notify(db, [t.assigned_to], "New task assigned", f"{t.title}" + (f" (due {t.due_date})" if t.due_date else ""), "task", t.priority, "/tasks")
    db.commit()
    audit(db, user, "CREATE", "task", t.id, {"title": t.title}, request)
    return _out(t)


@router.patch("/{tid}")
def update(tid: int, body: TaskUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.get(Task, tid)
    if not t:
        raise HTTPException(404, "Task not found")
    is_owner = t.assigned_to == user.id or t.created_by == user.id
    if not is_owner and user.role not in (ROLE_ADMIN, ROLE_HR):
        raise HTTPException(403, "Not allowed")
    data = body.model_dump(exclude_unset=True)
    if user.role not in (ROLE_ADMIN, ROLE_HR, ROLE_MANAGER) and set(data) - {"status"}:
        raise HTTPException(403, "Employees may only update task status")
    changes = {k: [str(getattr(t, k)), str(v)] for k, v in data.items() if getattr(t, k) != v}
    for k, v in data.items():
        setattr(t, k, v)
    if data.get("status") == "done":
        t.completed_at = datetime.utcnow()
        if t.created_by and t.created_by != user.id:
            notify(db, [t.created_by], "Task completed", t.title, "task", "low", "/tasks")
    db.commit()
    audit(db, user, "UPDATE", "task", tid, changes, request)
    return _out(t)


@router.delete("/{tid}", status_code=204)
def delete(tid: int, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    t = db.get(Task, tid)
    if not t:
        raise HTTPException(404, "Task not found")
    if t.created_by != user.id and user.role not in (ROLE_ADMIN, ROLE_HR):
        raise HTTPException(403, "Only the creator or HR can delete")
    db.delete(t)
    db.commit()
    audit(db, user, "DELETE", "task", tid, request=request)
