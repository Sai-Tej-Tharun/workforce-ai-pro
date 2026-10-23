"""Modules 11 & 12 (part): dataset upload/versioning/validation and model training."""
import io, uuid
from pathlib import Path
from typing import Optional
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Dataset, MLModel, User
from ..security import hr_admin, staff
from ..services import ml, risk
from ..services.common import audit

router = APIRouter(tags=["Datasets & Models"])
DATASET_DIR = settings.UPLOAD_DIR / "datasets"
DATASET_DIR.mkdir(parents=True, exist_ok=True)


def _ds(d: Dataset) -> dict:
    return {"id": d.id, "name": d.name, "version": d.version, "filename": d.filename, "rows_total": d.rows_total,
            "rows_valid": d.rows_valid, "rows_failed": d.rows_failed, "rows_duplicate": d.rows_duplicate,
            "attrition_rate": d.attrition_rate, "status": d.status, "created_at": d.created_at,
            "failed_preview": (d.failed_report or [])[:10]}


def _model(m: MLModel) -> dict:
    return {"id": m.id, "dataset_id": m.dataset_id, "algorithm": m.algorithm, "accuracy": m.accuracy,
            "precision": m.precision_score, "recall": m.recall, "f1": m.f1, "roc_auc": m.roc_auc, "cv_roc_auc": m.cv_roc_auc,
            "train_rows": m.train_rows, "feature_importance": m.feature_importance, "comparison": m.comparison,
            "confusion": m.confusion, "is_active": m.is_active, "created_at": m.created_at}


def register_dataset(db: Session, df_raw: pd.DataFrame, name: str, filename: str, user_id: Optional[int]) -> Dataset:
    res = ml.validate_dataset(df_raw)
    if res["missing_columns"]:
        raise HTTPException(422, {"message": "Missing required columns", "missing": res["missing_columns"],
                                  "required": ml.REQUIRED})
    clean = res["clean"]
    if clean is None or len(clean) == 0:
        raise HTTPException(422, {"message": "No valid rows in dataset", "failed_preview": res["failed"][:20]})
    version = (db.scalar(select(func.max(Dataset.version)).where(Dataset.name == name)) or 0) + 1
    path = DATASET_DIR / f"{uuid.uuid4().hex}_clean.csv"
    clean.to_csv(path, index=False)
    ds = Dataset(name=name, version=version, filename=filename, stored_path=str(path), rows_total=res["total"],
                 rows_valid=len(clean), rows_failed=len([f for f in res["failed"] if f["reason"] != "duplicate record"]),
                 rows_duplicate=res["duplicates"], attrition_rate=round(float(clean["attrition"].mean()), 4),
                 failed_report=res["failed"], uploaded_by=user_id)
    db.add(ds)
    db.commit()
    return ds


