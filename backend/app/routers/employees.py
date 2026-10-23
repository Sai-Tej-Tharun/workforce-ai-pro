"""Modules 2, 24: Employee management, profile, search and multi-filter."""
import uuid
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Employee, Prediction, Attendance, Intervention, User, ROLE_EMPLOYEE
from ..schemas import EmployeeCreate, EmployeeUpdate
from ..security import get_current_user, hr_admin, admin_only
from ..services import risk
from ..services.common import (audit, diff, employee_scope_filter, ensure_employee_access, latest_predictions)

router = APIRouter(prefix="/employees", tags=["Employees"])

SORTABLE = {"id": Employee.id, "name": Employee.first_name, "hire_date": Employee.hire_date,
            "salary": Employee.monthly_salary, "age": Employee.age, "tenure": Employee.years_at_company}
# fields that influence the AI model -> recalc risk when they change
RISK_FIELDS = {"monthly_salary", "job_satisfaction", "environment_satisfaction", "work_life_balance", "overtime",
               "years_since_promotion", "job_level", "training_times_last_year", "performance_rating",
               "stock_option_level", "distance_from_home", "manager_id", "department_id", "marital_status"}


def emp_dict(e: Employee, pred: Optional[Prediction] = None) -> dict:
    return {
        **{c.name: getattr(e, c.name) for c in e.__table__.columns},
        "department_name": e.department.name if e.department else None,
        "role_title": e.role.title if e.role else None,
        "shift_name": e.shift.name if e.shift else None,
        "risk_score": pred.risk_score if pred else None,
        "risk_level": pred.risk_level if pred else None,
        "risk_confidence": pred.confidence if pred else None,
    }


