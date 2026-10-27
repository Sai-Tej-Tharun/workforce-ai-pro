from sqlalchemy.engine import make_url
from app.config import settings

url = make_url(settings.DATABASE_URL)
print("Database type:", url.drivername)
print("Database name:", url.database)
print("Database host:", url.host or "local/default")
print("Database port:", url.port or "default")
