from getpass import getpass
from sqlalchemy import select
from app.database import SessionLocal
from app.models import User
from app.security import verify_password

email = input("Enter login email: ").strip().lower()
password = getpass("Enter login password: ")

db = SessionLocal()
try:
    user = db.scalar(select(User).where(User.email == email))

    print("\n--- Login Diagnostic ---")
    print("User exists:", user is not None)

    if user:
        print("Email:", user.email)
        print("Role:", user.role)
        print("Active:", user.is_active)
        print("Password hash format:", user.hashed_password.split("$")[0])
        print("Password matches:", verify_password(password, user.hashed_password))
finally:
    db.close()