@router.get("")
def list_employees(
    search: Optional[str] = None, department_id: Optional[int] = None, role_id: Optional[int] = None,
    status: Optional[str] = None, risk_level: Optional[str] = Query(None, pattern="^(low|medium|high)$"),
    min_salary: Optional[float] = None, max_salary: Optional[float] = None, overtime: Optional[bool] = None,
    min_late_days: Optional[int] = Query(None, description="late arrivals in the last 30 days"),
    manager_id: Optional[int] = None, sort: str = "id", order: str = "asc",
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    q = select(Employee)
    scope = employee_scope_filter(user)
    if scope is not None:
        q = q.where(scope)
    if search:
        like = f"%{search.strip()}%"
        q = q.where(or_(Employee.first_name.like(like), Employee.last_name.like(like),
                        Employee.email.like(like), Employee.employee_code.like(like),
                        (Employee.first_name + " " + Employee.last_name).like(like)))
    if department_id: q = q.where(Employee.department_id == department_id)
    if role_id: q = q.where(Employee.role_id == role_id)
    if status: q = q.where(Employee.status == status)
    if manager_id: q = q.where(Employee.manager_id == manager_id)
    if min_salary is not None: q = q.where(Employee.monthly_salary >= min_salary)
    if max_salary is not None: q = q.where(Employee.monthly_salary <= max_salary)
    if overtime is not None: q = q.where(Employee.overtime == overtime)
    if risk_level:
        latest = select(func.max(Prediction.id)).group_by(Prediction.employee_id).scalar_subquery()
        q = q.where(Employee.id.in_(select(Prediction.employee_id).where(Prediction.id.in_(latest), Prediction.risk_level == risk_level)))
    if min_late_days:
        since = date.today() - timedelta(days=30)
        q = q.where(Employee.id.in_(select(Attendance.employee_id).where(Attendance.work_date >= since, Attendance.status == "late")
                                    .group_by(Attendance.employee_id).having(func.count() >= min_late_days)))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    col = SORTABLE.get(sort, Employee.id)
    q = q.order_by(col.desc() if order == "desc" else col.asc()).offset((page - 1) * size).limit(size)
    emps = db.scalars(q).unique().all()
    preds = latest_predictions(db, [e.id for e in emps])
    can_see_risk = user.role != ROLE_EMPLOYEE
    return {"items": [emp_dict(e, preds.get(e.id) if can_see_risk else None) for e in emps],
            "total": total, "page": page, "size": size}


@router.post("", status_code=201)
def create_employee(body: EmployeeCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    if db.scalar(select(Employee.id).where(Employee.email == body.email.lower())):
        raise HTTPException(409, "An employee with this email already exists")
    data = body.model_dump(exclude={"employee_code"})
    data["email"] = data["email"].lower()
    emp = Employee(employee_code=body.employee_code or f"T{uuid.uuid4().hex[:15]}", **data)
    db.add(emp)
    db.flush()
    if not body.employee_code:
        emp.employee_code = f"EMP{emp.id:04d}"
    db.commit()
    audit(db, user, "CREATE", "employee", emp.id, {"email": emp.email}, request)
    risk.recalc_one(db, emp, "employee_created")
    db.refresh(emp)
    return emp_dict(emp, latest_predictions(db, [emp.id]).get(emp.id))


@router.get("/{emp_id}")
def get_employee(emp_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    emp = db.get(Employee, emp_id)
    if not emp:
        raise HTTPException(404, "Employee not found")
    ensure_employee_access(db, user, emp_id)
    pred = latest_predictions(db, [emp_id]).get(emp_id) if user.role != ROLE_EMPLOYEE else None
    return emp_dict(emp, pred)


@router.patch("/{emp_id}")
def update_employee(emp_id: int, body: EmployeeUpdate, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(hr_admin)):
    emp = db.get(Employee, emp_id)
    if not emp:
        raise HTTPException(404, "Employee not found")
    data = body.model_dump(exclude_unset=True)
    if "email" in data:
        data["email"] = data["email"].lower()
        dup = db.scalar(select(Employee.id).where(Employee.email == data["email"], Employee.id != emp_id))
        if dup:
            raise HTTPException(409, "Email already in use")
    if data.get("manager_id") == emp_id:
        raise HTTPException(422, "An employee cannot be their own manager")
    changes = diff(emp, data)
    for k, v in data.items():
        setattr(emp, k, v)
    db.commit()
    audit(db, user, "UPDATE", "employee", emp_id, changes, request)
    if RISK_FIELDS & set(changes):
        risk.recalc_one(db, emp, "profile_update")
    return emp_dict(emp, latest_predictions(db, [emp_id]).get(emp_id))


@router.patch("/me/profile")
def update_my_profile(body: dict, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Employees may edit only their own contact details."""
    if not user.employee_id:
        raise HTTPException(404, "No employee profile linked to this account")
    emp = db.get(Employee, user.employee_id)
    allowed = {k: str(v)[:255] for k, v in body.items() if k in {"phone", "address"}}
    changes = diff(emp, allowed)
    for k, v in allowed.items():
        setattr(emp, k, v)
    db.commit()
    audit(db, user, "UPDATE", "employee_profile", emp.id, changes, request)
    return emp_dict(emp)


@router.post("/{emp_id}/assign")
def assign_department_role(emp_id: int, body: dict, request: Request, db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    """Role assignment + employee/department mapping."""
    emp = db.get(Employee, emp_id)
    if not emp:
        raise HTTPException(404, "Employee not found")
    data = {k: body[k] for k in ("department_id", "role_id", "manager_id") if k in body}
    changes = diff(emp, data)
    for k, v in data.items():
        setattr(emp, k, v)
    db.commit()
    audit(db, user, "ASSIGN", "employee", emp_id, changes, request)
    return emp_dict(emp)


@router.post("/{emp_id}/terminate")
def terminate(emp_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    emp = db.get(Employee, emp_id)
    if not emp:
        raise HTTPException(404, "Employee not found")
    emp.status, emp.termination_date = "terminated", date.today()
    for iv in db.scalars(select(Intervention).where(Intervention.employee_id == emp_id, Intervention.status.in_(["open", "in_progress"]))):
        iv.status, iv.outcome = "completed", "left"
    db.commit()
    audit(db, user, "TERMINATE", "employee", emp_id, request=request)
    return emp_dict(emp)


@router.delete("/{emp_id}", status_code=204)
def delete_employee(emp_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(admin_only)):
    emp = db.get(Employee, emp_id)
    if not emp:
        raise HTTPException(404, "Employee not found")
    db.delete(emp)
    db.commit()
    audit(db, user, "DELETE", "employee", emp_id, {"email": emp.email}, request)
