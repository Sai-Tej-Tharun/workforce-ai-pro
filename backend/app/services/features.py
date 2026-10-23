"""Builds the ML feature matrix for employees from HR profile + live activity (attendance)."""
from datetime import date, timedelta
import pandas as pd
from sqlalchemy import select, func, case
from sqlalchemy.orm import Session
from ..models import Employee, Attendance
from .ml import FEATURES


def build_features(db: Session, employees: list[Employee], window_days: int = 90) -> pd.DataFrame:
    ids = [e.id for e in employees]
    since = date.today() - timedelta(days=window_days)
    act = {}
    if ids:
        rows = db.execute(
            select(Attendance.employee_id,
                   func.sum(case((Attendance.status == "late", 1), else_=0)),
                   func.sum(case((Attendance.status == "absent", 1), else_=0)),
                   func.avg(case((Attendance.status != "absent", Attendance.overtime_hours), else_=None)))
            .where(Attendance.employee_id.in_(ids), Attendance.work_date >= since)
            .group_by(Attendance.employee_id)).all()
        act = {r[0]: (int(r[1] or 0), int(r[2] or 0), float(r[3] or 0)) for r in rows}
    recs = []
    for e in employees:
        late, absent, ot = act.get(e.id, (0, 0, 0.0))
        recs.append({
            "age": e.age, "monthly_income": e.monthly_salary, "distance_from_home": e.distance_from_home,
            "job_level": e.job_level, "job_satisfaction": e.job_satisfaction,
            "environment_satisfaction": e.environment_satisfaction, "work_life_balance": e.work_life_balance,
            "years_at_company": e.years_at_company, "years_since_promotion": e.years_since_promotion,
            "total_working_years": e.total_working_years, "num_companies_worked": e.num_companies_worked,
            "training_times_last_year": e.training_times_last_year, "performance_rating": e.performance_rating,
            "stock_option_level": e.stock_option_level, "education": e.education,
            "overtime": 1 if e.overtime else 0, "late_days_90": late, "unplanned_leave_days_90": absent,
            "avg_overtime_hours": round(ot, 2), "marital_status": e.marital_status or "Single",
            "department": e.department.name if e.department else "Unknown",
        })
    return pd.DataFrame(recs, columns=FEATURES)
