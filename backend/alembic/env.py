"""Alembic environment configuration for multi-schema migrations.

Supports both shared and tenant schemas. Use -x tenant=schema_name
to target a specific tenant schema for migrations.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from app.db.base import shared_metadata, tenant_metadata

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Combine both metadata objects for autogenerate support
target_metadata = [tenant_metadata, shared_metadata]


def get_target_schema() -> str | None:
    """Get the target schema from -x tenant=schema_name argument."""
    x_args = context.get_x_argument(as_dictionary=True)
    return x_args.get("tenant")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (SQL script generation)."""
    url = config.get_main_option("sqlalchemy.url")
    schema = get_target_schema()

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=schema,
    )

    with context.begin_transaction():
        if schema:
            context.execute(text(f'SET search_path TO "{schema}"'))
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (direct database connection).

    Uses synchronous psycopg connection for Alembic compatibility.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    schema = get_target_schema()

    with connectable.connect() as connection:
        if schema:
            connection.execute(text(f'SET search_path TO "{schema}"'))
            connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=schema,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
