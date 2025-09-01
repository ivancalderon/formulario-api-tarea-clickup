from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import get_settings

settings = get_settings()

# For SQLite: check_same_thread=False is useful if you later use async or threads.
connect_args = {"check_same_thread": False} if settings.DB_URL.startswith("sqlite") else {}
engine = create_engine(settings.DB_URL, echo=False, future=True, connect_args=connect_args)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)

Base = declarative_base()

def init_db() -> None:
    """Create tables if not present. (No-op until models exist.)"""
    Base.metadata.create_all(bind=engine)
