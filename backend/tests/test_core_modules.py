from datetime import date, timedelta


def test_employee_crud_search_filter(client, H):
    r = client.post("/api/employees", headers=H["hr"], json={"first_name": "Test", "last_name": "Person", "email": "test.person@workforce.ai",
                                                              "department_id": 1, "monthly_salary": 5000, "age": 29})
    assert r.status_code == 201, r.text
    emp = r.json()
    assert emp["employee_code"].startswith("EMP") and emp["risk_score"] is not None  # risk auto-calculated on creation
    assert client.post("/api/employees", headers=H["hr"], json={"first_name": "T", "last_name": "P", "email": "test.person@workforce.ai"}).status_code == 409
    assert client.post("/api/employees", headers=H["hr"], json={"first_name": "T", "last_name": "P", "email": "bad", "age": 5}).status_code == 422
    lst = client.get("/api/employees?search=Person&size=5", headers=H["hr"]).json()
    assert lst["total"] >= 1 and any(e["id"] == emp["id"] for e in lst["items"])
    assert client.get("/api/employees?min_salary=4900&max_salary=5100", headers=H["hr"]).json()["total"] >= 1
    assert client.get("/api/employees?risk_level=high", headers=H["hr"]).status_code == 200
    up = client.patch(f"/api/employees/{emp['id']}", headers=H["hr"], json={"job_satisfaction": 1, "overtime": True})
    assert up.status_code == 200 and up.json()["job_satisfaction"] == 1
    assert client.delete(f"/api/employees/{emp['id']}", headers=H["hr"]).status_code == 403  # only ADMIN
    assert client.delete(f"/api/employees/{emp['id']}", headers=H["admin"]).status_code == 204
    assert client.get(f"/api/employees/{emp['id']}", headers=H["hr"]).status_code == 404


def test_manager_and_employee_scope(client, H):
    mgr = client.get("/api/employees?size=200", headers=H["manager"]).json()
    allp = client.get("/api/employees?size=200", headers=H["hr"]).json()
    assert 0 < mgr["total"] < allp["total"]
    emp = client.get("/api/employees?size=200", headers=H["employee"]).json()
    assert emp["total"] == 1 and emp["items"][0]["risk_score"] is None  # employees never see risk
    other = next(e for e in allp["items"] if e["email"] not in ("employee@workforce.ai",) and e["id"] != emp["items"][0]["id"])
    assert client.get(f"/api/employees/{other['id']}", headers=H["employee"]).status_code == 403


def test_departments_roles(client, H):
    r = client.post("/api/departments", headers=H["hr"], json={"name": "Legal", "budget": 1000})
    assert r.status_code == 201
    did = r.json()["id"]
    assert client.post("/api/departments", headers=H["hr"], json={"name": "legal"}).status_code == 409
    assert client.post("/api/roles", headers=H["hr"], json={"title": "Counsel", "department_id": did, "level": 3}).status_code == 201
    assert client.get("/api/departments/stats", headers=H["hr"]).json()
    assert client.post("/api/departments", headers=H["employee"], json={"name": "Hack"}).status_code == 403
    assert client.delete("/api/departments/1", headers=H["hr"]).status_code == 409  # still has employees
    assert client.delete(f"/api/departments/{did}", headers=H["hr"]).status_code in (204,)


def test_attendance_flow(client, H):
    emp_id = client.get("/api/auth/me", headers=H["admin"]).json()["employee_id"]
    # remove any record seeded for today so check-in is deterministic
    from app.database import SessionLocal
    from app.models import Attendance
    with SessionLocal() as db:
        db.query(Attendance).filter(Attendance.employee_id == emp_id, Attendance.work_date == date.today()).delete(); db.commit()
    ci = client.post("/api/attendance/check-in", headers=H["admin"], json={})
    assert ci.status_code == 200 and ci.json()["status"] in ("present", "late")
    assert client.post("/api/attendance/check-in", headers=H["admin"], json={}).status_code == 409
    co = client.post("/api/attendance/check-out", headers=H["admin"], json={})
    assert co.status_code == 200 and co.json()["working_hours"] >= 0
    assert client.post("/api/attendance/check-out", headers=H["admin"], json={}).status_code == 409
    rep = client.get(f"/api/attendance/report?month={date.today().month}&year={date.today().year}", headers=H["hr"]).json()
    assert rep and {"days_present", "late_days", "overtime_hours"} <= set(rep[0])
    assert client.get("/api/shifts", headers=H["hr"]).json()


