from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool
from .config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
_kwargs = {}
if _is_sqlite:
    _kwargs["connect_args"] = {"check_same_thread": False}
    if ":memory:" in settings.DATABASE_URL:
        _kwargs["poolclass"] = StaticPool
else:
    # Connection pooling for MySQL (scalability)
    _kwargs.update(pool_size=10, max_overflow=20, pool_pre_ping=True, pool_recycle=1800)

engine = create_engine(settings.DATABASE_URL, **_kwargs)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _fk_pragma(dbapi_con, _):
        dbapi_con.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
