"""Module 16: HR intervention & decision-support (AI recommendations, follow-ups, logs)."""
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Intervention, InterventionLog, Employee, User, Prediction, ROLE_ADMIN, ROLE_HR
from ..schemas import InterventionIn, InterventionUpdate
from ..security import staff, hr_admin
from ..services import recommend
from ..services.common import audit, notify, employee_scope_filter, ensure_employee_access, latest_predictions

router = APIRouter(prefix="/interventions", tags=["HR Interventions"])


def _out(i: Intervention, with_logs=False) -> dict:
    d = {"id": i.id, "employee_id": i.employee_id, "employee_name": i.employee.full_name if i.employee else None,
         "department": i.employee.department.name if i.employee and i.employee.department else None,
         "title": i.title, "recommendation": i.recommendation, "priority": i.priority, "status": i.status,
         "outcome": i.outcome, "assigned_to": i.assigned_to, "follow_up_date": i.follow_up_date,
         "auto_generated": i.auto_generated, "created_at": i.created_at, "closed_at": i.closed_at,
         "overdue": bool(i.follow_up_date and i.follow_up_date < date.today() and i.status in ("open", "in_progress"))}
    if with_logs:
        d["logs"] = [{"id": l.id, "action": l.action, "note": l.note, "user_id": l.user_id, "created_at": l.created_at} for l in i.logs]
    return d


@router.get("")
def list_interventions(status: Optional[str] = None, employee_id: Optional[int] = None, assigned_to: Optional[int] = None,
                       overdue: Optional[bool] = None, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                       db: Session = Depends(get_db), user: User = Depends(staff)):
    q = select(Intervention).join(Employee, Employee.id == Intervention.employee_id)
    scope = employee_scope_filter(user)
    if scope is not None: q = q.where(scope)
    if status: q = q.where(Intervention.status == status)
    if employee_id: q = q.where(Intervention.employee_id == employee_id)
    if assigned_to: q = q.where(Intervention.assigned_to == assigned_to)
    if overdue:
        q = q.where(Intervention.follow_up_date < date.today(), Intervention.status.in_(["open", "in_progress"]))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(Intervention.id.desc()).offset((page - 1) * size).limit(size)).unique().all()
    return {"items": [_out(i) for i in rows], "total": total, "page": page, "size": size}


@router.get("/stats")
def stats(db: Session = Depends(get_db), _: User = Depends(staff)):
    by = dict(db.execute(select(Intervention.status, func.count()).group_by(Intervention.status)).all())
    out = dict(db.execute(select(Intervention.outcome, func.count()).where(Intervention.outcome.is_not(None)).group_by(Intervention.outcome)).all())
    overdue = db.scalar(select(func.count()).select_from(Intervention).where(
        Intervention.follow_up_date < date.today(), Intervention.status.in_(["open", "in_progress"])))
    retained, left = out.get("retained", 0), out.get("left", 0)
    return {"open": by.get("open", 0), "in_progress": by.get("in_progress", 0), "completed": by.get("completed", 0),
            "dismissed": by.get("dismissed", 0), "overdue": overdue, "retained": retained, "left": left,
            "retention_success_rate": round(retained / (retained + left) * 100, 1) if (retained + left) else None}


@router.get("/suggest/{emp_id}")
def suggest(emp_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    """AI-based recommendations / retention suggestions for an employee from their latest risk drivers."""
    ensure_employee_access(db, user, emp_id)
    p = latest_predictions(db, [emp_id]).get(emp_id)
    if not p:
        raise HTTPException(404, "No prediction yet for this employee")
    return {"employee_id": emp_id, "risk_score": p.risk_score, "risk_level": p.risk_level,
            "actions": recommend.actions_from_factors(p.top_factors or [], limit=5)}


@router.get("/{iid}")
def get_one(iid: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    i = db.get(Intervention, iid)
    if not i:
        raise HTTPException(404, "Intervention not found")
    ensure_employee_access(db, user, i.employee_id)
    return _out(i, True)


@router.post("", status_code=201)
def create(body: InterventionIn, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    ensure_employee_access(db, user, body.employee_id)
    p = latest_predictions(db, [body.employee_id]).get(body.employee_id)
    i = Intervention(employee_id=body.employee_id, prediction_id=p.id if p else None, title=body.title,
                     recommendation=body.recommendation, priority=body.priority, assigned_to=body.assigned_to or user.id,
                     follow_up_date=body.follow_up_date)
    db.add(i)
    db.flush()
    db.add(InterventionLog(intervention_id=i.id, action="created", note=f"Created manually by {user.full_name}", user_id=user.id))
    if i.assigned_to and i.assigned_to != user.id:
        notify(db, [i.assigned_to], "Intervention assigned", i.title, "task", i.priority, "/interventions")
    db.commit()
    audit(db, user, "CREATE", "intervention", i.id, {"employee_id": body.employee_id}, request)
    return _out(i, True)


@router.patch("/{iid}")
def update(iid: int, body: InterventionUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    i = db.get(Intervention, iid)
    if not i:
        raise HTTPException(404, "Intervention not found")
    ensure_employee_access(db, user, i.employee_id)
    data = body.model_dump(exclude_unset=True)
    note = data.pop("note", None)
    changes = []
    for k, v in data.items():
        if getattr(i, k) != v:
            changes.append(f"{k}: {getattr(i, k)} -> {v}")
            setattr(i, k, v)
    if "status" in data and data["status"] in ("completed", "dismissed"):
        i.closed_at = datetime.utcnow()
    if changes or note:
        db.add(InterventionLog(intervention_id=i.id, action="updated", note="; ".join(changes + ([note] if note else []))[:500], user_id=user.id))
    if "assigned_to" in data and data["assigned_to"]:
        notify(db, [data["assigned_to"]], "Intervention assigned", i.title, "task", i.priority, "/interventions")
    db.commit()
    audit(db, user, "UPDATE", "intervention", iid, {"changes": changes}, request)
    return _out(i, True)
