"""Modules 13 & 18: Employee risk monitoring, activity ingestion, live feed, instability detection, WebSocket."""
from datetime import date, datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import select, func, case
from sqlalchemy.orm import Session

from ..database import get_db, SessionLocal
from ..models import (Employee, MonitoringLog, ActivityEvent, Alert, Attendance, Department, User, Prediction,
                      ROLE_ADMIN, ROLE_HR, ROLE_MANAGER)
from ..schemas import ActivityIn
from ..security import staff, hr_admin, user_from_token
from ..services import risk
from ..services.common import (audit, emit_activity, employee_scope_filter, ensure_employee_access, latest_predictions,
                               notify, user_ids_by_role)
from ..ws import manager
from .predictions import pred_dict

router = APIRouter(tags=["Risk Monitoring & Live Workforce"])


# ---------------- activity ingestion -> risk recalculation ----------------
def apply_activity(db: Session, emp: Employee, ev: ActivityIn) -> str:
    v, t = ev.value, ev.event_type
    if t == "overtime_spike":
        hrs = v if v is not None else 3.0
        emp.overtime = True
        att = db.scalar(select(Attendance).where(Attendance.employee_id == emp.id, Attendance.work_date == date.today())) or \
            Attendance(employee_id=emp.id, work_date=date.today(), status="present")
        att.overtime_hours = max(att.overtime_hours or 0, hrs)
        att.working_hours = max(att.working_hours or 0, 8 + hrs)
        db.add(att)
        return f"logged {hrs}h overtime"
    if t == "late_arrival":
        att = db.scalar(select(Attendance).where(Attendance.employee_id == emp.id, Attendance.work_date == date.today())) or \
            Attendance(employee_id=emp.id, work_date=date.today())
        att.status = "late"
        db.add(att)
        return "marked late today"
    if t == "unplanned_absence":
        att = db.scalar(select(Attendance).where(Attendance.employee_id == emp.id, Attendance.work_date == date.today())) or \
            Attendance(employee_id=emp.id, work_date=date.today())
        att.status, att.working_hours, att.overtime_hours = "absent", 0, 0
        db.add(att)
        return "marked absent today"
    if t == "satisfaction_drop":
        d = int(v or 1)
        emp.job_satisfaction = max(1, emp.job_satisfaction - d)
        emp.work_life_balance = max(1, emp.work_life_balance - (1 if d >= 2 else 0))
        return f"job satisfaction -> {emp.job_satisfaction}"
    if t == "promotion_denied":
        emp.years_since_promotion = round(emp.years_since_promotion + (v or 1), 1)
        return f"years since promotion -> {emp.years_since_promotion}"
    if t == "salary_change":
        pct = v or 0
        emp.monthly_salary = round(emp.monthly_salary * (1 + pct / 100), 2)
        return f"salary changed {pct:+.1f}% -> {emp.monthly_salary:,.0f}"
    if t == "training_completed":
        emp.training_times_last_year += 1
        emp.job_satisfaction = min(4, emp.job_satisfaction + 1)
        return "training completed; satisfaction +1"
    if t == "manager_change":
        emp.environment_satisfaction = max(1, emp.environment_satisfaction - 1)
        return "manager changed; environment satisfaction -1"
    return ev.note or "custom activity"


