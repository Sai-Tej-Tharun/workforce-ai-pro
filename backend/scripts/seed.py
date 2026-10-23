"""Seed the database with a realistic demo organisation, train the ML model, and build risk history.

Usage:  python -m scripts.seed [--reset] [--employees 90] [--dataset-rows 3000]
Demo logins:
  admin@workforce.ai / Admin@123 | hr@workforce.ai / Hr@12345 | manager@workforce.ai / Manager@123 | employee@workforce.ai / Employee@123
"""
import argparse, random, sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from sqlalchemy import select, update

from app.database import Base, engine, SessionLocal
from app import models as m
from app.security import hash_password
from app.routers import datasets as ds_router, payroll as payroll_router
from app.schemas import PayrollGenerateIn
from app.services import risk
from ml.synthetic import generate, DEPARTMENTS

FIRST = ["Aarav", "Maya", "Liam", "Sofia", "Noah", "Priya", "Ethan", "Zara", "Lucas", "Ananya", "Mason", "Isla", "Arjun", "Emma", "Omar",
         "Chloe", "Ravi", "Nora", "Daniel", "Meera", "Leo", "Aisha", "Kabir", "Ella", "Sam", "Tara", "Jon", "Neha", "Owen", "Lina"]
LAST = ["Sharma", "Patel", "Nguyen", "Garcia", "Kim", "Singh", "Brown", "Khan", "Silva", "Rossi", "Muller", "Ali", "Tanaka", "Lopez",
        "Reddy", "Cohen", "Novak", "Okafor", "Ivanov", "Costa", "Mehta", "Walker", "Hughes", "Das"]
ROLES = {
    "Engineering": ["Software Engineer", "QA Engineer", "DevOps Engineer", "Engineering Manager"],
    "Sales": ["Sales Executive", "Account Manager", "Sales Manager"],
    "Human Resources": ["HR Executive", "Recruiter", "HR Manager"],
    "Finance": ["Accountant", "Financial Analyst", "Finance Manager"],
    "Operations": ["Operations Associate", "Logistics Coordinator", "Operations Manager"],
    "Customer Support": ["Support Agent", "Support Lead", "Support Manager"],
}
DEPT_BUDGET = {"Engineering": 900000, "Sales": 600000, "Human Resources": 150000, "Finance": 250000, "Operations": 500000, "Customer Support": 350000}


def weekdays_back(n_days):
    d, out = date.today(), []
    for i in range(n_days):
        x = d - timedelta(days=i)
        if x.weekday() < 5:
            out.append(x)
    return out


