"""Module 12: AI attrition prediction engine (risk %, confidence, department-level, history, what-if)."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Employee, Prediction, User, ROLE_EMPLOYEE
from ..security import hr_admin, staff
from ..services import risk, ml, recommend
from ..services.common import audit, ensure_employee_access, employee_scope_filter, latest_predictions
from ..services.features import build_features

router = APIRouter(prefix="/ai", tags=["AI Prediction Engine"])


def pred_dict(p: Prediction, include_actions: bool = False) -> dict:
    d = {"id": p.id, "employee_id": p.employee_id, "employee_name": p.employee.full_name if p.employee else None,
         "department": p.employee.department.name if p.employee and p.employee.department else None,
         "risk_score": p.risk_score, "risk_percentage": round(p.risk_score * 100, 1), "risk_level": p.risk_level,
         "confidence": p.confidence, "confidence_percentage": round(p.confidence * 100, 1),
         "top_factors": p.top_factors or [], "trigger": p.trigger, "created_at": p.created_at}
    if include_actions:
        d["recommended_actions"] = recommend.actions_from_factors(p.top_factors or [])
    return d


def _need_model(db):
    if not risk.get_active_model(db):
        raise HTTPException(409, "No active ML model. Upload a dataset and train one first (Datasets page).")


@router.post("/predict/employee/{emp_id}")
def predict_employee(emp_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    _need_model(db)
    emp = db.get(Employee, emp_id)
    if not emp:
        raise HTTPException(404, "Employee not found")
    ensure_employee_access(db, user, emp_id)
    if emp.status == "terminated":
        raise HTTPException(409, "Employee is terminated")
    p = risk.recalc_one(db, emp, "manual")
    return pred_dict(p, True)


@router.post("/predict/all")
def predict_all(request: Request, db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    _need_model(db)
    emps = db.scalars(select(Employee).where(Employee.status != "terminated")).unique().all()
    preds = risk.recalc(db, list(emps), "batch")
    audit(db, user, "BATCH_PREDICT", "prediction", None, {"employees": len(preds)}, request)
    return {"predicted": len(preds), "high": sum(p.risk_level == "high" for p in preds),
            "medium": sum(p.risk_level == "medium" for p in preds), "low": sum(p.risk_level == "low" for p in preds)}


@router.post("/predict/what-if")
def what_if(body: dict, db: Session = Depends(get_db), user: User = Depends(staff)):
    """Decision support: {employee_id, overrides:{overtime:false, monthly_income:7000, ...}} -> risk before/after (not saved)."""
    _need_model(db)
    emp = db.get(Employee, int(body.get("employee_id", 0)))
    if not emp:
        raise HTTPException(404, "Employee not found")
    ensure_employee_access(db, user, emp.id)
    X = build_features(db, [emp])
    over = body.get("overrides") or {}
    bad = [k for k in over if k not in ml.FEATURES]
    if bad:
        raise HTTPException(422, f"Unknown feature(s): {bad}. Allowed: {ml.FEATURES}")
    pr = ml.get_predictor(risk.get_active_model(db).artifact_path)
    before = pr.predict(X, explain=False)[0]["score"]
    X2 = X.copy()
    for k, v in over.items():
        X2.loc[:, k] = (1 if v is True else 0 if v is False else v)
    after = pr.predict(X2, explain=True)[0]
    return {"employee_id": emp.id, "before": round(before, 4), "after": round(after["score"], 4),
            "change_pct_points": round((after["score"] - before) * 100, 1), "level_after": risk.risk_level(after["score"]),
            "remaining_drivers": after["factors"]}


@router.get("/predictions/latest")
def latest(department_id: Optional[int] = None, risk_level: Optional[str] = Query(None, pattern="^(low|medium|high)$"),
           search: Optional[str] = None, sort: str = "risk_desc", page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=200),
           db: Session = Depends(get_db), user: User = Depends(staff)):
    sub = select(func.max(Prediction.id)).group_by(Prediction.employee_id).scalar_subquery()
    q = (select(Prediction).join(Employee, Employee.id == Prediction.employee_id)
         .where(Prediction.id.in_(sub), Employee.status != "terminated"))
    scope = employee_scope_filter(user)
    if scope is not None: q = q.where(scope)
    if department_id: q = q.where(Employee.department_id == department_id)
    if risk_level: q = q.where(Prediction.risk_level == risk_level)
    if search: q = q.where((Employee.first_name + " " + Employee.last_name).like(f"%{search}%"))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    q = q.order_by(Prediction.risk_score.asc() if sort == "risk_asc" else Prediction.risk_score.desc())
    rows = db.scalars(q.offset((page - 1) * size).limit(size)).unique().all()
    return {"items": [pred_dict(p, True) for p in rows], "total": total, "page": page, "size": size}


@router.get("/predictions/employee/{emp_id}")
def history(emp_id: int, limit: int = Query(30, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(staff)):
    ensure_employee_access(db, user, emp_id)
    rows = db.scalars(select(Prediction).where(Prediction.employee_id == emp_id).order_by(Prediction.id.desc()).limit(limit)).unique().all()
    return [pred_dict(p, i == 0) for i, p in enumerate(rows)]


@router.get("/predictions/departments")
def department_predictions(db: Session = Depends(get_db), user: User = Depends(staff)):
    """Department-level predictions: expected leavers (sum of probabilities) and risk distribution."""
    from ..models import Department
    scope = employee_scope_filter(user)
    q = select(Employee).where(Employee.status != "terminated")
    if scope is not None: q = q.where(scope)
    emps = db.scalars(q).unique().all()
    preds = latest_predictions(db, [e.id for e in emps])
    agg: dict = {}
    for e in emps:
        p = preds.get(e.id)
        if not p:
            continue
        a = agg.setdefault(e.department.name if e.department else "Unassigned", {"scores": [], "conf": [], "high": 0, "medium": 0, "low": 0})
        a["scores"].append(p.risk_score)
        a["conf"].append(p.confidence)
        a[p.risk_level] += 1
    out = [{"department": k, "headcount": len(v["scores"]), "avg_risk": round(sum(v["scores"]) / len(v["scores"]), 4),
            "expected_leavers_12m": round(sum(v["scores"]), 1), "high": v["high"], "medium": v["medium"], "low": v["low"],
            "avg_confidence": round(sum(v["conf"]) / len(v["conf"]), 4)} for k, v in agg.items()]
    return sorted(out, key=lambda r: -r["avg_risk"])
