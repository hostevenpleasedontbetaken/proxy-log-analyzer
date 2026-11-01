"""Alembic entry point: connects with DATABASE_URL and compares against our models."""

import os

from alembic import context
from sqlalchemy import create_engine, pool

from app.db import Base, sqlalchemy_url

target_metadata = Base.metadata


def run_migrations_online() -> None:
    # In production this is Neon's *direct* (non-pooled) URL: migrations need a real session.
    engine = create_engine(sqlalchemy_url(os.environ["DATABASE_URL"]), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
