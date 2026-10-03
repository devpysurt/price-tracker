from datetime import UTC, datetime
from decimal import Decimal
from sqlalchemy import DateTime, Integer, create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.types import TypeDecorator

class Base(DeclarativeBase):
    pass

class Money(TypeDecorator):
    """Persist exact integer cents, expose Decimal dollars."""
    impl = Integer
    cache_ok = True
    def process_bind_param(self, value, dialect):
        return None if value is None else int(Decimal(value) * 100)
    def process_result_value(self, value, dialect):
        return None if value is None else (Decimal(value) / 100).quantize(Decimal("0.01"))

class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True
    def process_bind_param(self, value, dialect):
        return None if value is None else value.astimezone(UTC).replace(tzinfo=None)
    def process_result_value(self, value, dialect):
        return None if value is None else value.replace(tzinfo=UTC)

def utcnow() -> datetime:
    return datetime.now(UTC)

def make_database(url: str):
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})
    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
    return engine, sessionmaker(engine, expire_on_commit=False)
