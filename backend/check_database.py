from sqlalchemy.engine import make_url
from app.database import engine

url = make_url(str(engine.url))
print("Database type:", url.drivername)
print("Database name:", url.database)
print("Database host:", url.host or "local/default")
print("Database port:", url.port or "default")
