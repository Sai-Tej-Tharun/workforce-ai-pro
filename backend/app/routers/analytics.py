"""Modules 10, 14, 15, 27: Dashboard, attrition analytics, forecasting, stability."""
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, case
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (Employee, Department, Attendance, LeaveRequest, Payroll, Alert, Intervention, Prediction, Task, Goal,
                      Notification, User, ROLE_ADMIN, ROLE_HR, ROLE_MANAGER, ROLE_EMPLOYEE)
from ..security import get_current_user, staff, hr_admin
from ..services import forecast as fc
from ..services.common import employee_scope_filter, latest_predictions, ttl_cache
from .leave import balance_for

router = APIRouter(prefix="/analytics", tags=["Analytics & Dashboard"])


def _month_end(y: int, m: int) -> date:
    return date(y, m, monthrange(y, m)[1])


def _months_back(n: int):
    t = date.today().replace(day=1)
    out = []
    for i in range(n - 1, -1, -1):
        m = t.month - i
        y = t.year
        while m <= 0:
            m += 12
            y -= 1
        out.append((y, m))
    return out


@ttl_cache(15)
def _staff_dashboard(db: Session, user: User):
    scope = employee_scope_filter(user)
    base = select(Employee)
    if scope is not None: base = base.where(scope)
    emps = db.scalars(base.where(Employee.status != "terminated")).unique().all()
    ids = [e.id for e in emps]
    preds = latest_predictions(db, ids)
    today = date.today()
    by_dept = defaultdict(lambda: {"headcount": 0, "salary": 0.0, "risk": []})
    gender = defaultdict(int)
    for e in emps:
        n = e.department.name if e.department else "Unassigned"
        by_dept[n]["headcount"] += 1
        by_dept[n]["salary"] += e.monthly_salary
        if e.id in preds: by_dept[n]["risk"].append(preds[e.id].risk_score)
        gender[e.gender or "Unknown"] += 1
    risk_dist = {"low": 0, "medium": 0, "high": 0}
    for p in preds.values(): risk_dist[p.risk_level] += 1
    att_today = dict(db.execute(select(Attendance.status, func.count()).where(Attendance.work_date == today, Attendance.employee_id.in_(ids)).group_by(Attendance.status)).all()) if ids else {}
    on_leave = db.scalar(select(func.count()).select_from(LeaveRequest).where(
        LeaveRequest.status == "approved", LeaveRequest.start_date <= today, LeaveRequest.end_date >= today, LeaveRequest.employee_id.in_(ids))) if ids else 0
    trend_rows = db.execute(select(Attendance.work_date, func.sum(case((Attendance.status.in_(["present", "late", "half_day"]), 1), else_=0)),
                                   func.sum(case((Attendance.status == "late", 1), else_=0)), func.sum(case((Attendance.status == "absent", 1), else_=0)))
                            .where(Attendance.work_date >= today - timedelta(days=13), Attendance.employee_id.in_(ids)).group_by(Attendance.work_date).order_by(Attendance.work_date)).all() if ids else []
    pay = []
    if user.role in (ROLE_ADMIN, ROLE_HR):
        for y, m in _months_back(6):
            g, n = db.execute(select(func.sum(Payroll.gross), func.sum(Payroll.net_pay)).where(Payroll.year == y, Payroll.month == m)).one()
            pay.append({"label": f"{y}-{m:02d}", "gross": round(g or 0, 0), "net": round(n or 0, 0)})
    hires30 = sum(1 for e in emps if e.hire_date >= today - timedelta(days=30))
    return {
        "scope": user.role,
        "employees": {"total": len(emps), "new_hires_30d": hires30, "avg_tenure": round(sum(e.years_at_company for e in emps) / len(emps), 1) if emps else 0,
                      "avg_satisfaction": round(sum(e.job_satisfaction for e in emps) / len(emps), 2) if emps else 0,
                      "gender": [{"name": k, "value": v} for k, v in gender.items()]},
        "attendance_today": {"present": att_today.get("present", 0) + att_today.get("half_day", 0), "late": att_today.get("late", 0),
                             "absent": att_today.get("absent", 0), "on_leave": on_leave, "not_marked": max(len(emps) - sum(att_today.values()), 0)},
        "attendance_trend": [{"date": d.isoformat(), "present": int(p or 0), "late": int(l or 0), "absent": int(a or 0)} for d, p, l, a in trend_rows],
        "payroll": {"trend": pay, "monthly_cost": round(sum(e.monthly_salary for e in emps), 0) if user.role in (ROLE_ADMIN, ROLE_HR) else None},
        "departments": sorted([{"name": k, "headcount": v["headcount"], "avg_salary": round(v["salary"] / v["headcount"], 0) if v["headcount"] else 0,
                                "avg_risk": round(sum(v["risk"]) / len(v["risk"]), 3) if v["risk"] else None}
                               for k, v in by_dept.items()], key=lambda x: -x["headcount"]),
        "risk": {"distribution": risk_dist, "avg": round(sum(p.risk_score for p in preds.values()) / len(preds), 3) if preds else None,
                 "predicted_leavers_12m": round(sum(p.risk_score for p in preds.values()), 1)},
        "pending_leave": db.scalar(select(func.count()).select_from(LeaveRequest).where(LeaveRequest.status == "pending", LeaveRequest.employee_id.in_(ids))) if ids else 0,
        "open_alerts": db.scalar(select(func.count()).select_from(Alert).where(Alert.status == "open")),
        "open_interventions": db.scalar(select(func.count()).select_from(Intervention).where(Intervention.status.in_(["open", "in_progress"]))),
    }


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != ROLE_EMPLOYEE:
        return _staff_dashboard(db, user, cache_key=f"{user.role}:{user.employee_id}")
    # personal dashboard for EMPLOYEE
    eid, today = user.employee_id, date.today()
    out = {"scope": "EMPLOYEE", "linked": bool(eid)}
    if eid:
        start = today.replace(day=1)
        rows = db.execute(select(Attendance.status, func.count(), func.sum(Attendance.working_hours), func.sum(Attendance.overtime_hours))
                          .where(Attendance.employee_id == eid, Attendance.work_date >= start).group_by(Attendance.status)).all()
        out["attendance_month"] = {"days": {s: n for s, n, _, _ in rows}, "hours": round(sum(r[2] or 0 for r in rows), 1),
                                   "overtime": round(sum(r[3] or 0 for r in rows), 1)}
        out["leave_balance"] = balance_for(db, eid, today.year)
        out["goals"] = [{"id": g.id, "title": g.title, "progress": g.progress, "status": g.status} for g in db.scalars(select(Goal).where(Goal.employee_id == eid).limit(5)).unique()]
        out["latest_payslip"] = None
        p = db.scalar(select(Payroll).where(Payroll.employee_id == eid).order_by(Payroll.year.desc(), Payroll.month.desc()).limit(1))
        if p: out["latest_payslip"] = {"id": p.id, "month": p.month, "year": p.year, "net_pay": p.net_pay}
    out["open_tasks"] = db.scalar(select(func.count()).select_from(Task).where(Task.assigned_to == user.id, Task.status.in_(["todo", "in_progress"])))
    out["unread_notifications"] = db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.is_read == False))  # noqa: E712
    return out


