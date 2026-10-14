from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import settings
from app.db.base import Base

# Import models so that they are registered with Base.metadata.
import app.models  # noqa: F401


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = Base.metadata


def include_name(
    name,
    type_,
    parent_names,
):
    """
    Limit Alembic autogenerate/check to the application's public schema.

    PostGIS installations can add Tiger/Topology schemas and extension-owned
    objects that are visible through PostgreSQL's search path but are not part
    of Farm Platform's model metadata.
    """
    if type_ == "schema":
        return name in (
            None,
            "public",
        )

    schema_name = (
        parent_names.get(
            "schema_name"
        )
        if parent_names
        else None
    )

    if schema_name not in (
        None,
        "public",
    ):
        return False

    if (
        type_ == "table"
        and name == "spatial_ref_sys"
    ):
        return False

    return True


def include_object(
    object,
    name,
    type_,
    reflected,
    compare_to,
):
    # PostGIS manages this table itself.
    if type_ == "table" and name == "spatial_ref_sys":
        return False

    return True


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
        compare_type=True,
        include_schemas=True,
        include_name=include_name,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        settings.database_url,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_schemas=True,
            include_name=include_name,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
