import io
import numpy as np
import pandas as pd
import pytest
from app.services import ml
from ml.synthetic import generate


# ---------------- model quality ----------------
def test_model_beats_baseline_on_holdout(tmp_path):
    from sklearn.metrics import roc_auc_score, accuracy_score
    train_df = ml.validate_dataset(generate(2500, seed=1))["clean"]
    test_df = ml.validate_dataset(generate(1200, seed=99))["clean"]  # unseen, different seed
    metrics = ml.train(train_df, tmp_path / "m.joblib")
    pr = ml.Predictor(str(tmp_path / "m.joblib"))
    scores = np.array([r["score"] for r in pr.predict(test_df, explain=False)])
    y = test_df["attrition"].astype(int).values
    auc = roc_auc_score(y, scores)
    acc = accuracy_score(y, scores >= pr.threshold)
    assert auc >= 0.80, f"AUC {auc:.3f}"
    assert acc > 1 - y.mean(), "must beat majority-class accuracy"
    assert metrics["roc_auc"] >= 0.80
    assert 0 <= scores.min() and scores.max() <= 1


def test_explanations_are_directionally_sensible(tmp_path):
    df = ml.validate_dataset(generate(2500, seed=3))["clean"]
    ml.train(df, tmp_path / "m.joblib")
    pr = ml.Predictor(str(tmp_path / "m.joblib"))
    base = df.drop(columns=["attrition", "employee_number"]).iloc[[0]].copy()
    happy = base.copy(); happy.loc[:, ["overtime", "unplanned_leave_days_90", "late_days_90", "avg_overtime_hours"]] = [0, 0, 0, 0]; happy.loc[:, "job_satisfaction"] = 4
    unhappy = base.copy(); unhappy.loc[:, ["overtime", "unplanned_leave_days_90", "late_days_90", "avg_overtime_hours"]] = [1, 8, 12, 3]; unhappy.loc[:, "job_satisfaction"] = 1
    assert pr.predict(unhappy, False)[0]["score"] > pr.predict(happy, False)[0]["score"] + 0.2
    top = [f["feature"] for f in pr.predict(unhappy)[0]["factors"]]
    assert {"job_satisfaction", "overtime", "unplanned_leave_days_90", "late_days_90", "avg_overtime_hours"} & set(top)


# ---------------- dataset validation ----------------
def test_validation_reports_failures_and_duplicates():
    df = generate(300, seed=5)
    df.loc[3, "age"] = 5                    # out of range
    df["monthly_income"] = df["monthly_income"].astype(object); df.loc[7, "monthly_income"] = "abc"     # non numeric
    df.loc[9, "attrition"] = "maybe"        # bad label
    df = pd.concat([df, df.iloc[[20]]])     # exact duplicate
    res = ml.validate_dataset(df)
    assert res["total"] == 301 and res["duplicates"] == 1
    reasons = {f["row"]: f["reason"] for f in res["failed"]}
    assert "age" in reasons[5] and "monthly_income" in reasons[9] and "attrition" in reasons[11]
    assert len(res["clean"]) == 301 - 3 - 1


def test_validation_missing_required_and_ibm_aliases():
    assert ml.validate_dataset(pd.DataFrame({"age": [30]}))["missing_columns"]
    ibm = pd.DataFrame({"Age": [30, 40], "MonthlyIncome": [5000, 7000], "JobSatisfaction": [2, 4], "YearsAtCompany": [3, 8],
                        "OverTime": ["Yes", "No"], "Attrition": ["Yes", "No"], "EmployeeNumber": [1, 2], "MaritalStatus": ["Single", "Married"]})
    res = ml.validate_dataset(ibm)
    assert not res["missing_columns"] and len(res["clean"]) == 2


def _csv(df):
    return io.BytesIO(df.to_csv(index=False).encode())


