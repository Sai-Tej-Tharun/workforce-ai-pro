"""Module 22: Performance reviews, ratings, history, goal tracking."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PerformanceReview, Goal, Employee, User, ROLE_EMPLOYEE, ROLE_ADMIN, ROLE_HR
from ..schemas import ReviewIn, GoalIn, GoalUpdate
from ..security import get_current_user, staff
from ..services import risk
from ..services.common import audit, ensure_employee_access, employee_scope_filter, notify

router = APIRouter(prefix="/performance", tags=["Performance"])


def _rev(r: PerformanceReview) -> dict:
    return {"id": r.id, "employee_id": r.employee_id, "employee_name": r.employee.full_name if r.employee else None, "reviewer_id": r.reviewer_id,
            "period": r.period, "rating": r.rating, "strengths": r.strengths, "improvements": r.improvements, "comments": r.comments, "created_at": r.created_at}


def _goal(g: Goal) -> dict:
    return {"id": g.id, "employee_id": g.employee_id, "employee_name": g.employee.full_name if g.employee else None, "title": g.title,
            "description": g.description, "progress": g.progress, "status": g.status, "due_date": g.due_date}


@router.get("/reviews")
def list_reviews(employee_id: Optional[int] = None, page: int = Query(1, ge=1), size: int = Query(30, ge=1, le=100),
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = select(PerformanceReview).join(Employee, Employee.id == PerformanceReview.employee_id)
    scope = employee_scope_filter(user)
    if scope is not None: q = q.where(scope)
    if employee_id:
        ensure_employee_access(db, user, employee_id)
        q = q.where(PerformanceReview.employee_id == employee_id)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(PerformanceReview.id.desc()).offset((page - 1) * size).limit(size)).unique().all()
    return {"items": [_rev(r) for r in rows], "total": total, "page": page, "size": size}


@router.post("/reviews", status_code=201)
def create_review(body: ReviewIn, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    ensure_employee_access(db, user, body.employee_id)
    if body.employee_id == user.employee_id and user.role not in (ROLE_ADMIN, ROLE_HR):
        raise HTTPException(403, "You cannot review yourself")
    r = PerformanceReview(**body.model_dump(), reviewer_id=user.id)
    db.add(r)
    emp = db.get(Employee, body.employee_id)
    emp.performance_rating = max(1, min(4, round(body.rating * 4 / 5)))  # 1-5 review scale -> 1-4 model scale
    eu = db.scalar(select(User.id).where(User.employee_id == emp.id))
    if eu:
        notify(db, [eu], "New performance review", f"A review for {body.period} was added (rating {body.rating}/5).", "system", "low", "/performance")
    db.commit()
    audit(db, user, "CREATE", "performance_review", r.id, {"employee_id": emp.id, "rating": body.rating}, request)
    risk.recalc_one(db, emp, "performance_review")
    return _rev(r)


@router.get("/summary/{employee_id}")
def summary(employee_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_employee_access(db, user, employee_id)
    revs = db.scalars(select(PerformanceReview).where(PerformanceReview.employee_id == employee_id).order_by(PerformanceReview.id)).unique().all()
    goals = db.scalars(select(Goal).where(Goal.employee_id == employee_id)).unique().all()
    return {"average_rating": round(sum(r.rating for r in revs) / len(revs), 2) if revs else None,
            "history": [{"period": r.period, "rating": r.rating} for r in revs],
            "goal_completion": round(sum(g.progress for g in goals) / len(goals), 0) if goals else None}


@router.get("/goals")
def list_goals(employee_id: Optional[int] = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = select(Goal).join(Employee, Employee.id == Goal.employee_id)
    scope = employee_scope_filter(user)
    if scope is not None: q = q.where(scope)
    if employee_id: q = q.where(Goal.employee_id == employee_id)
    return [_goal(g) for g in db.scalars(q.order_by(Goal.id.desc()).limit(300)).unique()]


@router.post("/goals", status_code=201)
def create_goal(body: GoalIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role == ROLE_EMPLOYEE and body.employee_id != user.employee_id:
        raise HTTPException(403, "Employees can only create their own goals")
    ensure_employee_access(db, user, body.employee_id)
    g = Goal(**body.model_dump())
    db.add(g)
    db.commit()
    audit(db, user, "CREATE", "goal", g.id, {"title": g.title}, request)
    return _goal(g)


@router.patch("/goals/{gid}")
def update_goal(gid: int, body: GoalUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    g = db.get(Goal, gid)
    if not g:
        raise HTTPException(404, "Goal not found")
    ensure_employee_access(db, user, g.employee_id)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(g, k, v)
    if data.get("progress") == 100 and "status" not in data:
        g.status = "completed"
    db.commit()
    audit(db, user, "UPDATE", "goal", gid, data, request)
    return _goal(g)


@router.delete("/goals/{gid}", status_code=204)
def delete_goal(gid: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    g = db.get(Goal, gid)
    if not g:
        raise HTTPException(404, "Goal not found")
    if user.role == ROLE_EMPLOYEE and g.employee_id != user.employee_id:
        raise HTTPException(403, "Not allowed")
    ensure_employee_access(db, user, g.employee_id)
    db.delete(g)
    db.commit()
    audit(db, user, "DELETE", "goal", gid, request=request)