def test_leave_workflow(client, H):
    start = date.today() + timedelta(days=40)
    while start.weekday() >= 5:
        start += timedelta(days=1)
    end = start + timedelta(days=2)
    body = {"leave_type": "Annual", "start_date": str(start), "end_date": str(end), "reason": "trip"}
    bal0 = {b["leave_type"]: b for b in client.get("/api/leave/balance", headers=H["employee"]).json()}["Annual"]
    r = client.post("/api/leave", headers=H["employee"], json=body)
    assert r.status_code == 201, r.text
    lid = r.json()["id"]
    assert client.post("/api/leave", headers=H["employee"], json=body).status_code == 409  # overlap
    assert client.post("/api/leave", headers=H["employee"], json={**body, "end_date": str(start - timedelta(days=1))}).status_code == 422
    assert client.post("/api/leave", headers=H["employee"], json={**body, "leave_type": "Bogus"}).status_code == 422
    assert client.patch(f"/api/leave/{lid}/review", headers=H["employee"], json={"action": "approve"}).status_code == 403
    rv = client.patch(f"/api/leave/{lid}/review", headers=H["manager"], json={"action": "approve", "comment": "ok"})
    assert rv.status_code == 200 and rv.json()["status"] == "approved"
    assert client.patch(f"/api/leave/{lid}/review", headers=H["manager"], json={"action": "reject"}).status_code == 409
    bal1 = {b["leave_type"]: b for b in client.get("/api/leave/balance", headers=H["employee"]).json()}["Annual"]
    assert bal1["remaining"] == bal0["remaining"] - r.json()["days"]
    # employee got a notification
    notes = client.get("/api/notifications", headers=H["employee"]).json()
    assert any("approved" in n["title"].lower() for n in notes["items"])
    # exceeding balance
    far = date.today() + timedelta(days=200)
    while far.weekday() != 0: far += timedelta(days=1)
    assert client.post("/api/leave", headers=H["employee"], json={"leave_type": "Casual", "start_date": str(far), "end_date": str(far + timedelta(days=40))}).status_code == 422
    assert client.get("/api/leave/report", headers=H["hr"]).status_code == 200


def test_payroll_generation_and_payslip(client, H):
    r = client.post("/api/payroll/generate", headers=H["hr"], json={"month": 1, "year": 2025, "bonus": 100, "incentive": 50})
    assert r.status_code == 200 and r.json()["created"] > 0
    again = client.post("/api/payroll/generate", headers=H["hr"], json={"month": 1, "year": 2025}).json()
    assert again["created"] == 0 and again["skipped_existing"] > 0  # idempotent
    rows = client.get("/api/payroll?month=1&year=2025&size=5", headers=H["hr"]).json()["items"]
    p = rows[0]
    assert abs(p["gross"] - p["total_deductions"] - p["net_pay"]) < 0.05
    assert p["tax"] >= 0 and p["bonus"] == 100
    pdf = client.get(f"/api/payroll/{p['id']}/payslip", headers=H["hr"])
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    # employees see only their own payroll
    mine = client.get("/api/payroll?size=100", headers=H["employee"]).json()
    me_emp = client.get("/api/auth/me", headers=H["employee"]).json()["employee_id"]
    assert all(i["employee_id"] == me_emp for i in mine["items"])
    other = next(i for i in rows if i["employee_id"] != me_emp)
    assert client.get(f"/api/payroll/{other['id']}/payslip", headers=H["employee"]).status_code == 403
    upd = client.patch(f"/api/payroll/{p['id']}", headers=H["hr"], json={"bonus": 500})
    assert upd.status_code == 200 and upd.json()["bonus"] == 500


def test_documents_validation(client, H):
    pdf = b"%PDF-1.4 test"
    ok = client.post("/api/documents", headers=H["employee"], files={"file": ("cv.pdf", pdf, "application/pdf")}, data={"doc_type": "resume"})
    assert ok.status_code == 201, ok.text
    did = ok.json()["id"]
    assert client.post("/api/documents", headers=H["employee"], files={"file": ("evil.exe", b"MZ", "application/octet-stream")}).status_code == 415
    assert client.post("/api/documents", headers=H["employee"], files={"file": ("fake.pdf", b"not a pdf", "application/pdf")}).status_code == 422
    assert client.post("/api/documents", headers=H["employee"], files={"file": ("e.pdf", b"", "application/pdf")}).status_code == 422
    dl = client.get(f"/api/documents/{did}/download", headers=H["employee"])
    assert dl.status_code == 200 and dl.content == pdf
    assert client.get(f"/api/documents/{did}/download", headers=H["manager"]).status_code == 403
    assert client.get(f"/api/documents/{did}/download", headers=H["hr"]).status_code == 200
    assert client.delete(f"/api/documents/{did}", headers=H["employee"]).status_code == 204