@router.post("/monitoring/activity")
def ingest_activity(body: ActivityIn, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    """Employee activity changes -> prediction recalculated -> alert/intervention/log -> live feed."""
    emp = db.get(Employee, body.employee_id)
    if not emp or emp.status == "terminated":
        raise HTTPException(404, "Active employee not found")
    ensure_employee_access(db, user, emp.id)
    before = latest_predictions(db, [emp.id]).get(emp.id)
    n_alerts_before = db.scalar(select(func.count()).select_from(Alert))
    effect = apply_activity(db, emp, body)
    emit_activity(db, emp.id, body.event_type, f"{emp.full_name}: {body.event_type.replace('_', ' ')} – {effect}",
                  "warning" if body.event_type in ("overtime_spike", "satisfaction_drop", "unplanned_absence", "promotion_denied") else "info")
    db.commit()
    audit(db, user, "ACTIVITY", "employee", emp.id, {"event": body.event_type, "effect": effect}, request)
    after = risk.recalc_one(db, emp, f"activity:{body.event_type}")
    if not after:
        raise HTTPException(409, "No active ML model; activity recorded but risk not recalculated")
    n_alerts_after = db.scalar(select(func.count()).select_from(Alert))
    return {"effect": effect, "before": {"score": before.risk_score, "level": before.risk_level} if before else None,
            "after": pred_dict(after, True), "alerts_created": n_alerts_after - n_alerts_before}


# ---------------- monitoring views ----------------
@router.get("/monitoring/high-risk")
def high_risk(department_id: Optional[int] = None, limit: int = Query(50, ge=1, le=200),
              db: Session = Depends(get_db), user: User = Depends(staff)):
    sub = select(func.max(Prediction.id)).group_by(Prediction.employee_id).scalar_subquery()
    q = (select(Prediction).join(Employee, Employee.id == Prediction.employee_id)
         .where(Prediction.id.in_(sub), Prediction.risk_level == "high", Employee.status != "terminated"))
    scope = employee_scope_filter(user)
    if scope is not None: q = q.where(scope)
    if department_id: q = q.where(Employee.department_id == department_id)
    rows = db.scalars(q.order_by(Prediction.risk_score.desc()).limit(limit)).unique().all()
    return [pred_dict(p, True) for p in rows]


@router.get("/monitoring/logs")
def logs(employee_id: Optional[int] = None, event: Optional[str] = None, page: int = Query(1, ge=1),
         size: int = Query(25, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(staff)):
    q = select(MonitoringLog)
    scope = employee_scope_filter(user)
    if scope is not None: q = q.where(MonitoringLog.employee_id.in_(select(Employee.id).where(scope)))
    if employee_id: q = q.where(MonitoringLog.employee_id == employee_id)
    if event: q = q.where(MonitoringLog.event == event)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(MonitoringLog.id.desc()).offset((page - 1) * size).limit(size)).unique().all()
    items = [{"id": m.id, "employee_id": m.employee_id, "employee_name": m.employee.full_name if m.employee else None,
              "event": m.event, "old_score": m.old_score, "new_score": m.new_score, "old_level": m.old_level,
              "new_level": m.new_level, "delta": round(m.new_score - m.old_score, 4) if m.old_score is not None else None,
              "trigger": m.trigger, "created_at": m.created_at} for m in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/monitoring/risk-changes")
def risk_changes(days: int = Query(7, ge=1, le=90), db: Session = Depends(get_db), user: User = Depends(staff)):
    """Risk change tracking: biggest movers over the window (current vs earliest score in window)."""
    since = datetime.utcnow() - timedelta(days=days)
    q = select(MonitoringLog).where(MonitoringLog.created_at >= since, MonitoringLog.old_score.is_not(None))
    scope = employee_scope_filter(user)
    if scope is not None: q = q.where(MonitoringLog.employee_id.in_(select(Employee.id).where(scope)))
    movers: dict = {}
    for m in db.scalars(q.order_by(MonitoringLog.id)).unique():
        r = movers.setdefault(m.employee_id, {"employee_id": m.employee_id, "employee_name": m.employee.full_name,
                                              "start": m.old_score, "end": m.new_score, "events": 0})
        r["end"], r["events"] = m.new_score, r["events"] + 1
    out = [{**r, "delta": round(r["end"] - r["start"], 4)} for r in movers.values()]
    return {"up": sorted([o for o in out if o["delta"] > 0], key=lambda o: -o["delta"])[:10],
            "down": sorted([o for o in out if o["delta"] < 0], key=lambda o: o["delta"])[:10]}


@router.get("/monitoring/feed")
def feed(limit: int = Query(40, ge=1, le=200), since_id: Optional[int] = None, severity: Optional[str] = None,
         db: Session = Depends(get_db), user: User = Depends(staff)):
    q = select(ActivityEvent)
    scope = employee_scope_filter(user)
    if scope is not None: q = q.where(ActivityEvent.employee_id.in_(select(Employee.id).where(scope)))
    if since_id: q = q.where(ActivityEvent.id > since_id)
    if severity: q = q.where(ActivityEvent.severity == severity)
    rows = db.scalars(q.order_by(ActivityEvent.id.desc()).limit(limit)).unique().all()
    return [{"id": e.id, "employee_id": e.employee_id, "employee_name": e.employee.full_name if e.employee else None,
             "event_type": e.event_type, "description": e.description, "severity": e.severity, "created_at": e.created_at} for e in rows]


def detect_instability(db: Session) -> list[dict]:
    """Workforce instability signals per department (last 7d vs previous 21d)."""
    today = date.today()
    w1, w0 = today - timedelta(days=7), today - timedelta(days=28)
    depts = {d.id: d.name for d in db.scalars(select(Department))}
    size = dict(db.execute(select(Employee.department_id, func.count()).where(Employee.status != "terminated").group_by(Employee.department_id)).all())

    def rates(start, end):
        rows = db.execute(select(Employee.department_id,
                                 func.sum(case((Attendance.status == "late", 1), else_=0)),
                                 func.sum(case((Attendance.status == "absent", 1), else_=0)),
                                 func.avg(Attendance.overtime_hours), func.count())
                          .join(Employee, Employee.id == Attendance.employee_id)
                          .where(Attendance.work_date >= start, Attendance.work_date < end).group_by(Employee.department_id)).all()
        return {d: (int(l or 0) / max(n, 1), int(a or 0) / max(n, 1), float(o or 0)) for d, l, a, o, n in rows}
    recent, base = rates(w1, today + timedelta(days=1)), rates(w0, w1)
    since = datetime.utcnow() - timedelta(days=7)
    entered = dict(db.execute(select(Employee.department_id, func.count()).join(MonitoringLog, MonitoringLog.employee_id == Employee.id)
                              .where(MonitoringLog.event == "entered_high_risk", MonitoringLog.created_at >= since)
                              .group_by(Employee.department_id)).all())
    out = []
    for did, name in depts.items():
        sig = []
        r, b = recent.get(did), base.get(did)
        if r and b:
            if r[0] > max(b[0] * 1.5, 0.08): sig.append(f"Late-arrival rate up {r[0]:.0%} vs {b[0]:.0%} baseline")
            if r[1] > max(b[1] * 1.5, 0.05): sig.append(f"Absence rate up {r[1]:.0%} vs {b[1]:.0%} baseline")
            if r[2] > max(b[2] * 1.4, 0.8): sig.append(f"Average overtime {r[2]:.1f}h/day vs {b[2]:.1f}h baseline")
        n_high = entered.get(did, 0)
        if n_high >= 2 or (n_high >= 1 and size.get(did, 1) <= 6):
            sig.append(f"{n_high} employee(s) entered high risk in the last 7 days")
        if sig:
            out.append({"department_id": did, "department": name, "signals": sig,
                        "severity": "critical" if len(sig) >= 3 else "high" if len(sig) == 2 else "medium"})
    return sorted(out, key=lambda x: -len(x["signals"]))


@router.get("/monitoring/instability")
def instability(db: Session = Depends(get_db), _: User = Depends(staff)):
    return detect_instability(db)


@router.post("/monitoring/instability/scan")
def instability_scan(db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    """Runs detection and raises alerts (idempotent per department per day)."""
    found = detect_instability(db)
    created = 0
    start = datetime.combine(date.today(), datetime.min.time())
    for f in found:
        marker = f"[{f['department']}]"
        if db.scalar(select(Alert.id).where(Alert.alert_type == "instability", Alert.message.like(f"{marker}%"), Alert.created_at >= start)):
            continue
        msg = f"{marker} Workforce instability: " + "; ".join(f["signals"])
        db.add(Alert(alert_type="instability", severity=f["severity"], message=msg[:500]))
        notify(db, user_ids_by_role(db, ROLE_ADMIN, ROLE_HR), "Workforce instability detected", msg[:300], "risk", f["severity"], "/live")
        emit_activity(db, None, "instability", msg[:290], "critical" if f["severity"] == "critical" else "warning")
        created += 1
    db.commit()
    return {"departments_flagged": len(found), "alerts_created": created}


# ---------------- WebSocket: notifications, chat, live feed, risk updates ----------------
@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str = Query(...)):
    import asyncio
    manager.loop = asyncio.get_running_loop()
    db = SessionLocal()
    try:
        user = user_from_token(db, token)
    except Exception:
        db.close()
        await ws.close(code=4401)
        return
    uid, role = user.id, user.role
    db.close()
    await manager.connect(ws, uid, role)
    try:
        await ws.send_json({"type": "connected", "data": {"user_id": uid}})
        while True:
            msg = await ws.receive_text()  # heartbeat / typing indicators
            if msg == "ping":
                await ws.send_json({"type": "pong"})
            elif msg.startswith("typing:"):
                try:
                    await manager.send_to_user(int(msg.split(":")[1]), {"type": "typing", "data": {"user_id": uid}})
                except ValueError:
                    pass
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws, uid)
