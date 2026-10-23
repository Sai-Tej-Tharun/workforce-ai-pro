"""Dataset validation + ML training + prediction + explanations (Modules 11, 12)."""
from __future__ import annotations
import re
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score,
                             roc_auc_score, confusion_matrix)
from sklearn.model_selection import train_test_split, cross_val_score, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERIC = ["age", "monthly_income", "distance_from_home", "job_level", "job_satisfaction",
           "environment_satisfaction", "work_life_balance", "years_at_company", "years_since_promotion",
           "total_working_years", "num_companies_worked", "training_times_last_year", "performance_rating",
           "stock_option_level", "education", "overtime", "late_days_90", "unplanned_leave_days_90",
           "avg_overtime_hours"]
CATEGORICAL = ["marital_status", "department"]
FEATURES = NUMERIC + CATEGORICAL
REQUIRED = ["attrition", "age", "monthly_income", "job_satisfaction", "years_at_company", "overtime"]

DEFAULTS = {"distance_from_home": 8, "job_level": 2, "environment_satisfaction": 3, "work_life_balance": 3,
            "years_since_promotion": 1, "total_working_years": 8, "num_companies_worked": 2,
            "training_times_last_year": 2, "performance_rating": 3, "stock_option_level": 0, "education": 3,
            "late_days_90": 0, "unplanned_leave_days_90": 0, "avg_overtime_hours": 0,
            "marital_status": "Single", "department": "Unknown"}
RANGES = {"age": (16, 75), "monthly_income": (1, 1_000_000), "distance_from_home": (0, 500),
          "job_level": (1, 5), "job_satisfaction": (1, 4), "environment_satisfaction": (1, 4),
          "work_life_balance": (1, 4), "years_at_company": (0, 60), "years_since_promotion": (0, 60),
          "total_working_years": (0, 60), "num_companies_worked": (0, 30), "training_times_last_year": (0, 30),
          "performance_rating": (1, 4), "stock_option_level": (0, 3), "education": (1, 5),
          "late_days_90": (0, 90), "unplanned_leave_days_90": (0, 90), "avg_overtime_hours": (0, 24)}

ALIASES = {
    "monthlyincome": "monthly_income", "monthlysalary": "monthly_income", "income": "monthly_income",
    "distancefromhome": "distance_from_home", "joblevel": "job_level", "jobsatisfaction": "job_satisfaction",
    "environmentsatisfaction": "environment_satisfaction", "worklifebalance": "work_life_balance",
    "yearsatcompany": "years_at_company", "yearssincelastpromotion": "years_since_promotion",
    "yearssincepromotion": "years_since_promotion", "totalworkingyears": "total_working_years",
    "numcompaniesworked": "num_companies_worked", "trainingtimeslastyear": "training_times_last_year",
    "performancerating": "performance_rating", "stockoptionlevel": "stock_option_level",
    "maritalstatus": "marital_status", "employeenumber": "employee_number", "employeeid": "employee_number",
    "employeecode": "employee_number", "left": "attrition", "turnover": "attrition",
    "latedays90": "late_days_90", "unplannedleavedays90": "unplanned_leave_days_90",
    "avgovertimehours": "avg_overtime_hours",
}
LABELS = {"age": "Age", "monthly_income": "Monthly income", "distance_from_home": "Commute distance",
          "job_level": "Job level", "job_satisfaction": "Job satisfaction",
          "environment_satisfaction": "Environment satisfaction", "work_life_balance": "Work-life balance",
          "years_at_company": "Tenure", "years_since_promotion": "Years since promotion",
          "total_working_years": "Total experience", "num_companies_worked": "Past employers",
          "training_times_last_year": "Training last year", "performance_rating": "Performance rating",
          "stock_option_level": "Stock options", "education": "Education", "overtime": "Overtime",
          "late_days_90": "Late arrivals (90d)", "unplanned_leave_days_90": "Unplanned absences (90d)",
          "avg_overtime_hours": "Avg overtime hrs/day", "marital_status": "Marital status",
          "department": "Department"}