def seed(db, n_active=90, n_terminated=14, dataset_rows=3000, rng_seed=11):
    rnd, nrng = random.Random(rng_seed), np.random.default_rng(rng_seed)
    # ---------- reference data ----------
    depts = {n: m.Department(name=n, description=f"{n} department", budget=DEPT_BUDGET[n]) for n in DEPARTMENTS}
    db.add_all(depts.values()); db.flush()
    roles = {}
    for dn, titles in ROLES.items():
        for i, t in enumerate(titles):
            lvl = min(5, i + 1) if "Manager" not in t else 4
            r = m.JobRole(title=t, department_id=depts[dn].id, level=lvl, min_salary=2800 + lvl * 1500, max_salary=5500 + lvl * 3500)
            db.add(r); roles[(dn, t)] = r
    db.flush()
    shifts = [m.Shift(name="Morning", start_time=time(9, 0), end_time=time(17, 0), standard_hours=8),
              m.Shift(name="Evening", start_time=time(14, 0), end_time=time(22, 0), standard_hours=8),
              m.Shift(name="Night", start_time=time(22, 0), end_time=time(6, 0), standard_hours=8)]
    db.add_all(shifts)
    db.add_all([m.LeavePolicy(leave_type="Annual", annual_quota=18, carry_forward=True, description="Paid annual leave"),
                m.LeavePolicy(leave_type="Sick", annual_quota=10, description="Medical leave"),
                m.LeavePolicy(leave_type="Casual", annual_quota=8, description="Short personal leave"),
                m.LeavePolicy(leave_type="Unpaid", annual_quota=30, description="Loss-of-pay leave")])
    db.flush()

    # ---------- employees ----------
    pool = generate(n_active + n_terminated + 60, seed=rng_seed + 1, target_rate=0.30)
    yes, no = pool[pool.attrition == "Yes"].reset_index(drop=True), pool[pool.attrition == "No"].reset_index(drop=True)
    n_yes = int(n_active * 0.22)
    active_rows = [r for _, r in no.iloc[: n_active - n_yes].iterrows()] + [r for _, r in yes.iloc[: n_yes].iterrows()]
    term_rows = [r for _, r in yes.iloc[n_yes: n_yes + n_terminated].iterrows()]
    rnd.shuffle(active_rows)
    used_emails, emps, counter = set(), [], 0

    def mk(row, dept, terminated=False, **over):
        nonlocal counter
        counter += 1
        while True:
            f, l = rnd.choice(FIRST), rnd.choice(LAST)
            email = over.get("email") or f"{f}.{l}{counter}@workforce.ai".lower()
            if email not in used_emails: break
        used_emails.add(email)
        titles = [t for t in ROLES[dept] if "Manager" not in t] or ROLES[dept]
        role = roles[(dept, over.pop("role", rnd.choice(titles)))]
        yrs = float(row.years_at_company)
        term = date.today() - timedelta(days=rnd.randint(10, 340)) if terminated else None
        hire = (term or date.today()) - timedelta(days=int(yrs * 365) + 20)
        e = m.Employee(
            employee_code=f"TMP{counter}", first_name=over.pop("first_name", f), last_name=over.pop("last_name", l), email=email,
            phone=f"+1-555-{rnd.randint(1000, 9999)}", gender=rnd.choice(["Male", "Female", "Other"]) if rnd.random() < .05 else rnd.choice(["Male", "Female"]),
            age=int(row.age), marital_status=row.marital_status, education=int(row.education), department_id=depts[dept].id,
            role_id=role.id, shift_id=rnd.choice(shifts[:2]).id, hire_date=hire, status="terminated" if terminated else "active",
            termination_date=term, monthly_salary=float(row.monthly_income), job_level=int(row.job_level), distance_from_home=float(row.distance_from_home),
            years_at_company=yrs, years_since_promotion=float(row.years_since_promotion), total_working_years=float(row.total_working_years),
            num_companies_worked=int(row.num_companies_worked), overtime=row.overtime == "Yes", job_satisfaction=int(row.job_satisfaction),
            environment_satisfaction=int(row.environment_satisfaction), work_life_balance=int(row.work_life_balance),
            training_times_last_year=int(row.training_times_last_year), performance_rating=int(row.performance_rating),
            stock_option_level=int(row.stock_option_level))
        for k, v in over.items(): setattr(e, k, v)
        db.add(e); db.flush()
        e.employee_code = f"EMP{e.id:04d}"
        e._act = (float(row.late_days_90), float(row.unplanned_leave_days_90), float(row.avg_overtime_hours))
        return e

    # managers (one per department), then staff
    managers = {}
    for i, dn in enumerate(DEPARTMENTS):
        base = no.iloc[40 + i].copy(); base["job_level"] = 4; base["monthly_income"] = max(float(base["monthly_income"]), 9500); base["years_at_company"] = max(float(base["years_at_company"]), 6)
        base["job_satisfaction"], base["overtime"] = 4, "No"
        title = [t for t in ROLES[dn] if "Manager" in t][0]
        over = dict(role=title, job_level=4)
        if dn == "Engineering": over.update(first_name="Maya", last_name="Manager", email="manager@workforce.ai")
        if dn == "Human Resources": over.update(first_name="Hannah", last_name="Rivers", email="hr@workforce.ai")
        managers[dn] = mk(base, dn, **over)
    for j, row in enumerate(active_rows):
        dn = row.department if row.department in DEPARTMENTS else rnd.choice(DEPARTMENTS)
        over = {"manager_id": managers[dn].id}
        if j == 0: dn = "Engineering"; over = {"manager_id": managers[dn].id, "first_name": "Eli", "last_name": "Employee", "email": "employee@workforce.ai", "role": "Software Engineer"}
        emps.append(mk(row, dn, **over))
    admin_emp = mk(no.iloc[60], "Human Resources", first_name="Alex", last_name="Admin", email="admin@workforce.ai", manager_id=managers["Human Resources"].id, role="HR Executive")
    term = [mk(r, r.department if r.department in DEPARTMENTS else "Sales", terminated=True, manager_id=managers.get(r.department, managers["Sales"]).id) for r in term_rows]
    db.commit()
    everyone = list(managers.values()) + emps + [admin_emp]

    # ---------- users ----------
    users = {
        "admin": m.User(email="admin@workforce.ai", full_name="Alex Admin", hashed_password=hash_password("Admin@123"), role="ADMIN", employee_id=admin_emp.id),
        "hr": m.User(email="hr@workforce.ai", full_name="Hannah Rivers", hashed_password=hash_password("Hr@12345"), role="HR", employee_id=managers["Human Resources"].id),
        "manager": m.User(email="manager@workforce.ai", full_name="Maya Manager", hashed_password=hash_password("Manager@123"), role="MANAGER", employee_id=managers["Engineering"].id),
        "employee": m.User(email="employee@workforce.ai", full_name="Eli Employee", hashed_password=hash_password("Employee@123"), role="EMPLOYEE", employee_id=emps[0].id),
    }
    db.add_all(users.values())
    for dn, mg in managers.items():  # other department managers get MANAGER logins
        if dn not in ("Engineering", "Human Resources"):
            db.add(m.User(email=mg.email, full_name=mg.full_name, hashed_password=hash_password("Manager@123"), role="MANAGER", employee_id=mg.id))
    db.commit()

    # ---------- attendance (≈95 days; patterns follow each employee's underlying behaviour) ----------
    days = weekdays_back(95)
    batch = []
    for e in everyone:
        late_d, abs_d, ot_h = e._act
        p_late, p_abs = min(late_d / 64, 0.6), min(abs_d / 64, 0.4)
        for d in days:
            if d == date.today() and rnd.random() < .3:
                continue  # some people haven't checked in yet today
            r = rnd.random()
            if r < p_abs:
                batch.append(m.Attendance(employee_id=e.id, work_date=d, status="absent")); continue
            late = rnd.random() < p_late
            start = (e.shift.start_time if e.shift else time(9, 0)) if e.shift_id else time(9, 0)
            sh = {s.id: s for s in shifts}[e.shift_id]
            ci = datetime.combine(d, sh.start_time) + timedelta(minutes=rnd.randint(15, 50) if late else rnd.randint(-15, 8))
            ot = round(float(max(0, nrng.normal(ot_h, 0.6))), 2) if (e.overtime or ot_h > 1) and rnd.random() < .75 else 0.0
            hours = round(8 + ot + rnd.uniform(-0.3, 0.4), 2)
            batch.append(m.Attendance(employee_id=e.id, work_date=d, check_in=ci, check_out=ci + timedelta(hours=hours),
                                      working_hours=hours, overtime_hours=ot, status="late" if late else "present"))
    db.bulk_save_objects(batch); db.commit()

    # ---------- leave, reviews, goals, tasks ----------
    hr_user, mgr_user = users["hr"], users["manager"]
    for e in rnd.sample(emps, min(30, len(emps))):
        lt = rnd.choice(["Annual", "Sick", "Casual", "Annual", "Unpaid"])
        start = date.today() + timedelta(days=rnd.randint(-60, 25))
        while start.weekday() >= 5: start += timedelta(days=1)
        end = start + timedelta(days=rnd.randint(0, 3))
        from app.routers.leave import working_days
        status = rnd.choice(["approved", "approved", "pending", "rejected"]) if start < date.today() + timedelta(days=5) else "pending"
        db.add(m.LeaveRequest(employee_id=e.id, leave_type=lt, start_date=start, end_date=end, days=max(1, working_days(start, end)),
                              reason=rnd.choice(["Family event", "Medical appointment", "Travel", "Personal work", "Fever"]), status=status,
                              reviewed_by=hr_user.id if status in ("approved", "rejected") else None))
    for e in everyone:
        for per in ("2026-Q1", "2026-Q2"):
            rating = int(np.clip(e.performance_rating + rnd.choice([-1, 0, 0, 1]) + (1 if e.performance_rating == 3 else 0), 1, 5))
            db.add(m.PerformanceReview(employee_id=e.id, reviewer_id=hr_user.id, period=per, rating=rating,
                                       strengths=rnd.choice(["Ownership", "Collaboration", "Technical depth", "Customer focus"]),
                                       improvements=rnd.choice(["Time management", "Delegation", "Documentation", "Communication", None]),
                                       comments="Auto-seeded review"))
        for t in rnd.sample(["Complete certification", "Mentor a junior colleague", "Improve process documentation", "Deliver Q4 project", "Reduce ticket backlog"], rnd.randint(1, 3)):
            prog = rnd.choice([10, 30, 50, 70, 90, 100])
            db.add(m.Goal(employee_id=e.id, title=t, progress=prog, status="completed" if prog == 100 else rnd.choice(["in_progress", "in_progress", "at_risk"]),
                          due_date=date.today() + timedelta(days=rnd.randint(-10, 90))))
    for title, prio, due, who in [("Review Q4 headcount plan", "high", 3, hr_user), ("Run stay interviews for high-risk staff", "critical", 2, hr_user),
                                  ("Update leave policy handbook", "medium", 14, hr_user), ("Approve pending leave requests", "high", 1, mgr_user),
                                  ("Prepare team performance review", "medium", 10, mgr_user), ("Audit overtime hours", "high", -2, hr_user)]:
        db.add(m.Task(title=title, priority=prio, assigned_to=who.id, created_by=users["admin"].id, due_date=date.today() + timedelta(days=due), status="todo"))
    db.commit()

    # ---------- payroll (last 3 months) ----------
    t = date.today().replace(day=1)
    for k in (3, 2, 1):
        mo, yr = t.month - k, t.year
        if mo <= 0: mo, yr = mo + 12, yr - 1
        payroll_router.generate(PayrollGenerateIn(month=mo, year=yr, bonus=0, incentive=0), None, db, users["hr"])
    db.execute(update(m.Payroll).values(status="paid")); db.commit()

    # ---------- dataset + model ----------
    df = generate(dataset_rows, seed=7)
    d = ds_router.register_dataset(db, df, "hr_attrition_baseline", "hr_attrition_sample.csv", users["admin"].id)
    rec, metrics = ds_router.train_and_register(db, d, users["admin"].id, True)
    print(f"Model: {metrics['algorithm']}  AUC={metrics['roc_auc']}  acc={metrics['accuracy']}  F1={metrics['f1']}")

    # ---------- risk history: 3 snapshots (28d, 14d, today) with behavioural drift between them ----------
    active = [e for e in everyone + [admin_emp] if e.status == "active"]
    for days_ago in (28, 14, 0):
        last = {c: db.scalar(select(__import__("sqlalchemy").func.coalesce(__import__("sqlalchemy").func.max(c.id), 0))) for c in
                (m.Prediction, m.MonitoringLog, m.Alert, m.Notification, m.ActivityEvent, m.Intervention, m.InterventionLog)}
        if days_ago != 28:  # drift: some employees' circumstances change
            for e in rnd.sample(active, 14):
                kind = rnd.choice(["sat", "ot", "promo", "wlb"])
                if kind == "sat": e.job_satisfaction = max(1, e.job_satisfaction - 1)
                elif kind == "ot": e.overtime = True
                elif kind == "promo": e.years_since_promotion += 1.5
                else: e.work_life_balance = max(1, e.work_life_balance - 1)
            for e in rnd.sample(active, 5):
                e.job_satisfaction = min(4, e.job_satisfaction + 1); e.overtime = False
            db.commit()
        risk.recalc(db, active, "seed" if days_ago else "batch")
        if days_ago:
            delta = timedelta(days=days_ago)
            for cls in last:
                for obj in db.scalars(select(cls).where(cls.id > last[cls])):
                    obj.created_at = obj.created_at - delta
            db.commit()
    # make intervention workflow look lived-in
    ivs = db.scalars(select(m.Intervention).order_by(m.Intervention.id)).unique().all()
    for i, iv in enumerate(ivs):
        iv.follow_up_date = (iv.created_at + timedelta(days=7)).date()
        iv.assigned_to = hr_user.id
        if iv.created_at < datetime.utcnow() - timedelta(days=10) and i % 3 == 0:
            iv.status, iv.outcome, iv.closed_at = "completed", rnd.choice(["retained", "retained", "left"]), datetime.utcnow() - timedelta(days=rnd.randint(1, 8))
            db.add(m.InterventionLog(intervention_id=iv.id, action="updated", note="status: open -> completed", user_id=hr_user.id))
        elif i % 3 == 1:
            iv.status = "in_progress"
            db.add(m.InterventionLog(intervention_id=iv.id, action="updated", note="status: open -> in_progress; stay interview scheduled", user_id=hr_user.id))
    db.commit()
    # welcome notifications
    for u in users.values():
        db.add(m.Notification(user_id=u.id, title="Welcome to WorkForce AI Pro", message="Your account is ready. Explore the dashboard.", category="system"))
    db.commit()
    n_alerts = db.scalar(select(__import__("sqlalchemy").func.count()).select_from(m.Alert))
    print(f"Seeded {len(everyone) + len(term)} employees ({len(term)} terminated), {n_alerts} alerts, {len(ivs)} interventions.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="drop and recreate all tables first")
    ap.add_argument("--employees", type=int, default=90)
    ap.add_argument("--dataset-rows", type=int, default=3000)
    a = ap.parse_args()
    if a.reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(m.User.id).limit(1)) and not a.reset:
            print("Database already has data. Use --reset to re-seed."); sys.exit(0)
        seed(db, n_active=a.employees, dataset_rows=a.dataset_rows)
