from alembic import context
from app.infrastructure.database import Base
from app.infrastructure import db_models
from app.infrastructure.settings import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url.replace("+asyncpg", "").replace("+aiosqlite", ""))
target_metadata = Base.metadata

def run_migrations_online():
    from sqlalchemy import engine_from_config, pool
    connectable = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction(): context.run_migrations()

run_migrations_online()
