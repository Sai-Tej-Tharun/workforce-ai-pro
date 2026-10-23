"""Module 5: Leave management (policies, apply, approval workflow, balances, reports)."""
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy import select, func, extract
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import LeavePolicy, LeaveRequest, Employee, User, ROLE_ADMIN, ROLE_HR, ROLE_MANAGER
from ..schemas import LeavePolicyIn, LeavePolicyOut, LeaveApplyIn, LeaveReviewIn, LeaveOut
from ..security import get_current_user, hr_admin, staff
from ..services import risk
from ..services.common import (audit, notify, user_ids_by_role, employee_scope_filter, ensure_employee_access, emit_activity)

router = APIRouter(prefix="/leave", tags=["Leave"])


def working_days(start: date, end: date) -> int:
    return sum(1 for i in range((end - start).days + 1) if (start + timedelta(days=i)).weekday() < 5)


def _out(r: LeaveRequest) -> dict:
    d = LeaveOut.model_validate(r).model_dump(mode="json")
    d["employee_name"] = r.employee.full_name if r.employee else None
    return d


def balance_for(db: Session, emp_id: int, year: int) -> list[dict]:
    policies = db.scalars(select(LeavePolicy)).all()
    used = dict(db.execute(select(LeaveRequest.leave_type, func.sum(LeaveRequest.days)).where(
        LeaveRequest.employee_id == emp_id, LeaveRequest.status == "approved",
        extract("year", LeaveRequest.start_date) == year).group_by(LeaveRequest.leave_type)).all())
    pending = dict(db.execute(select(LeaveRequest.leave_type, func.sum(LeaveRequest.days)).where(
        LeaveRequest.employee_id == emp_id, LeaveRequest.status == "pending",
        extract("year", LeaveRequest.start_date) == year).group_by(LeaveRequest.leave_type)).all())
    return [{"leave_type": p.leave_type, "quota": p.annual_quota, "used": int(used.get(p.leave_type, 0)),
             "pending": int(pending.get(p.leave_type, 0)),
             "remaining": p.annual_quota - int(used.get(p.leave_type, 0)) - int(pending.get(p.leave_type, 0))} for p in policies]


# -------- policies --------
@router.get("/policies", response_model=list[LeavePolicyOut])
def policies(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(LeavePolicy).order_by(LeavePolicy.leave_type)).all()