def test_dataset_upload_versioning_and_train(client, H):
    df = generate(900, seed=21)
    df.loc[1, "age"] = 200
    r1 = client.post("/api/datasets/upload", headers=H["hr"], files={"file": ("d.csv", _csv(df), "text/csv")}, data={"name": "ver_test"})
    assert r1.status_code == 201, r1.text
    assert r1.json()["version"] == 1 and r1.json()["rows_failed"] == 1
    r2 = client.post("/api/datasets/upload", headers=H["hr"], files={"file": ("d.csv", _csv(df), "text/csv")}, data={"name": "ver_test"})
    assert r2.json()["version"] == 2
    rep = client.get(f"/api/datasets/{r1.json()['id']}/failed-report", headers=H["hr"])
    assert rep.status_code == 200 and "out of range" in rep.text
    bad = client.post("/api/datasets/upload", headers=H["hr"], files={"file": ("d.csv", _csv(pd.DataFrame({"x": [1]})), "text/csv")})
    assert bad.status_code == 422 and "missing" in str(bad.json()["detail"]).lower()
    assert client.post("/api/datasets/upload", headers=H["hr"], files={"file": ("d.txt", io.BytesIO(b"x"), "text/plain")}).status_code == 415
    tr = client.post(f"/api/datasets/{r2.json()['id']}/train", headers=H["hr"])
    assert tr.status_code == 200 and tr.json()["roc_auc"] > 0.75 and tr.json()["is_active"]
    assert client.get("/api/models/active", headers=H["manager"]).json()["id"] == tr.json()["id"]
    assert client.post("/api/datasets/%d/train" % 99999, headers=H["hr"]).status_code == 404


# ---------------- prediction APIs ----------------
def test_prediction_endpoints(client, H):
    lst = client.get("/api/ai/predictions/latest?size=5", headers=H["hr"]).json()
    assert lst["total"] > 0
    p = lst["items"][0]
    assert 0 <= p["risk_percentage"] <= 100 and 0 <= p["confidence_percentage"] <= 100
    assert p["risk_level"] in ("low", "medium", "high") and "top_factors" in p
    assert lst["items"][0]["risk_score"] >= lst["items"][-1]["risk_score"]  # sorted desc
    eid = p["employee_id"]
    one = client.post(f"/api/ai/predict/employee/{eid}", headers=H["hr"]).json()
    assert one["recommended_actions"] is not None
    hist = client.get(f"/api/ai/predictions/employee/{eid}", headers=H["hr"]).json()
    assert len(hist) >= 2 and hist[0]["id"] > hist[1]["id"]  # historical storage
    dep = client.get("/api/ai/predictions/departments", headers=H["hr"]).json()
    assert dep and {"avg_risk", "expected_leavers_12m", "high"} <= set(dep[0])
    assert client.post(f"/api/ai/predict/employee/{eid}", headers=H["employee"]).status_code == 403


def test_what_if_reduces_risk(client, H):
    p = client.get("/api/ai/predictions/latest?risk_level=high&size=1", headers=H["hr"]).json()["items"][0]
    r = client.post("/api/ai/predict/what-if", headers=H["hr"], json={"employee_id": p["employee_id"], "overrides": {"overtime": False, "job_satisfaction": 4, "avg_overtime_hours": 0}})
    assert r.status_code == 200 and r.json()["after"] <= r.json()["before"]
    assert client.post("/api/ai/predict/what-if", headers=H["hr"], json={"employee_id": p["employee_id"], "overrides": {"nonsense": 1}}).status_code == 422


def test_batch_predict(client, H):
    r = client.post("/api/ai/predict/all", headers=H["hr"]).json()
    assert r["predicted"] > 30 and r["high"] + r["medium"] + r["low"] == r["predicted"]


