"""Configure offline and online database migrations for registered ORM models."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool, text

from app.core.config import settings
from app.db.base import Base

# Import models so that they are registered with Base.metadata.
import app.models  # noqa: F401


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = Base.metadata

_extension_owned_relation_names: set[str] = set()


def _load_extension_owned_relation_names(
    connection,
) -> set[str]:
    """
    Return PostgreSQL relation names owned by installed extensions.

    PostGIS distributions may install topology/tiger-geocoder objects that are
    visible to reflection even though they are not part of application model
    metadata. Alembic must ignore those objects while still checking all Farm
    Platform tables for drift.
    """
    rows = connection.execute(
        text(
            """
            SELECT DISTINCT
                c.relname
            FROM pg_depend AS d
            JOIN pg_class AS c
              ON c.oid = d.objid
            JOIN pg_extension AS e
              ON e.oid = d.refobjid
            WHERE
                d.classid = 'pg_class'::regclass
                AND d.deptype = 'e'
            """
        )
    )

    return {
        str(row[0])
        for row in rows
    }


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
    # Extension-owned tables/indexes/sequences are PostgreSQL infrastructure,
    # not Farm Platform schema. Some PostGIS images expose Tiger objects with
    # schema=None during reflection, so filtering by schema alone is not
    # sufficient.
    if (
        reflected
        and name
        in _extension_owned_relation_names
    ):
        return False

    # Keep this explicit for offline migration/autogenerate paths where no
    # database connection is available to populate the extension set.
    if (
        type_ == "table"
        and name == "spatial_ref_sys"
    ):
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
        global _extension_owned_relation_names

        _extension_owned_relation_names = (
            _load_extension_owned_relation_names(
                connection
            )
        )

        # The metadata query above starts an implicit SQLAlchemy transaction.
        # End it before Alembic opens its own migration transaction; otherwise
        # connection close would roll back the migration and version table.
        connection.commit()

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
