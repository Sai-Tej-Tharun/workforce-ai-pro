"""Module 3: Departments, roles and department statistics."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Department, JobRole, Employee, User
from ..schemas import DepartmentIn, DepartmentOut, JobRoleIn, JobRoleOut
from ..security import get_current_user, hr_admin, staff
from ..services.common import audit, diff, latest_predictions

router = APIRouter(tags=["Departments & Roles"])


@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(Department).order_by(Department.name)).all()


@router.post("/departments", response_model=DepartmentOut, status_code=201)
def create_department(body: DepartmentIn, request: Request, db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    if db.scalar(select(Department.id).where(func.lower(Department.name) == body.name.lower())):
        raise HTTPException(409, "Department already exists")
    d = Department(**body.model_dump())
    db.add(d)
    db.commit()
    audit(db, user, "CREATE", "department", d.id, body.model_dump(), request)
    return d


@router.put("/departments/{dept_id}", response_model=DepartmentOut)
def update_department(dept_id: int, body: DepartmentIn, request: Request, db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    d = db.get(Department, dept_id)
    if not d:
        raise HTTPException(404, "Department not found")
    changes = diff(d, body.model_dump())
    for k, v in body.model_dump().items():
        setattr(d, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Department name already exists")
    audit(db, user, "UPDATE", "department", dept_id, changes, request)
    return d


@router.delete("/departments/{dept_id}", status_code=204)
def delete_department(dept_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    d = db.get(Department, dept_id)
    if not d:
        raise HTTPException(404, "Department not found")
    n = db.scalar(select(func.count()).select_from(Employee).where(Employee.department_id == dept_id, Employee.status != "terminated"))
    if n:
        raise HTTPException(409, f"Department still has {n} active employees; reassign them first")
    db.delete(d)
    db.commit()
    audit(db, user, "DELETE", "department", dept_id, {"name": d.name}, request)


@router.get("/departments/stats")
def department_stats(db: Session = Depends(get_db), _: User = Depends(staff)):
    rows = db.execute(
        select(Department.id, Department.name, Department.budget, func.count(Employee.id),
               func.avg(Employee.monthly_salary), func.sum(Employee.monthly_salary),
               func.avg(Employee.job_satisfaction), func.avg(Employee.years_at_company))
        .join(Employee, (Employee.department_id == Department.id) & (Employee.status != "terminated"), isouter=True)
        .group_by(Department.id, Department.name, Department.budget)).all()
    emps = db.execute(select(Employee.id, Employee.department_id).where(Employee.status != "terminated")).all()
    preds = latest_predictions(db)
    risk_by_dept: dict = {}
    for eid, did in emps:
        if eid in preds:
            risk_by_dept.setdefault(did, []).append(preds[eid].risk_score)
    out = []
    for did, name, budget, n, avg_sal, tot_sal, sat, ten in rows:
        rs = risk_by_dept.get(did, [])
        out.append({"id": did, "name": name, "budget": budget, "headcount": n,
                    "avg_salary": round(avg_sal or 0, 2), "payroll_monthly": round(tot_sal or 0, 2),
                    "avg_satisfaction": round(sat or 0, 2), "avg_tenure": round(ten or 0, 2),
                    "avg_risk": round(sum(rs) / len(rs), 4) if rs else None,
                    "high_risk": sum(1 for s in rs if s >= 0.6)})
    return out


@router.get("/roles", response_model=list[JobRoleOut])
def list_roles(department_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    q = select(JobRole).order_by(JobRole.title)
    if department_id:
        q = q.where(JobRole.department_id == department_id)
    return db.scalars(q).all()


@router.post("/roles", response_model=JobRoleOut, status_code=201)
def create_role(body: JobRoleIn, request: Request, db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    r = JobRole(**body.model_dump())
    db.add(r)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Role already exists in this department")
    audit(db, user, "CREATE", "job_role", r.id, body.model_dump(), request)
    return r


@router.put("/roles/{role_id}", response_model=JobRoleOut)
def update_role(role_id: int, body: JobRoleIn, request: Request, db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    r = db.get(JobRole, role_id)
    if not r:
        raise HTTPException(404, "Role not found")
    changes = diff(r, body.model_dump())
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    db.commit()
    audit(db, user, "UPDATE", "job_role", role_id, changes, request)
    return r


@router.delete("/roles/{role_id}", status_code=204)
def delete_role(role_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    r = db.get(JobRole, role_id)
    if not r:
        raise HTTPException(404, "Role not found")
    db.delete(r)
    db.commit()
    audit(db, user, "DELETE", "job_role", role_id, {"title": r.title}, request)
