"""Workforce forecasting & stability engine (Modules 14, 27).

Survival model: each employee's model probability p is read as 12-month attrition probability.
Monthly hazard h = 1-(1-p)^(1/12); expected survivors after m months = sum (1-h)^m.
"""
from datetime import date, timedelta
from collections import defaultdict
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..models import Employee, Department
from .common import latest_predictions


def _active_with_risk(db: Session):
    emps = list(db.scalars(select(Employee).where(Employee.status != "terminated")))
    preds = latest_predictions(db, [e.id for e in emps])
    return emps, preds


def historical_hire_rate(db: Session) -> float:
    since = date.today() - timedelta(days=365)
    n = db.scalar(select(func.count()).select_from(Employee).where(Employee.hire_date >= since)) or 0
    return n / 12


def forecast(db: Session, months: int = 12, monthly_hires: float | None = None, department_id: int | None = None) -> dict:
    emps, preds = _active_with_risk(db)
    if department_id:
        emps = [e for e in emps if e.department_id == department_id]
    hires = historical_hire_rate(db) if monthly_hires is None else monthly_hires
    if department_id:
        total = db.scalar(select(func.count()).select_from(Employee).where(Employee.status != "terminated")) or 1
        hires = hires * len(emps) / total
    scores = [preds[e.id].risk_score if e.id in preds else 0.15 for e in emps]
    hazards = [1 - (1 - min(max(s, 0), 0.999)) ** (1 / 12) for s in scores]
    start = len(emps)
    series, leavers_cum = [], 0.0
    today = date.today().replace(day=1)
    prev_survivors = float(start)
    mean_h = sum(hazards) / len(hazards) if hazards else 0.0
    new_hire_pool = 0.0  # surviving new hires; they leave at the average hazard
    for m in range(1, months + 1):
        surv = sum((1 - h) ** m for h in hazards)
        leavers_month = prev_survivors - surv
        prev_survivors = surv
        new_hire_pool = (new_hire_pool + hires) * (1 - mean_h)
        hc = surv + new_hire_pool
        y, mo = today.year + (today.month - 1 + m) // 12, (today.month - 1 + m) % 12 + 1
        leavers_cum += leavers_month
        series.append({"month": f"{y}-{mo:02d}", "expected_leavers": round(leavers_month, 2),
                       "cumulative_leavers": round(leavers_cum, 2), "headcount_no_hiring": round(surv, 1),
                       "projected_headcount": round(hc, 1),
                       "retention_rate": round(surv / start * 100, 1) if start else 0})
    yearly = []
    for yrs in (1, 2, 3):
        surv = sum((1 - h) ** (12 * yrs) for h in hazards)
        pool = 0.0
        for _ in range(12 * yrs):
            pool = (pool + hires) * (1 - mean_h)
        proj = surv + pool
        yearly.append({"year": yrs, "retained": round(surv, 1), "expected_leavers": round(start - surv, 1),
                       "retention_rate": round(surv / start * 100, 1) if start else 0,
                       "projected_headcount": round(proj, 1)})
    return {"current_headcount": start, "monthly_hires_assumed": round(hires, 2), "months": series, "yearly": yearly,
            "expected_leavers_12m": series[min(11, months - 1)]["cumulative_leavers"] if series else 0,
            "avg_risk": round(sum(scores) / len(scores), 4) if scores else 0}


def department_stability(db: Session) -> list[dict]:
    """Stability score 0-100: 100 - (55*avg_risk + 25*high_risk_share + 20*low_satisfaction_share)*100."""
    emps, preds = _active_with_risk(db)
    depts = {d.id: d.name for d in db.scalars(select(Department))}
    groups = defaultdict(list)
    for e in emps:
        groups[e.department_id].append(e)
    out = []
    for did, members in groups.items():
        scores = [preds[e.id].risk_score if e.id in preds else 0.15 for e in members]
        n = len(members)
        avg = sum(scores) / n
        high = sum(1 for s in scores if s >= 0.6) / n
        lowsat = sum(1 for e in members if e.job_satisfaction <= 2) / n
        stability = max(0.0, 100 - (0.55 * avg + 0.25 * high + 0.20 * lowsat) * 100 * 1.6)
        retention_12m = (1 - avg) * 100  # model score = 12-month attrition probability
        grade = "Stable" if stability >= 75 else "Watch" if stability >= 55 else "At risk"
        out.append({"department_id": did, "department": depts.get(did, "Unassigned"), "headcount": n,
                    "avg_risk": round(avg, 4), "high_risk_count": sum(1 for s in scores if s >= 0.6),
                    "stability_score": round(stability, 1), "grade": grade,
                    "forecast_retention_12m": round(retention_12m, 1)})
    return sorted(out, key=lambda r: r["stability_score"])