def test_notifications_and_chat(client, H):
    me = client.get("/api/auth/me", headers=H["employee"]).json()
    hr = client.get("/api/auth/me", headers=H["hr"]).json()
    assert client.post("/api/notifications/send", headers=H["hr"], json={"user_id": me["id"], "title": "Hi", "message": "Test", "priority": "high"}).status_code == 201
    n = client.get("/api/notifications?unread_only=true", headers=H["employee"]).json()
    assert n["total"] >= 1
    nid = n["items"][0]["id"]
    assert client.patch(f"/api/notifications/{nid}/read", headers=H["employee"]).json()["is_read"]
    assert client.patch(f"/api/notifications/{nid}/read", headers=H["hr"]).status_code == 404  # not owner
    assert client.post("/api/notifications/read-all", headers=H["employee"]).status_code == 200
    assert client.get("/api/notifications/unread-count", headers=H["employee"]).json()["unread"] == 0
    # chat
    m = client.post("/api/chat", headers=H["hr"], json={"receiver_id": me["id"], "content": "Hello Eli"})
    assert m.status_code == 201 and not m.json()["is_read"]
    assert client.post("/api/chat", headers=H["hr"], json={"receiver_id": hr["id"], "content": "me"}).status_code == 422
    contacts = {c["id"]: c for c in client.get("/api/chat/contacts", headers=H["employee"]).json()}
    assert contacts[hr["id"]]["unread"] >= 1
    assert client.post(f"/api/chat/read/{hr['id']}", headers=H["employee"]).json()["marked"] >= 1
    hist = client.get(f"/api/chat/history/{me['id']}", headers=H["hr"]).json()
    assert hist[-1]["is_read"] and hist[-1]["read_at"]
    assert client.get("/api/chat/logs", headers=H["employee"]).status_code == 403
    assert client.get("/api/chat/logs", headers=H["hr"]).json()["total"] >= 1


def test_websocket_auth_and_push(client, H, tokens):
    me = client.get("/api/auth/me", headers=H["employee"]).json()
    with client.websocket_connect(f"/api/ws?token={tokens['employee']}") as ws:
        assert ws.receive_json()["type"] == "connected"
        ws.send_text("ping")
        assert ws.receive_json()["type"] == "pong"
        client.post("/api/notifications/send", headers=H["hr"], json={"user_id": me["id"], "title": "Live", "message": "pushed"})
        msg = ws.receive_json()
        assert msg["type"] == "notification" and msg["data"]["title"] == "Live"
    import pytest
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/ws?token=garbage"):
            pass


def test_tasks_and_performance(client, H):
    uid = client.get("/api/auth/me", headers=H["manager"]).json()["id"]
    t = client.post("/api/tasks", headers=H["hr"], json={"title": "Follow up", "assigned_to": uid, "due_date": str(date.today() + timedelta(days=1)), "priority": "high"})
    assert t.status_code == 201 and t.json()["due_soon"]
    assert client.post("/api/tasks", headers=H["hr"], json={"title": "Past", "due_date": "2020-01-01"}).status_code == 422
    done = client.patch(f"/api/tasks/{t.json()['id']}", headers=H["manager"], json={"status": "done"})
    assert done.status_code == 200 and done.json()["completed_at"]
    assert client.get("/api/tasks/stats", headers=H["hr"]).json()["done"] >= 1
    team = client.get("/api/employees?size=5", headers=H["manager"]).json()["items"]
    eid = next(e["id"] for e in team if e["email"] != "manager@workforce.ai")
    rv = client.post("/api/performance/reviews", headers=H["manager"], json={"employee_id": eid, "period": "2026-Q3", "rating": 2, "improvements": "Docs"})
    assert rv.status_code == 201
    assert client.get(f"/api/performance/summary/{eid}", headers=H["manager"]).json()["average_rating"] is not None
    g = client.post("/api/performance/goals", headers=H["manager"], json={"employee_id": eid, "title": "Ship feature"})
    assert client.patch(f"/api/performance/goals/{g.json()['id']}", headers=H["manager"], json={"progress": 100}).json()["status"] == "completed"
    me = client.get("/api/auth/me", headers=H["employee"]).json()["employee_id"]
    assert client.post("/api/performance/reviews", headers=H["employee"], json={"employee_id": me, "period": "x", "rating": 5}).status_code == 403


def test_audit_trail(client, H):
    logs = client.get("/api/audit?size=200", headers=H["admin"]).json()
    actions = {l["action"] for l in logs["items"]}
    assert {"LOGIN", "CREATE", "UPDATE"} <= actions
    assert client.get("/api/audit/summary", headers=H["admin"]).json()["failed_logins"] >= 1
    upd = [l for l in logs["items"] if l["action"] == "UPDATE" and l["entity"] == "employee" and l["changes"]]
    assert upd and "job_satisfaction" in upd[0]["changes"] or any("job_satisfaction" in (l["changes"] or {}) for l in upd)
