"""Module 4: Attendance & shift management (check-in/out, hours, overtime, reports)."""
from datetime import date, datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy import select, func, case
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Attendance, Shift, Employee, User, ROLE_ADMIN, ROLE_HR
from ..schemas import ShiftIn, ShiftOut, ShiftAssignIn, CheckIn, AttendanceOut
from ..security import get_current_user, hr_admin, staff
from ..services import risk
from ..services.common import audit, employee_scope_filter, ensure_employee_access, emit_activity

router = APIRouter(tags=["Attendance & Shifts"])
GRACE_MIN = 10


def _target_employee(db: Session, user: User, employee_id: Optional[int]) -> Employee:
    eid = employee_id if (employee_id and user.role in (ROLE_ADMIN, ROLE_HR)) else user.employee_id
    if not eid:
        raise HTTPException(400, "No employee profile linked to this account")
    emp = db.get(Employee, eid)
    if not emp or emp.status == "terminated":
        raise HTTPException(404, "Active employee not found")
    return emp


# ---------------- shifts ----------------
@router.get("/shifts", response_model=list[ShiftOut])
def list_shifts(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(Shift).order_by(Shift.start_time)).all()


@router.post("/shifts", response_model=ShiftOut, status_code=201)
def create_shift(body: ShiftIn, request: Request, db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    if db.scalar(select(Shift.id).where(Shift.name == body.name)):
        raise HTTPException(409, "Shift name already exists")
    s = Shift(**body.model_dump())
    db.add(s)
    db.commit()
    audit(db, user, "CREATE", "shift", s.id, body.model_dump(mode="json"), request)
    return s


@router.post("/shifts/assign")
def assign_shift(body: ShiftAssignIn, request: Request, db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    emp, shift = db.get(Employee, body.employee_id), db.get(Shift, body.shift_id)
    if not emp or not shift:
        raise HTTPException(404, "Employee or shift not found")
    old = emp.shift_id
    emp.shift_id = shift.id
    db.commit()
    audit(db, user, "ASSIGN", "shift", emp.id, {"shift_id": [old, shift.id]}, request)
    return {"employee_id": emp.id, "shift": shift.name}


# ---------------- check-in / out ----------------
@router.post("/attendance/check-in", response_model=AttendanceOut)
def check_in(body: CheckIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    emp = _target_employee(db, user, body.employee_id)
    now = datetime.now()
    if db.scalar(select(Attendance.id).where(Attendance.employee_id == emp.id, Attendance.work_date == now.date())):
        raise HTTPException(409, "Already checked in today")
    status = "present"
    if emp.shift:
        start = datetime.combine(now.date(), emp.shift.start_time) + timedelta(minutes=GRACE_MIN)
        if now > start:
            status = "late"
    rec = Attendance(employee_id=emp.id, work_date=now.date(), check_in=now, status=status)
    db.add(rec)
    db.commit()
    emit_activity(db, emp.id, "check_in", f"{emp.full_name} checked in" + (" (late)" if status == "late" else ""),
                  "warning" if status == "late" else "info")
    db.commit()
    if status == "late":
        risk.recalc_one(db, emp, "attendance")
    return rec


@router.post("/attendance/check-out", response_model=AttendanceOut)
def check_out(body: CheckIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    emp = _target_employee(db, user, body.employee_id)
    now = datetime.now()
    rec = db.scalar(select(Attendance).where(Attendance.employee_id == emp.id, Attendance.work_date == now.date()))
    if not rec or not rec.check_in:
        raise HTTPException(409, "You have not checked in today")
    if rec.check_out:
        raise HTTPException(409, "Already checked out today")
    std = emp.shift.standard_hours if emp.shift else 8.0
    hours = round((now - rec.check_in).total_seconds() / 3600, 2)
    rec.check_out, rec.working_hours = now, hours
    rec.overtime_hours = round(max(0.0, hours - std), 2)
    if hours < std / 2:
        rec.status = "half_day"
    db.commit()
    sev = "warning" if rec.overtime_hours >= 2 else "info"
    emit_activity(db, emp.id, "check_out", f"{emp.full_name} checked out ({hours}h, overtime {rec.overtime_hours}h)", sev)
    db.commit()
    if rec.overtime_hours >= 1:
        risk.recalc_one(db, emp, "attendance")
    return rec


@router.post("/attendance/manual", response_model=AttendanceOut)
def manual_entry(body: dict, request: Request, db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    """HR correction / back-fill: {employee_id, work_date, check_in, check_out, status}."""
    try:
        emp_id, wd = int(body["employee_id"]), date.fromisoformat(body["work_date"])
        ci = datetime.fromisoformat(body["check_in"]) if body.get("check_in") else None
        co = datetime.fromisoformat(body["check_out"]) if body.get("check_out") else None
    except (KeyError, ValueError):
        raise HTTPException(422, "employee_id, work_date (YYYY-MM-DD) required; check_in/out ISO datetimes")
    emp = db.get(Employee, emp_id)
    if not emp:
        raise HTTPException(404, "Employee not found")
    rec = db.scalar(select(Attendance).where(Attendance.employee_id == emp_id, Attendance.work_date == wd)) or \
        Attendance(employee_id=emp_id, work_date=wd)
    rec.check_in, rec.check_out = ci, co
    std = emp.shift.standard_hours if emp.shift else 8.0
    rec.working_hours = round((co - ci).total_seconds() / 3600, 2) if ci and co else 0
    rec.overtime_hours = round(max(0, rec.working_hours - std), 2)
    rec.status = body.get("status") or ("present" if ci else "absent")
    db.add(rec)
    db.commit()
    audit(db, user, "MANUAL_ENTRY", "attendance", rec.id, {"employee_id": emp_id, "date": str(wd)}, request)
    return rec


@router.get("/attendance/today")
def today_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.employee_id:
        return {"linked": False}
    rec = db.scalar(select(Attendance).where(Attendance.employee_id == user.employee_id, Attendance.work_date == date.today()))
    return {"linked": True, "record": AttendanceOut.model_validate(rec) if rec else None}


@router.get("/attendance")
def list_attendance(employee_id: Optional[int] = None, date_from: Optional[date] = None, date_to: Optional[date] = None,
                    status: Optional[str] = None, page: int = Query(1, ge=1), size: int = Query(31, ge=1, le=200),
                    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = select(Attendance, Employee.first_name, Employee.last_name).join(Employee, Employee.id == Attendance.employee_id)
    scope = employee_scope_filter(user)
    if scope is not None:
        q = q.where(scope)
    if employee_id:
        ensure_employee_access(db, user, employee_id)
        q = q.where(Attendance.employee_id == employee_id)
    if date_from: q = q.where(Attendance.work_date >= date_from)
    if date_to: q = q.where(Attendance.work_date <= date_to)
    if status: q = q.where(Attendance.status == status)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.execute(q.order_by(Attendance.work_date.desc(), Attendance.id.desc()).offset((page - 1) * size).limit(size)).all()
    items = [{**AttendanceOut.model_validate(a).model_dump(mode="json"), "employee_name": f"{f} {l}"} for a, f, l in rows]
    return {"items": items, "total": total, "page": page, "size": size}


def attendance_report_rows(db: Session, user: User, month: int, year: int, department_id: Optional[int] = None):
    start = date(year, month, 1)
    end = date(year + (month == 12), month % 12 + 1, 1)
    q = (select(Employee.id, Employee.employee_code, Employee.first_name, Employee.last_name,
                func.sum(case((Attendance.status.in_(["present", "late", "half_day"]), 1), else_=0)),
                func.sum(case((Attendance.status == "late", 1), else_=0)),
                func.sum(case((Attendance.status == "absent", 1), else_=0)),
                func.sum(Attendance.working_hours), func.sum(Attendance.overtime_hours))
         .join(Attendance, (Attendance.employee_id == Employee.id) & (Attendance.work_date >= start) & (Attendance.work_date < end), isouter=True)
         .where(Employee.status != "terminated").group_by(Employee.id, Employee.employee_code, Employee.first_name, Employee.last_name)
         .order_by(Employee.id))
    scope = employee_scope_filter(user)
    if scope is not None: q = q.where(scope)
    if department_id: q = q.where(Employee.department_id == department_id)
    return [{"employee_id": i, "employee_code": c, "employee_name": f"{f} {l}", "days_present": int(p or 0),
             "late_days": int(late or 0), "absent_days": int(ab or 0), "total_hours": round(h or 0, 1),
             "overtime_hours": round(o or 0, 1)} for i, c, f, l, p, late, ab, h, o in db.execute(q).all()]


@router.get("/attendance/report")
def attendance_report(month: int = Query(default_factory=lambda: date.today().month, ge=1, le=12),
                      year: int = Query(default_factory=lambda: date.today().year),
                      department_id: Optional[int] = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return attendance_report_rows(db, user, month, year, department_id)


@router.get("/attendance/summary")
def attendance_summary(db: Session = Depends(get_db), user: User = Depends(staff)):
    today = date.today()
    since = today - timedelta(days=13)
    q = (select(Attendance.work_date,
                func.sum(case((Attendance.status == "present", 1), else_=0)),
                func.sum(case((Attendance.status == "late", 1), else_=0)),
                func.sum(case((Attendance.status == "absent", 1), else_=0)),
                func.sum(Attendance.overtime_hours))
         .join(Employee, Employee.id == Attendance.employee_id).where(Attendance.work_date >= since))
    scope = employee_scope_filter(user)
    if scope is not None: q = q.where(scope)
    rows = db.execute(q.group_by(Attendance.work_date).order_by(Attendance.work_date)).all()
    return [{"date": d.isoformat(), "present": int(p or 0), "late": int(l or 0), "absent": int(a or 0),
             "overtime_hours": round(o or 0, 1)} for d, p, l, a, o in rows]
