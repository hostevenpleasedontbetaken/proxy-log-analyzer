"""Database engine + ORM base class.

The engine (a pool of Postgres connections) is created on first use, so importing this module
never needs a database. Models (M3) subclass `Base`; Alembic reads `Base.metadata` to generate
migrations.
"""

from functools import cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def sqlalchemy_url(database_url: str) -> str:
    """Neon/compose give `postgresql://...`; SQLAlchemy needs the driver named (psycopg 3)."""
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
    return database_url


@cache
def get_engine(database_url: str) -> Engine:
    # pool_pre_ping: Neon closes idle connections when it sleeps; test each one before use.
    return create_engine(sqlalchemy_url(database_url), pool_pre_ping=True)