@router.get("/attrition")
def attrition(db: Session = Depends(get_db), user: User = Depends(staff)):
    """Attrition statistics, turnover analytics, department-wise analysis, employee trend reports."""
    scope = employee_scope_filter(user)
    q = select(Employee)
    if scope is not None: q = q.where(scope)
    allemps = db.scalars(q).unique().all()
    active = [e for e in allemps if e.status != "terminated"]
    today = date.today()
    preds = latest_predictions(db, [e.id for e in active])
    # monthly turnover (actual)
    monthly = []
    for y, m in _months_back(12):
        end = _month_end(y, m)
        start = date(y, m, 1)
        hc = sum(1 for e in allemps if e.hire_date <= end and (e.termination_date is None or e.termination_date > end))
        left = sum(1 for e in allemps if e.termination_date and start <= e.termination_date <= end)
        hired = sum(1 for e in allemps if start <= e.hire_date <= end)
        monthly.append({"month": f"{y}-{m:02d}", "headcount": hc, "leavers": left, "hires": hired,
                        "turnover_rate": round(left / hc * 100, 2) if hc else 0})
    left12 = sum(m["leavers"] for m in monthly)
    avg_hc = sum(m["headcount"] for m in monthly) / 12 if monthly else 0
    # department-wise
    dep = defaultdict(lambda: {"headcount": 0, "left12": 0, "risk": [], "high": 0})
    for e in allemps:
        n = e.department.name if e.department else "Unassigned"
        if e.status != "terminated":
            dep[n]["headcount"] += 1
            if e.id in preds:
                dep[n]["risk"].append(preds[e.id].risk_score)
                dep[n]["high"] += preds[e.id].risk_level == "high"
        elif e.termination_date and e.termination_date >= today - timedelta(days=365):
            dep[n]["left12"] += 1
    dept_rows = [{"department": k, "headcount": v["headcount"], "leavers_12m": v["left12"],
                  "turnover_rate_12m": round(v["left12"] / (v["headcount"] + v["left12"]) * 100, 1) if (v["headcount"] + v["left12"]) else 0,
                  "predicted_avg_risk": round(sum(v["risk"]) / len(v["risk"]) * 100, 1) if v["risk"] else None,
                  "high_risk": v["high"]} for k, v in dep.items()]
    # tenure bands
    bands = {"<1y": (0, 1), "1-3y": (1, 3), "3-5y": (3, 5), "5-10y": (5, 10), "10y+": (10, 99)}
    tenure = []
    for name, (lo, hi) in bands.items():
        grp = [e for e in active if lo <= e.years_at_company < hi]
        rs = [preds[e.id].risk_score for e in grp if e.id in preds]
        tenure.append({"band": name, "headcount": len(grp), "avg_risk": round(sum(rs) / len(rs) * 100, 1) if rs else 0})
    # risk trend (avg of daily latest scores over last 30 days)
    since = datetime.utcnow() - timedelta(days=30)
    trend_q = select(func.date(Prediction.created_at), func.avg(Prediction.risk_score), func.count()).where(Prediction.created_at >= since)
    if scope is not None: trend_q = trend_q.where(Prediction.employee_id.in_([e.id for e in allemps]))
    trend = [{"date": str(d), "avg_risk": round(float(a) * 100, 2), "predictions": n} for d, a, n in db.execute(trend_q.group_by(func.date(Prediction.created_at)).order_by(func.date(Prediction.created_at))).all()]
    # driver prevalence across high-risk
    drivers = defaultdict(int)
    for e in active:
        p = preds.get(e.id)
        if p and p.risk_level in ("high", "medium"):
            for f in (p.top_factors or [])[:3]: drivers[f["label"]] += 1
    dist = {"low": 0, "medium": 0, "high": 0}
    for p in preds.values(): dist[p.risk_level] += 1
    return {
        "stats": {"active_headcount": len(active), "leavers_12m": left12, "turnover_rate_12m": round(left12 / avg_hc * 100, 1) if avg_hc else 0,
                  "predicted_attrition_rate": round(sum(p.risk_score for p in preds.values()) / len(preds) * 100, 1) if preds else None,
                  "predicted_leavers_12m": round(sum(p.risk_score for p in preds.values()), 1), "risk_distribution": dist},
        "monthly_turnover": monthly, "departments": sorted(dept_rows, key=lambda r: -(r["predicted_avg_risk"] or 0)),
        "tenure_analysis": tenure, "risk_trend": trend,
        "top_drivers": sorted([{"driver": k, "employees": v} for k, v in drivers.items()], key=lambda x: -x["employees"])[:8],
    }


@router.get("/forecast")
def forecast(months: int = Query(12, ge=1, le=36), monthly_hires: Optional[float] = Query(None, ge=0), department_id: Optional[int] = None,
             db: Session = Depends(get_db), _: User = Depends(hr_admin)):
    return fc.forecast(db, months, monthly_hires, department_id)


@router.get("/stability")
def stability(db: Session = Depends(get_db), _: User = Depends(hr_admin)):
    f = fc.forecast(db, 12)
    return {"departments": fc.department_stability(db), "growth": {
        "current_headcount": f["current_headcount"], "projected_12m": f["months"][-1]["projected_headcount"] if f["months"] else None,
        "hires_assumed_per_month": f["monthly_hires_assumed"], "expected_leavers_12m": f["expected_leavers_12m"],
        "retention_12m": f["yearly"][0]["retention_rate"] if f["yearly"] else None}}