_TRUE = {"yes", "y", "true", "1", "1.0"}
_FALSE = {"no", "n", "false", "0", "0.0"}


def _canon(col: str) -> str:
    key = re.sub(r"[^a-z0-9]", "", str(col).lower())
    if key in ALIASES:
        return ALIASES[key]
    snake = re.sub(r"[^a-z0-9]+", "_", str(col).strip().lower()).strip("_")
    return snake


def _to_bool(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip().str.lower()
    out = pd.Series(np.nan, index=series.index, dtype="float64")
    out[s.isin(_TRUE)] = 1.0
    out[s.isin(_FALSE)] = 0.0
    return out


# =====================  Dataset validation  =====================
def validate_dataset(raw: pd.DataFrame) -> dict:
    """Returns {clean, failed:[{row,reason}], duplicates, total, missing_columns}."""
    df = raw.reset_index(drop=True).copy()
    df.columns = [_canon(c) for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]
    total = len(df)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        return {"clean": None, "failed": [], "duplicates": 0, "total": total, "missing_columns": missing}

    reasons: dict[int, str] = {}

    def fail(mask: pd.Series, msg: str):
        for idx in df.index[mask.fillna(False)]:
            reasons.setdefault(int(idx), msg)

    for col in ("attrition", "overtime"):
        parsed = _to_bool(df[col])
        fail(parsed.isna(), f"invalid {col} value (expected Yes/No)")
        df[col] = parsed
    for col in NUMERIC:
        if col == "overtime":
            continue
        if col not in df.columns:
            df[col] = DEFAULTS[col]
            continue
        raw_col = df[col]
        num = pd.to_numeric(raw_col, errors="coerce")
        blank = raw_col.isna() | (raw_col.astype(str).str.strip() == "")
        if col in REQUIRED:
            fail(num.isna(), f"missing or non-numeric {col}")
        else:
            fail(num.isna() & ~blank, f"non-numeric {col}")
            num = num.fillna(DEFAULTS[col])
        lo, hi = RANGES[col]
        fail(num.notna() & ((num < lo) | (num > hi)), f"{col} out of range [{lo}, {hi}]")
        df[col] = num
    for col in CATEGORICAL:
        if col not in df.columns:
            df[col] = DEFAULTS[col]
        df[col] = df[col].fillna(DEFAULTS[col]).astype(str).str.strip().replace("", DEFAULTS[col])

    bad = set(reasons)
    good = df.loc[[i for i in df.index if int(i) not in bad]].copy()
    # duplicate validation: by employee_number if present, otherwise on the full feature row
    subset = ["employee_number"] if "employee_number" in good.columns else None
    dup_mask = good.duplicated(subset=subset, keep="first") if subset else good.duplicated(keep="first")
    dups = int(dup_mask.sum())
    dup_rows = [int(i) + 2 for i in good.index[dup_mask]]
    good = good.loc[~dup_mask]
    failed = [{"row": i + 2, "reason": r} for i, r in sorted(reasons.items())]
    failed += [{"row": r, "reason": "duplicate record"} for r in dup_rows]
    return {"clean": good, "failed": failed[:1000], "duplicates": dups, "total": total, "missing_columns": []}


# =====================  Training  =====================
def _preprocessor() -> ColumnTransformer:
    return ColumnTransformer([
        ("num", StandardScaler(), NUMERIC),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
    ])


def _candidates(seed: int) -> dict:
    return {
        "LogisticRegression": LogisticRegression(max_iter=3000, C=1.0),
        "RandomForest": RandomForestClassifier(n_estimators=300, min_samples_leaf=5, n_jobs=-1, random_state=seed),
        "GradientBoosting": GradientBoostingClassifier(n_estimators=250, max_depth=3, learning_rate=0.05,
                                                       subsample=0.9, random_state=seed),
    }


def train(df: pd.DataFrame, out_path: Path, seed: int = 42) -> dict:
    X, y = df[FEATURES], df["attrition"].astype(int)
    if y.nunique() < 2 or len(df) < 100 or y.value_counts().min() < 10:
        raise ValueError("Dataset needs at least 100 rows with at least 10 examples of each outcome")
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, stratify=y, random_state=seed)
    comparison, best = [], None
    for name, est in _candidates(seed).items():
        pipe = Pipeline([("prep", _preprocessor()), ("clf", est)])
        cv = float(cross_val_score(pipe, Xtr, ytr, cv=4, scoring="roc_auc", n_jobs=1).mean())
        comparison.append({"algorithm": name, "cv_roc_auc": round(cv, 4)})
        if best is None or cv > best[1]:
            best = (name, cv, pipe)
    name, cv_auc, pipe = best
    # decision threshold = best-F1 threshold on out-of-fold training predictions
    oof = cross_val_predict(pipe, Xtr, ytr, cv=4, method="predict_proba")[:, 1]
    grid = np.linspace(0.1, 0.7, 61)
    thr = float(grid[int(np.argmax([f1_score(ytr, oof >= t) for t in grid]))])
    pipe.fit(Xtr, ytr)
    proba = pipe.predict_proba(Xte)[:, 1]
    pred = (proba >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(yte, pred, labels=[0, 1]).ravel()
    imp = permutation_importance(pipe, Xte, yte, scoring="roc_auc", n_repeats=5, random_state=seed, n_jobs=1)
    importance = {f: round(float(max(v, 0)), 5) for f, v in zip(FEATURES, imp.importances_mean)}
    importance = dict(sorted(importance.items(), key=lambda kv: -kv[1]))
    metrics = {
        "algorithm": name,
        "accuracy": round(float(accuracy_score(yte, pred)), 4),
        "precision": round(float(precision_score(yte, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(yte, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(yte, pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(yte, proba)), 4),
        "cv_roc_auc": round(cv_auc, 4),
        "majority_baseline_accuracy": round(float(1 - yte.mean()), 4),
        "threshold": round(thr, 3),
        "train_rows": int(len(Xtr)), "test_rows": int(len(Xte)),
        "confusion": [[int(tn), int(fp)], [int(fn), int(tp)]],
        "feature_importance": importance,
        "comparison": comparison,
    }
    # refit on all data for the production artifact
    pipe.fit(X, y)
    reference = {c: float(X[c].median()) for c in NUMERIC}
    reference.update({c: X[c].mode().iloc[0] for c in CATEGORICAL})
    joblib.dump({"pipeline": pipe, "reference": reference, "threshold": thr, "metrics": metrics}, out_path)
    return metrics


# =====================  Prediction  =====================
class Predictor:
    def __init__(self, artifact_path: str):
        art = joblib.load(artifact_path)
        self.pipe: Pipeline = art["pipeline"]
        self.reference: dict = art["reference"]
        self.threshold: float = art["threshold"]

    def predict(self, X: pd.DataFrame, explain: bool = True, top_k: int = 4) -> list[dict]:
        X = X[FEATURES].copy()
        p = self.pipe.predict_proba(X)[:, 1]
        contrib = {}
        if explain:
            for f in FEATURES:  # counterfactual: replace feature by population reference value
                Xm = X.copy()
                Xm[f] = self.reference[f]
                contrib[f] = p - self.pipe.predict_proba(Xm)[:, 1]
        out = []
        for i in range(len(X)):
            score = float(p[i])
            factors = []
            if explain:
                ranked = sorted(FEATURES, key=lambda f: -contrib[f][i])
                for f in ranked[:top_k]:
                    if contrib[f][i] > 0.005:
                        v = X.iloc[i][f]
                        factors.append({"feature": f, "label": LABELS[f],
                                        "value": float(v) if f in NUMERIC else str(v),
                                        "impact": round(float(contrib[f][i]) * 100, 1)})
            out.append({"score": score, "confidence": float(max(score, 1 - score)), "factors": factors})
        return out


_cache: dict[str, Predictor] = {}


def get_predictor(path: str) -> Predictor:
    if path not in _cache:
        _cache[path] = Predictor(path)
    return _cache[path]


def clear_cache():
    _cache.clear()
