from sqlalchemy import inspect, text
from app.database import engine

inspector = inspect(engine)
tables = inspector.get_table_names()

print("Tables found:", len(tables))
print("\n--- Existing database data ---")

with engine.connect() as conn:
    for table in tables:
        quoted = "`" + table.replace("`", "``") + "`"
        count = conn.execute(text(f"SELECT COUNT(*) FROM {quoted}")).scalar()
        if count:
            print(f"{table}: {count} rows")

print("\nDatabase inspection complete.")
