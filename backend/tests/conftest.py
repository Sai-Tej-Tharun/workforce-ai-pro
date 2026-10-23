import os, tempfile, sys
from pathlib import Path
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")
os.environ["UPLOAD_DIR"] = str(Path(_tmp) / "uploads")
os.environ["MODEL_DIR"] = str(Path(_tmp) / "models")
os.environ["EXPOSE_RESET_TOKEN"] = "true"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, SessionLocal
from app import security
from scripts.seed import seed

CREDS = {"admin": ("admin@workforce.ai", "Admin@123"), "hr": ("hr@workforce.ai", "Hr@12345"),
         "manager": ("manager@workforce.ai", "Manager@123"), "employee": ("employee@workforce.ai", "Employee@123")}


@pytest.fixture(scope="session")
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db, n_active=36, n_terminated=6, dataset_rows=1000)
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_throttle():
    security.reset_throttle()


@pytest.fixture(scope="session")
def tokens(client):
    out = {}
    for role, (email, pw) in CREDS.items():
        r = client.post("/api/auth/login", data={"username": email, "password": pw})
        assert r.status_code == 200, r.text
        out[role] = r.json()["access_token"]
    return out


@pytest.fixture(scope="session")
def H(tokens):
    return {role: {"Authorization": f"Bearer {t}"} for role, t in tokens.items()}