@router.post("/policies", response_model=LeavePolicyOut, status_code=201)
def create_policy(body: LeavePolicyIn, request: Request, db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    if db.scalar(select(LeavePolicy.id).where(LeavePolicy.leave_type == body.leave_type)):
        raise HTTPException(409, "Policy for this leave type already exists")
    p = LeavePolicy(**body.model_dump())
    db.add(p)
    db.commit()
    audit(db, user, "CREATE", "leave_policy", p.id, body.model_dump(), request)
    return p


@router.put("/policies/{pid}", response_model=LeavePolicyOut)
def update_policy(pid: int, body: LeavePolicyIn, request: Request, db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    p = db.get(LeavePolicy, pid)
    if not p:
        raise HTTPException(404, "Policy not found")
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    db.commit()
    audit(db, user, "UPDATE", "leave_policy", pid, body.model_dump(), request)
    return p


# -------- balance / list / apply / review --------
@router.get("/balance")
def balance(employee_id: Optional[int] = None, year: int = Query(default_factory=lambda: date.today().year),
            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    eid = employee_id or user.employee_id
    if not eid:
        raise HTTPException(400, "No employee profile linked")
    ensure_employee_access(db, user, eid)
    return balance_for(db, eid, year)


@router.get("")
def list_leave(status: Optional[str] = None, employee_id: Optional[int] = None, page: int = Query(1, ge=1),
               size: int = Query(20, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = select(LeaveRequest).join(Employee, Employee.id == LeaveRequest.employee_id)
    scope = employee_scope_filter(user)
    if scope is not None: q = q.where(scope)
    if status: q = q.where(LeaveRequest.status == status)
    if employee_id: q = q.where(LeaveRequest.employee_id == employee_id)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(LeaveRequest.id.desc()).offset((page - 1) * size).limit(size)).unique().all()
    return {"items": [_out(r) for r in rows], "total": total, "page": page, "size": size}


@router.post("", status_code=201)
def apply_leave(body: LeaveApplyIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    eid = body.employee_id if (body.employee_id and user.role in (ROLE_ADMIN, ROLE_HR)) else user.employee_id
    if not eid:
        raise HTTPException(400, "No employee profile linked to this account")
    emp = db.get(Employee, eid)
    if body.end_date < body.start_date:
        raise HTTPException(422, "end_date must be on or after start_date")
    policy = db.scalar(select(LeavePolicy).where(LeavePolicy.leave_type == body.leave_type))
    if not policy:
        raise HTTPException(422, f"Unknown leave type '{body.leave_type}'")
    days = working_days(body.start_date, body.end_date)
    if days == 0:
        raise HTTPException(422, "Selected range contains no working days")
    overlap = db.scalar(select(LeaveRequest.id).where(
        LeaveRequest.employee_id == eid, LeaveRequest.status.in_(["pending", "approved"]),
        LeaveRequest.start_date <= body.end_date, LeaveRequest.end_date >= body.start_date))
    if overlap:
        raise HTTPException(409, "Overlaps with an existing leave request")
    bal = next((b for b in balance_for(db, eid, body.start_date.year) if b["leave_type"] == body.leave_type), None)
    if bal and body.leave_type != "Unpaid" and days > bal["remaining"]:
        raise HTTPException(422, f"Insufficient {body.leave_type} balance: {bal['remaining']} day(s) remaining, {days} requested")
    r = LeaveRequest(employee_id=eid, leave_type=body.leave_type, start_date=body.start_date, end_date=body.end_date,
                     days=days, reason=body.reason)
    db.add(r)
    db.flush()
    targets = set(user_ids_by_role(db, ROLE_HR))
    if emp.manager_id:
        mu = db.scalar(select(User.id).where(User.employee_id == emp.manager_id))
        if mu: targets.add(mu)
    notify(db, list(targets), "Leave request pending", f"{emp.full_name} requested {days} day(s) of {body.leave_type} leave",
           "leave", "medium", "/leave")
    emit_activity(db, eid, "leave_applied", f"{emp.full_name} applied for {days} day(s) {body.leave_type} leave")
    db.commit()
    audit(db, user, "CREATE", "leave_request", r.id, {"days": days, "type": body.leave_type}, request)
    return _out(r)


@router.patch("/{leave_id}/review")
def review_leave(leave_id: int, body: LeaveReviewIn, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    r = db.get(LeaveRequest, leave_id)
    if not r:
        raise HTTPException(404, "Leave request not found")
    if r.status != "pending":
        raise HTTPException(409, f"Request already {r.status}")
    ensure_employee_access(db, user, r.employee_id)
    if r.employee_id == user.employee_id:
        raise HTTPException(403, "You cannot review your own leave request")
    r.status = "approved" if body.action == "approve" else "rejected"
    r.reviewed_by, r.review_comment = user.id, body.comment
    emp_user = db.scalar(select(User.id).where(User.employee_id == r.employee_id))
    if emp_user:
        notify(db, [emp_user], f"Leave {r.status}", f"Your {r.leave_type} leave ({r.start_date} – {r.end_date}) was {r.status}."
               + (f" Comment: {body.comment}" if body.comment else ""), "leave", "medium", "/leave")
    db.commit()
    audit(db, user, body.action.upper(), "leave_request", leave_id, {"status": r.status}, request)
    if r.status == "approved":
        risk.recalc_one(db, r.employee, "leave_approved")
    return _out(r)


@router.post("/{leave_id}/cancel")
def cancel_leave(leave_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = db.get(LeaveRequest, leave_id)
    if not r or (r.employee_id != user.employee_id and user.role not in (ROLE_ADMIN, ROLE_HR)):
        raise HTTPException(404, "Leave request not found")
    if r.status != "pending":
        raise HTTPException(409, "Only pending requests can be cancelled")
    r.status = "cancelled"
    db.commit()
    audit(db, user, "CANCEL", "leave_request", leave_id, request=request)
    return _out(r)


def leave_report_rows(db: Session, year: int):
    rows = db.execute(select(Employee.employee_code, Employee.first_name, Employee.last_name, LeaveRequest.leave_type,
                             func.sum(LeaveRequest.days), func.count(LeaveRequest.id))
                      .join(Employee, Employee.id == LeaveRequest.employee_id)
                      .where(LeaveRequest.status == "approved", extract("year", LeaveRequest.start_date) == year)
                      .group_by(Employee.employee_code, Employee.first_name, Employee.last_name, LeaveRequest.leave_type)).all()
    return [{"employee_code": c, "employee_name": f"{f} {l}", "leave_type": t, "days": int(d), "requests": n} for c, f, l, t, d, n in rows]


@router.get("/report")
def leave_report(year: int = Query(default_factory=lambda: date.today().year), db: Session = Depends(get_db), _: User = Depends(hr_admin)):
    rows = leave_report_rows(db, year)
    by_type: dict = {}
    for r in rows:
        by_type[r["leave_type"]] = by_type.get(r["leave_type"], 0) + r["days"]
    return {"year": year, "by_type": [{"leave_type": k, "days": v} for k, v in by_type.items()], "rows": rows}
