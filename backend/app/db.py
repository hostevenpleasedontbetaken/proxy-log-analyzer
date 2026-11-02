"""Database engine + ORM base class.

The engine (a pool of Postgres connections) is created on first use, so importing this module
never needs a database. Models (M3) subclass `Base`; Alembic reads `Base.metadata` to generate
migrations.
"""

from functools import cache

from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

# Predictable constraint and index names (e.g. "fk_log_entries_upload_id_uploads"), so
# migrations can refer to them by name instead of whatever Postgres would invent.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def sqlalchemy_url(database_url: str) -> str:
    """Neon/compose give `postgresql://...`; SQLAlchemy needs the driver named (psycopg 3)."""
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
    return database_url


@cache
def get_engine(database_url: str) -> Engine:
    # pool_pre_ping: Neon closes idle connections when it sleeps; test each one before use.
    return create_engine(sqlalchemy_url(database_url), pool_pre_ping=True)


def new_session(database_url: str) -> Session:
    """A unit of work with the database (borrows a pooled connection). Use as a context
    manager: `with new_session(url) as session, session.begin(): ...` commits on success and
    rolls everything back if an exception escapes the block."""
    return Session(get_engine(database_url))