@router.post("/datasets/upload", status_code=201)
async def upload_dataset(request: Request, file: UploadFile = File(...), name: Optional[str] = Form(None),
                         db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    fn = Path(file.filename or "dataset.csv").name
    ext = Path(fn).suffix.lower()
    if ext not in (".csv", ".xlsx"):
        raise HTTPException(415, "Only .csv and .xlsx datasets are supported")
    data = await file.read(settings.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"Dataset exceeds {settings.MAX_UPLOAD_MB} MB")
    try:
        df = pd.read_csv(io.BytesIO(data)) if ext == ".csv" else pd.read_excel(io.BytesIO(data))
    except Exception as e:
        raise HTTPException(422, f"Could not parse file: {e}")
    if df.empty:
        raise HTTPException(422, "Dataset is empty")
    ds = register_dataset(db, df, (name or Path(fn).stem)[:120], fn, user.id)
    audit(db, user, "UPLOAD", "dataset", ds.id, {"rows": ds.rows_total, "failed": ds.rows_failed}, request)
    return _ds(ds)


@router.get("/datasets/template")
def template(_: User = Depends(staff)):
    cols = ["employee_number", "age", "monthly_income", "job_satisfaction", "years_at_company", "overtime", "attrition",
            "distance_from_home", "job_level", "environment_satisfaction", "work_life_balance", "years_since_promotion",
            "total_working_years", "num_companies_worked", "training_times_last_year", "performance_rating",
            "stock_option_level", "education", "marital_status", "department", "late_days_90", "unplanned_leave_days_90", "avg_overtime_hours"]
    row = [1, 34, 5200, 3, 4, "Yes", "No", 8, 2, 3, 3, 1, 10, 2, 2, 3, 0, 3, "Single", "Engineering", 2, 1, 0.5]
    buf = io.StringIO()
    pd.DataFrame([row], columns=cols).to_csv(buf, index=False)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="dataset_template.csv"'})


@router.get("/datasets")
def list_datasets(db: Session = Depends(get_db), _: User = Depends(hr_admin)):
    return [_ds(d) for d in db.scalars(select(Dataset).order_by(Dataset.created_at.desc(), Dataset.id.desc()))]


@router.get("/datasets/{did}")
def get_dataset(did: int, db: Session = Depends(get_db), _: User = Depends(hr_admin)):
    d = db.get(Dataset, did)
    if not d:
        raise HTTPException(404, "Dataset not found")
    return {**_ds(d), "failed_report": d.failed_report or []}


@router.get("/datasets/{did}/failed-report")
def failed_report(did: int, db: Session = Depends(get_db), _: User = Depends(hr_admin)):
    d = db.get(Dataset, did)
    if not d:
        raise HTTPException(404, "Dataset not found")
    buf = io.StringIO()
    pd.DataFrame(d.failed_report or [], columns=["row", "reason"]).to_csv(buf, index=False)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="failed_records_{d.name}_v{d.version}.csv"'})


@router.delete("/datasets/{did}", status_code=204)
def delete_dataset(did: int, request: Request, db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    d = db.get(Dataset, did)
    if not d:
        raise HTTPException(404, "Dataset not found")
    Path(d.stored_path).unlink(missing_ok=True)
    db.delete(d)
    db.commit()
    audit(db, user, "DELETE", "dataset", did, request=request)


def train_and_register(db: Session, d: Dataset, user_id: Optional[int], activate: bool = True) -> tuple[MLModel, dict]:
    df = pd.read_csv(d.stored_path)
    path = settings.MODEL_DIR / f"model_{uuid.uuid4().hex[:10]}.joblib"
    m = ml.train(df, path)
    rec = MLModel(dataset_id=d.id, algorithm=m["algorithm"], accuracy=m["accuracy"], precision_score=m["precision"],
                  recall=m["recall"], f1=m["f1"], roc_auc=m["roc_auc"], cv_roc_auc=m["cv_roc_auc"], train_rows=m["train_rows"],
                  feature_importance=m["feature_importance"], comparison=m["comparison"], confusion=m["confusion"],
                  artifact_path=str(path), is_active=False, trained_by=user_id)
    db.add(rec)
    db.flush()
    if activate:
        for old in db.scalars(select(MLModel).where(MLModel.is_active == True)):  # noqa: E712
            old.is_active = False
        rec.is_active = True
    db.commit()
    ml.clear_cache()
    return rec, m


@router.post("/datasets/{did}/train")
def train_on_dataset(did: int, request: Request, activate: bool = True, db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    d = db.get(Dataset, did)
    if not d:
        raise HTTPException(404, "Dataset not found")
    try:
        rec, m = train_and_register(db, d, user.id, activate)
    except ValueError as e:
        raise HTTPException(422, str(e))
    audit(db, user, "TRAIN", "ml_model", rec.id, {"dataset": d.id, "auc": m["roc_auc"]}, request)
    return {**_model(rec), "majority_baseline_accuracy": m["majority_baseline_accuracy"], "threshold": m["threshold"],
            "test_rows": m["test_rows"]}


@router.get("/models")
def list_models(db: Session = Depends(get_db), _: User = Depends(staff)):
    return [_model(m) for m in db.scalars(select(MLModel).order_by(MLModel.id.desc()))]


@router.get("/models/active")
def active_model(db: Session = Depends(get_db), _: User = Depends(staff)):
    m = risk.get_active_model(db)
    if not m:
        raise HTTPException(404, "No active model. Upload a dataset and train one.")
    return _model(m)


@router.post("/models/{mid}/activate")
def activate_model(mid: int, request: Request, db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    m = db.get(MLModel, mid)
    if not m:
        raise HTTPException(404, "Model not found")
    for old in db.scalars(select(MLModel).where(MLModel.is_active == True)):  # noqa: E712
        old.is_active = False
    m.is_active = True
    db.commit()
    audit(db, user, "ACTIVATE", "ml_model", mid, request=request)
    return _model(m)
