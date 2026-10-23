"""Module 23: AI recommendation engine – employee improvement, workforce optimisation, team & department insights."""
from collections import defaultdict
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (Employee, Attendance, PerformanceReview, Goal, Department, User, ROLE_EMPLOYEE, ROLE_ADMIN, ROLE_HR, ROLE_MANAGER)
from ..security import get_current_user, staff, hr_admin
from ..services import recommend
from ..services.common import ensure_employee_access, employee_scope_filter, latest_predictions

router = APIRouter(prefix="/recommendations", tags=["AI Recommendations"])


def _tip(area: str, text: str, priority: str = "medium") -> dict:
    return {"area": area, "recommendation": text, "priority": priority}


def employee_tips(db: Session, emp: Employee) -> list[dict]:
    tips, since = [], date.today() - timedelta(days=60)
    rows = db.execute(select(Attendance.status, func.count(), func.avg(Attendance.overtime_hours)).where(
        Attendance.employee_id == emp.id, Attendance.work_date >= since).group_by(Attendance.status)).all()
    total = sum(n for _, n, _ in rows) or 1
    late = sum(n for s, n, _ in rows if s == "late")
    ot = [float(a or 0) for s, n, a in rows if s != "absent"]
    if late / total > 0.2:
        tips.append(_tip("Punctuality", f"Arrived late on {late} of the last {total} working days – agree a realistic start time or flexible-hours option.", "high"))
    if ot and max(ot) > 1.5:
        tips.append(_tip("Workload", "Averaging significant overtime; prioritise tasks and delegate to avoid burnout.", "high"))
    last = db.scalar(select(PerformanceReview).where(PerformanceReview.employee_id == emp.id).order_by(PerformanceReview.id.desc()).limit(1))
    if last and last.rating <= 2:
        tips.append(_tip("Performance", f"Last review rating {last.rating}/5 – set a 30/60/90-day improvement plan with weekly check-ins.", "high"))
    if last and last.improvements:
        tips.append(_tip("Development", f"Focus area from last review: {last.improvements}", "medium"))
    for g in db.scalars(select(Goal).where(Goal.employee_id == emp.id, Goal.status != "completed")).unique():
        if g.status == "at_risk" or (g.due_date and g.due_date < date.today() + timedelta(days=14) and g.progress < 60):
            tips.append(_tip("Goals", f"Goal '{g.title}' is behind ({g.progress}%). Break it into milestones or request support.", "medium"))
    if emp.training_times_last_year < 2:
        tips.append(_tip("Learning", "Fewer than 2 trainings last year – enrol in a course aligned with career goals.", "low"))
    if emp.years_since_promotion >= 3 and (not last or last.rating >= 4):
        tips.append(_tip("Career", "Strong performance but no promotion in 3+ years – discuss a growth path.", "medium"))
    if not tips:
        tips.append(_tip("Overall", "No concerns detected. Keep up the good work and continue stretch goals.", "low"))
    return tips