# ---------------- the full expected flow ----------------
def test_end_to_end_activity_to_alert_flow(client, H, tokens):
    """activity -> recalculation -> high-risk -> alert -> intervention -> monitoring log -> notification -> dashboard."""
    from app.database import SessionLocal
    from app.models import Employee, Alert, Intervention, MonitoringLog, Prediction
    from sqlalchemy import select, func
    with SessionLocal() as db:
        from app.services.common import latest_predictions
        preds = latest_predictions(db)
        # pick an active, currently LOW-risk employee with room to deteriorate and no open intervention
        cands = [e for e in db.scalars(select(Employee).where(Employee.status == "active")).unique()
                 if e.id in preds and preds[e.id].risk_level == "low" and e.job_satisfaction >= 2]
        victim = max(cands, key=lambda e: preds[e.id].risk_score)
        vid = victim.id
        # make them fragile so the compound events push them over the threshold
        victim.overtime, victim.years_since_promotion, victim.work_life_balance, victim.job_satisfaction = False, 3, 2, 3
        db.commit()
    client.post(f"/api/ai/predict/employee/{vid}", headers=H["hr"])
    with client.websocket_connect(f"/api/ws?token={tokens['hr']}") as ws:
        assert ws.receive_json()["type"] == "connected"
        before = None
        crossed = False
        for ev in [{"event_type": "satisfaction_drop", "value": 2}, {"event_type": "overtime_spike", "value": 4},
                   {"event_type": "unplanned_absence"}, {"event_type": "promotion_denied", "value": 3},
                   {"event_type": "late_arrival"}, {"event_type": "salary_change", "value": -10}]:
            r = client.post("/api/monitoring/activity", headers=H["hr"], json={"employee_id": vid, **ev})
            assert r.status_code == 200, r.text
            body = r.json()
            before = before or body["before"]
            if body["after"]["risk_level"] == "high":
                crossed = True
                break
        assert crossed, f"employee never crossed to high; last={body['after']['risk_percentage']}%"
        assert body["after"]["risk_score"] > before["score"]
        assert body["alerts_created"] >= 1
        seen = set()
        for _ in range(60):  # drain live messages
            try:
                seen.add(ws.receive_json()["type"])
            except Exception:
                break
            if {"notification", "activity", "risk_update"} <= seen:
                break
        assert {"notification", "activity", "risk_update"} <= seen
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Alert).where(Alert.employee_id == vid, Alert.alert_type == "high_risk")) >= 1
        iv = db.scalar(select(Intervention).where(Intervention.employee_id == vid).order_by(Intervention.id.desc()))
        assert iv and iv.auto_generated and iv.status == "open" and "1." in iv.recommendation
        assert db.scalar(select(func.count()).select_from(MonitoringLog).where(MonitoringLog.employee_id == vid, MonitoringLog.event == "entered_high_risk")) == 1
    hi = client.get("/api/monitoring/high-risk", headers=H["hr"]).json()
    assert any(h["employee_id"] == vid for h in hi)
    feed = client.get("/api/monitoring/feed?limit=20", headers=H["hr"]).json()
    assert any(f["event_type"] == "risk_alert" for f in feed)
    ch = client.get("/api/monitoring/risk-changes?days=1", headers=H["hr"]).json()
    assert any(u["employee_id"] == vid for u in ch["up"])
    inbox = client.get("/api/notifications?category=risk", headers=H["hr"]).json()
    assert inbox["total"] >= 1
    # repeated activity must NOT spam duplicate high-risk alerts
    client.post("/api/monitoring/activity", headers=H["hr"], json={"employee_id": vid, "event_type": "late_arrival"})
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Alert).where(Alert.employee_id == vid, Alert.alert_type == "high_risk")) == 1
    # dashboard refreshed (cache cleared on recalculation)
    dash = client.get("/api/analytics/dashboard", headers=H["hr"]).json()
    assert dash["risk"]["distribution"]["high"] >= 1 and dash["open_alerts"] >= 1


def test_intervention_workflow(client, H):
    lst = client.get("/api/interventions?size=50", headers=H["hr"]).json()
    assert lst["total"] > 0
    iv = next(i for i in lst["items"] if i["status"] == "open")
    sg = client.get(f"/api/interventions/suggest/{iv['employee_id']}", headers=H["hr"]).json()
    assert sg["actions"]
    up = client.patch(f"/api/interventions/{iv['id']}", headers=H["hr"], json={"status": "completed", "outcome": "retained", "note": "Stay interview held"})
    assert up.status_code == 200 and up.json()["closed_at"] and len(up.json()["logs"]) >= 2
    st = client.get("/api/interventions/stats", headers=H["hr"]).json()
    assert st["completed"] >= 1 and st["retained"] >= 1
    new = client.post("/api/interventions", headers=H["manager"], json={"employee_id": iv["employee_id"], "title": "x", "recommendation": "y"})
    assert new.status_code in (201, 403)


def test_alert_priority_and_ack(client, H):
    al = client.get("/api/alerts?size=50", headers=H["hr"]).json()["items"]
    assert al
    open_ = [a for a in al if a["status"] != "resolved"]
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    assert [order[a["severity"]] for a in open_] == sorted(order[a["severity"]] for a in open_)
    assert client.patch(f"/api/alerts/{al[0]['id']}", headers=H["hr"], json={"status": "acknowledged"}).json()["status"] == "acknowledged"
    assert client.patch(f"/api/alerts/{al[0]['id']}", headers=H["hr"], json={"status": "bogus"}).status_code == 422


