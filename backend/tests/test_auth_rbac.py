def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_register_login_session_refresh(client):
    r = client.post("/api/auth/register", json={"email": "new.user@example.com", "full_name": "New User", "password": "Passw0rdX"})
    assert r.status_code == 201 and r.json()["role"] == "EMPLOYEE"
    assert client.post("/api/auth/register", json={"email": "new.user@example.com", "full_name": "New User", "password": "Passw0rdX"}).status_code == 409
    lg = client.post("/api/auth/login", data={"username": "new.user@example.com", "password": "Passw0rdX"})
    assert lg.status_code == 200
    body = lg.json()
    h = {"Authorization": f"Bearer {body['access_token']}"}
    s = client.get("/api/auth/session", headers=h).json()
    assert s["valid"] and 0 < s["expires_in_seconds"] <= 30 * 60
    rf = client.post("/api/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert rf.status_code == 200
    # refresh token must not work as access token, and vice versa
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['refresh_token']}"}).status_code == 401
    assert client.post("/api/auth/refresh", json={"refresh_token": body["access_token"]}).status_code == 401


def test_weak_password_and_bad_login(client):
    assert client.post("/api/auth/register", json={"email": "weak@example.com", "full_name": "Weak", "password": "abcdefgh"}).status_code == 422
    assert client.post("/api/auth/login", data={"username": "admin@workforce.ai", "password": "nope"}).status_code == 401


def test_login_throttle(client):
    for _ in range(8):
        client.post("/api/auth/login", data={"username": "hr@workforce.ai", "password": "bad"})
    assert client.post("/api/auth/login", data={"username": "hr@workforce.ai", "password": "Hr@12345"}).status_code == 429


def test_forgot_reset_password(client):
    r = client.post("/api/auth/forgot-password", json={"email": "new.user@example.com"}).json()
    tok = r["dev_reset_token"]
    assert client.post("/api/auth/reset-password", json={"token": "bogus", "new_password": "Another1Pass"}).status_code == 400
    assert client.post("/api/auth/reset-password", json={"token": tok, "new_password": "Another1Pass"}).status_code == 200
    assert client.post("/api/auth/reset-password", json={"token": tok, "new_password": "Another1Pass"}).status_code == 400  # single use
    assert client.post("/api/auth/login", data={"username": "new.user@example.com", "password": "Another1Pass"}).status_code == 200
    # unknown email -> same generic response, no token
    assert "dev_reset_token" not in client.post("/api/auth/forgot-password", json={"email": "ghost@example.com"}).json()


def test_expired_and_missing_token(client):
    import jwt, time
    from app.config import settings
    bad = jwt.encode({"sub": "1", "type": "access", "exp": int(time.time()) - 10}, settings.SECRET_KEY, algorithm="HS256")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {bad}"})
    assert r.status_code == 401 and "expired" in r.json()["detail"].lower()
    assert client.get("/api/employees").status_code == 401


def test_rbac_matrix(client, H):
    assert client.get("/api/users", headers=H["employee"]).status_code == 403
    assert client.get("/api/users", headers=H["hr"]).status_code == 200
    assert client.post("/api/users", headers=H["hr"], json={"email": "x@y.com", "full_name": "X Y", "password": "Passw0rd1"}).status_code == 403
    assert client.get("/api/audit", headers=H["manager"]).status_code == 403
    assert client.get("/api/datasets", headers=H["manager"]).status_code == 403
    assert client.get("/api/monitoring/high-risk", headers=H["employee"]).status_code == 403
    assert client.post("/api/payroll/generate", headers=H["manager"], json={"month": 1, "year": 2026}).status_code == 403
    assert client.get("/api/analytics/forecast", headers=H["manager"]).status_code == 403


def test_admin_user_management(client, H):
    r = client.post("/api/users", headers=H["admin"], json={"email": "mgr2@example.com", "full_name": "Mgr Two", "password": "Passw0rd1", "role": "MANAGER"})
    assert r.status_code == 201
    uid = r.json()["id"]
    assert client.patch(f"/api/users/{uid}", headers=H["admin"], json={"is_active": False}).status_code == 200
    assert client.post("/api/auth/login", data={"username": "mgr2@example.com", "password": "Passw0rd1"}).status_code == 403
    me = client.get("/api/auth/me", headers=H["admin"]).json()
    assert client.patch(f"/api/users/{me['id']}", headers=H["admin"], json={"role": "HR"}).status_code == 400