@router.get("/employee/{emp_id}")
def for_employee(emp_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    emp = db.get(Employee, emp_id)
    if not emp:
        raise HTTPException(404, "Employee not found")
    ensure_employee_access(db, user, emp_id)
    out = {"employee_id": emp_id, "improvement_suggestions": employee_tips(db, emp)}
    if user.role != ROLE_EMPLOYEE:
        p = latest_predictions(db, [emp_id]).get(emp_id)
        out["retention_actions"] = recommend.actions_from_factors(p.top_factors or [], 4) if p else []
        out["risk_level"] = p.risk_level if p else None
    return out


@router.get("/workforce")
def workforce(db: Session = Depends(get_db), user: User = Depends(staff)):
    """Workforce optimisation tips across the (scoped) organisation."""
    scope = employee_scope_filter(user)
    q = select(Employee).where(Employee.status != "terminated")
    if scope is not None: q = q.where(scope)
    emps = db.scalars(q).unique().all()
    preds = latest_predictions(db, [e.id for e in emps])
    tips = []
    if not emps:
        return tips
    ot_share = sum(e.overtime for e in emps) / len(emps)
    if ot_share > 0.25:
        tips.append(_tip("Workload", f"{ot_share:.0%} of employees work overtime. Review staffing levels and automate repetitive work.", "high"))
    low_sat = [e for e in emps if e.job_satisfaction <= 2]
    if len(low_sat) / len(emps) > 0.2:
        tips.append(_tip("Engagement", f"{len(low_sat)} employees report low job satisfaction – run a pulse survey and stay interviews.", "high"))
    stagnant = [e for e in emps if e.years_since_promotion >= 4]
    if stagnant:
        tips.append(_tip("Career growth", f"{len(stagnant)} employees have had no promotion in 4+ years – review promotion cycle and succession plans.", "medium"))
    underpaid = [e for e in emps if e.role and e.role.min_salary and e.monthly_salary < e.role.min_salary]
    if underpaid:
        tips.append(_tip("Compensation", f"{len(underpaid)} employees are paid below their role's salary band minimum.", "high"))
    high = [e for e in emps if preds.get(e.id) and preds[e.id].risk_level == "high"]
    if high:
        tips.append(_tip("Retention", f"{len(high)} employees are at high attrition risk – ensure each has an active intervention plan.", "high"))
    by_mgr = defaultdict(int)
    for e in emps:
        if e.manager_id: by_mgr[e.manager_id] += 1
    wide = [m for m, n in by_mgr.items() if n > 10]
    if wide:
        tips.append(_tip("Span of control", f"{len(wide)} manager(s) have more than 10 direct reports – consider adding team leads.", "medium"))
    return tips or [_tip("Overall", "Workforce indicators look healthy.", "low")]


@router.get("/department/{dept_id}")
def for_department(dept_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    dep = db.get(Department, dept_id)
    if not dep:
        raise HTTPException(404, "Department not found")
    q = select(Employee).where(Employee.department_id == dept_id, Employee.status != "terminated")
    scope = employee_scope_filter(user)
    if scope is not None: q = q.where(scope)
    emps = db.scalars(q).unique().all()
    if not emps:
        return {"department": dep.name, "headcount": 0, "recommendations": []}
    preds = latest_predictions(db, [e.id for e in emps])
    scores = [preds[e.id].risk_score for e in emps if e.id in preds]
    drivers = defaultdict(int)
    for e in emps:
        p = preds.get(e.id)
        if p and p.risk_level != "low":
            for f in (p.top_factors or [])[:2]: drivers[f["feature"]] += 1
    recs = []
    for feat, n in sorted(drivers.items(), key=lambda kv: -kv[1])[:4]:
        title, text = recommend.PLAYBOOK.get(feat, ("Review", "Review this driver."))
        recs.append({"driver": feat, "employees_affected": n, "action": title, "detail": text})
    payroll = sum(e.monthly_salary for e in emps)
    return {"department": dep.name, "headcount": len(emps), "avg_risk": round(sum(scores) / len(scores), 3) if scores else None,
            "monthly_payroll": round(payroll, 0), "budget": dep.budget, "recommendations": recs}


@router.get("/team")
def team_insights(db: Session = Depends(get_db), user: User = Depends(staff)):
    """Team performance insights for managers (or org-wide for HR/Admin, grouped by manager)."""
    scope = employee_scope_filter(user)
    q = select(Employee).where(Employee.status != "terminated")
    if scope is not None: q = q.where(scope)
    emps = db.scalars(q).unique().all()
    ids = [e.id for e in emps]
    ratings = dict(db.execute(select(PerformanceReview.employee_id, func.avg(PerformanceReview.rating)).where(PerformanceReview.employee_id.in_(ids)).group_by(PerformanceReview.employee_id)).all()) if ids else {}
    goals = dict(db.execute(select(Goal.employee_id, func.avg(Goal.progress)).where(Goal.employee_id.in_(ids)).group_by(Goal.employee_id)).all()) if ids else {}
    preds = latest_predictions(db, ids)
    groups = defaultdict(list)
    names = {e.id: e.full_name for e in emps}
    for e in emps:
        groups[e.manager_id].append(e)
    out = []
    for mid, members in groups.items():
        r = [float(ratings[e.id]) for e in members if e.id in ratings]
        g = [float(goals[e.id]) for e in members if e.id in goals]
        rs = [preds[e.id].risk_score for e in members if e.id in preds]
        insight = []
        if r and sum(r) / len(r) < 3: insight.append("Below-average review ratings – consider coaching and clearer expectations.")
        if rs and sum(rs) / len(rs) > 0.35: insight.append("Elevated attrition risk across the team – hold team retros and 1:1s.")
        if g and sum(g) / len(g) < 50: insight.append("Goal progress is low – re-prioritise objectives.")
        out.append({"manager": names.get(mid) if mid else "No manager", "team_size": len(members),
                    "avg_rating": round(sum(r) / len(r), 2) if r else None, "avg_goal_progress": round(sum(g) / len(g), 0) if g else None,
                    "avg_risk": round(sum(rs) / len(rs), 3) if rs else None, "insights": insight or ["Team indicators look healthy."]})
    return sorted(out, key=lambda x: -(x["avg_risk"] or 0))
