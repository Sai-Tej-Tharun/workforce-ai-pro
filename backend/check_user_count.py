from sqlalchemy import func, select
from app.database import SessionLocal
from app.models import User

with SessionLocal() as db:
    count = db.scalar(select(func.count()).select_from(User))
    print("Existing users:", count)