# ---------------- forecasting / analytics ----------------
def test_forecast_properties(client, H):
    f = client.get("/api/analytics/forecast?months=12&monthly_hires=0", headers=H["hr"]).json()
    hc = [m["headcount_no_hiring"] for m in f["months"]]
    assert all(a >= b for a, b in zip(hc, hc[1:])) and hc[0] <= f["current_headcount"]  # monotone decreasing
    assert abs(f["months"][-1]["cumulative_leavers"] - (f["current_headcount"] - hc[-1])) < 0.1
    assert [y["retention_rate"] for y in f["yearly"]] == sorted((y["retention_rate"] for y in f["yearly"]), reverse=True)
    hired = client.get("/api/analytics/forecast?months=12&monthly_hires=3", headers=H["hr"]).json()
    assert hired["months"][-1]["projected_headcount"] > f["months"][-1]["projected_headcount"] + 20
    d = client.get("/api/analytics/forecast?department_id=1", headers=H["hr"]).json()
    assert d["current_headcount"] < f["current_headcount"]


def test_stability_and_attrition_analytics(client, H):
    s = client.get("/api/analytics/stability", headers=H["hr"]).json()
    assert s["departments"] and all(0 <= d["stability_score"] <= 100 for d in s["departments"])
    a = client.get("/api/analytics/attrition", headers=H["hr"]).json()
    assert len(a["monthly_turnover"]) == 12 and a["stats"]["leavers_12m"] >= 1 and a["departments"] and a["tenure_analysis"]
    assert a["stats"]["predicted_attrition_rate"] is not None


def test_dashboards_per_role(client, H):
    hr = client.get("/api/analytics/dashboard", headers=H["hr"]).json()
    assert hr["employees"]["total"] > 30 and hr["payroll"]["trend"]
    mg = client.get("/api/analytics/dashboard", headers=H["manager"]).json()
    assert mg["employees"]["total"] < hr["employees"]["total"] and mg["payroll"]["monthly_cost"] is None
    em = client.get("/api/analytics/dashboard", headers=H["employee"]).json()
    assert em["scope"] == "EMPLOYEE" and "leave_balance" in em


def test_instability_scan(client, H):
    assert isinstance(client.get("/api/monitoring/instability", headers=H["hr"]).json(), list)
    r = client.post("/api/monitoring/instability/scan", headers=H["hr"])
    assert r.status_code == 200
    again = client.post("/api/monitoring/instability/scan", headers=H["hr"]).json()
    assert again["alerts_created"] == 0  # idempotent per day


def test_recommendations(client, H):
    assert client.get("/api/recommendations/workforce", headers=H["hr"]).json()
    assert client.get("/api/recommendations/department/1", headers=H["hr"]).json()["headcount"] > 0
    assert client.get("/api/recommendations/team", headers=H["manager"]).json()
    me = client.get("/api/auth/me", headers=H["employee"]).json()["employee_id"]
    mine = client.get(f"/api/recommendations/employee/{me}", headers=H["employee"]).json()
    assert mine["improvement_suggestions"] and "retention_actions" not in mine  # employees never see retention/risk info


def test_reports_export(client, H):
    for kind, ct in [("xlsx", "spreadsheetml"), ("pdf", "pdf"), ("csv", "csv")]:
        r = client.get(f"/api/reports/attrition?format={kind}", headers=H["hr"])
        assert r.status_code == 200 and ct in r.headers["content-type"]
    x = client.get("/api/reports/employees?format=xlsx", headers=H["hr"]).content
    assert x[:2] == b"PK"
    assert client.get("/api/reports/employees?format=pdf", headers=H["hr"]).content.startswith(b"%PDF")
    assert client.get("/api/reports/payroll?format=csv&month=1&year=2025", headers=H["hr"]).status_code == 200
    assert client.get("/api/reports/payroll", headers=H["manager"]).status_code == 403
    assert client.get("/api/reports/attendance?format=xlsx", headers=H["manager"]).status_code == 200
    assert client.get("/api/reports/leave?format=bad", headers=H["hr"]).status_code == 422
