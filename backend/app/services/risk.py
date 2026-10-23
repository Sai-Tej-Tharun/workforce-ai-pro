"""AI risk engine: recalculation -> detection -> alert -> intervention -> monitoring log -> live push.

Implements the expected flow from the project brief:
  employee activity changes -> prediction recalculated -> high-risk detected -> HR alert triggered ->
  intervention workflow initiated -> monitoring logs updated -> analytics dashboard refreshed.
"""
from datetime import date, timedelta
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import (Employee, Prediction, MLModel, MonitoringLog, Alert, Intervention, InterventionLog,
                      User, ROLE_ADMIN, ROLE_HR)
from ..ws import manager
from . import ml, recommend
from .common import notify, user_ids_by_role, latest_predictions, emit_activity, clear_cache
from .features import build_features


def risk_level(score: float) -> str:
    if score >= settings.HIGH_RISK_THRESHOLD:
        return "high"
    if score >= settings.MEDIUM_RISK_THRESHOLD:
        return "medium"
    return "low"


def get_active_model(db: Session) -> Optional[MLModel]:
    return db.scalar(select(MLModel).where(MLModel.is_active == True).order_by(MLModel.id.desc()))  # noqa: E712


def recalc(db: Session, employees: list[Employee], trigger: str = "manual", explain: bool = True,
           raise_alerts: bool = True) -> list[Prediction]:
    """Recalculate risk for the given employees. Returns the new Prediction rows (committed)."""
    employees = [e for e in employees if e.status != "terminated"]
    model = get_active_model(db)
    if not model or not employees:
        return []
    predictor = ml.get_predictor(model.artifact_path)
    X = build_features(db, employees)
    results = predictor.predict(X, explain=explain)
    prev = latest_predictions(db, [e.id for e in employees])
    high_ids = {a.employee_id for a in db.scalars(select(Alert).where(Alert.status != "resolved", Alert.alert_type == "high_risk"))}
    new_preds: list[Prediction] = []
    recipients = user_ids_by_role(db, ROLE_ADMIN, ROLE_HR) if raise_alerts else []

    for emp, res in zip(employees, results):
        score = res["score"]
        level = risk_level(score)
        p = Prediction(employee_id=emp.id, model_id=model.id, risk_score=round(score, 4), risk_level=level,
                       confidence=round(res["confidence"], 4), top_factors=res["factors"], trigger=trigger)
        db.add(p)
        db.flush()
        new_preds.append(p)
        old = prev.get(emp.id)
        old_score, old_level = (old.risk_score, old.risk_level) if old else (None, None)

        # --- monitoring log (Module 13: risk change tracking) ---
        changed = old is None or old_level != level or abs(score - old_score) >= 0.03
        if changed:
            if level == "high" and old_level != "high":
                event = "entered_high_risk"
            elif old_level == "high" and level != "high":
                event = "left_high_risk"
            elif old is None:
                event = "first_assessment"
            else:
                event = "risk_increased" if score > old_score else "risk_decreased"
            db.add(MonitoringLog(employee_id=emp.id, event=event, old_score=old_score, new_score=p.risk_score,
                                 old_level=old_level, new_level=level, trigger=trigger))

        if not raise_alerts:
            continue
        # --- alerts + interventions (Modules 13, 16, 17) ---
        newly_high = level == "high" and old_level != "high" and emp.id not in high_ids
        jump = old is not None and score - old_score >= 0.15 and level in ("medium", "high")
        if newly_high:
            sev = "critical" if score >= 0.8 else "high"
            msg = f"{emp.full_name} entered HIGH attrition risk ({score:.0%}). Top drivers: " + \
                  ", ".join(f["label"] for f in res["factors"][:3])
            alert = Alert(employee_id=emp.id, alert_type="high_risk", severity=sev, message=msg[:500])
            db.add(alert)
            targets = set(recipients)
            mgr_user = _manager_user(db, emp)
            if mgr_user:
                targets.add(mgr_user)
            notify(db, list(targets), "High attrition risk detected", msg, "risk", sev, "/risk-monitor")
            emit_activity(db, emp.id, "risk_alert", msg, "critical", {"score": score})
            if not _open_intervention(db, emp.id):
                title, body, prio = recommend.intervention_text(emp.full_name, score, res["factors"])
                iv = Intervention(employee_id=emp.id, prediction_id=p.id, title=title, recommendation=body,
                                  priority=prio, status="open", auto_generated=True,
                                  follow_up_date=date.today() + timedelta(days=7))
                db.add(iv)
                db.flush()
                db.add(InterventionLog(intervention_id=iv.id, action="auto_created",
                                       note=f"Triggered by risk {score:.0%} ({trigger})"))
        elif jump and level != "low":
            msg = f"{emp.full_name}: risk escalated {old_score:.0%} -> {score:.0%}"
            db.add(Alert(employee_id=emp.id, alert_type="risk_escalation", severity="medium", message=msg))
            notify(db, recipients, "Risk escalation", msg, "risk", "medium", "/risk-monitor")
            emit_activity(db, emp.id, "risk_escalation", msg, "warning", {"old": old_score, "new": score})
        elif old_level == "high" and level != "high":
            for a in db.scalars(select(Alert).where(Alert.employee_id == emp.id, Alert.status != "resolved",
                                                    Alert.alert_type == "high_risk")):
                a.status = "resolved"
                a.resolved_at = p.created_at
            emit_activity(db, emp.id, "risk_resolved", f"{emp.full_name} left the high-risk group ({score:.0%})", "info")

    db.commit()
    clear_cache()
    manager.publish_roles(("ADMIN", "HR", "MANAGER"), {"type": "risk_update", "data": {
        "employee_ids": [e.id for e in employees][:200], "count": len(employees), "trigger": trigger}})
    return new_preds


def recalc_one(db: Session, emp: Employee, trigger: str) -> Optional[Prediction]:
    r = recalc(db, [emp], trigger)
    return r[0] if r else None


def _open_intervention(db: Session, employee_id: int) -> bool:
    return db.scalar(select(Intervention.id).where(Intervention.employee_id == employee_id,
                                                   Intervention.status.in_(["open", "in_progress"])).limit(1)) is not None


def _manager_user(db: Session, emp: Employee) -> Optional[int]:
    if not emp.manager_id:
        return None
    return db.scalar(select(User.id).where(User.employee_id == emp.manager_id))
