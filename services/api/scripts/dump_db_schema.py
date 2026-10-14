from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.core.config import settings


def section(title: str) -> str:
    return "\n" + "=" * 100 + f"\n{title}\n" + "=" * 100 + "\n"


def safe_db_url() -> str:
    url = make_url(settings.database_url)
    return str(url.set(password="***" if url.password else None))


def pg_tool_url() -> str:
    """
    Convert SQLAlchemy URLs such as:
      postgresql+psycopg://...
    to a libpq/pg_dump compatible:
      postgresql://...
    """
    url = make_url(settings.database_url)

    return str(url.set(drivername="postgresql"))


def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
        )

        output = completed.stdout

        if completed.stderr:
            output += "\n[stderr]\n" + completed.stderr

        return completed.returncode, output

    except Exception as error:
        return (
            1,
            f"{type(error).__name__}: {error}\n",
        )


def fetch_all_dicts(
    connection,
    sql: str,
    params: dict | None = None,
) -> list[dict]:
    return [
        dict(row)
        for row in (
            connection.execute(
                text(sql),
                params or {},
            )
            .mappings()
            .all()
        )
    ]


def write_rows(
    handle,
    rows: list[dict],
) -> None:
    if not rows:
        handle.write("(none)\n")
        return

    for row in rows:
        handle.write(
            json.dumps(
                row,
                default=str,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Dump the complete PostgreSQL schema plus a "
            "database integrity/audit report into one text file."
        )
    )

    parser.add_argument(
        "--output",
        default="db_schema_audit.txt",
        help=("Output text file. Default: db_schema_audit.txt"),
    )

    parser.add_argument(
        "--skip-row-counts",
        action="store_true",
        help=("Skip exact COUNT(*) for every table if the database is large."),
    )

    args = parser.parse_args()

    output_path = Path(args.output).resolve()

    engine = create_engine(settings.database_url)

    inspector = inspect(engine)

    now = datetime.now(timezone.utc)

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as handle:
        handle.write("FARM PLATFORM DATABASE SCHEMA + INTEGRITY AUDIT\n")
        handle.write(f"Generated at: {now.isoformat()}\n")
        handle.write(f"Database URL: {safe_db_url()}\n")

        # ---------------------------------------------------------
        # PostgreSQL / database identity
        # ---------------------------------------------------------

        handle.write(section("1. SERVER / DATABASE INFORMATION"))

        with engine.connect() as connection:
            rows = fetch_all_dicts(
                connection,
                """
                SELECT
                    current_database() AS database_name,
                    current_user AS current_user,
                    version() AS postgres_version,
                    current_schema() AS current_schema
                """,
            )

            write_rows(
                handle,
                rows,
            )

        # ---------------------------------------------------------
        # Alembic state
        # ---------------------------------------------------------

        handle.write(section("2. ALEMBIC STATE"))

        api_dir = Path.cwd()

        for label, command in (
            (
                "alembic current",
                [
                    "uv",
                    "run",
                    "alembic",
                    "current",
                ],
            ),
            (
                "alembic heads",
                [
                    "uv",
                    "run",
                    "alembic",
                    "heads",
                ],
            ),
            (
                "alembic check",
                [
                    "uv",
                    "run",
                    "alembic",
                    "check",
                ],
            ),
        ):
            handle.write(f"\n--- {label} ---\n")

            code, output = run_command(
                command,
                cwd=api_dir,
            )

            handle.write(f"exit_code={code}\n")

            handle.write(output or "(no output)\n")

        # ---------------------------------------------------------
        # Complete schema SQL
        # ---------------------------------------------------------

        handle.write(section("3. COMPLETE PG_DUMP --SCHEMA-ONLY"))

        pg_dump = shutil.which("pg_dump")

        if pg_dump is None:
            handle.write("pg_dump not found in PATH.\n")
        else:
            code, output = run_command(
                [
                    pg_dump,
                    "--schema-only",
                    "--no-owner",
                    "--no-privileges",
                    "--quote-all-identifiers",
                    pg_tool_url(),
                ]
            )

            handle.write(f"exit_code={code}\n")

            handle.write(output)

        # ---------------------------------------------------------
        # Extensions
        # ---------------------------------------------------------

        handle.write(section("4. INSTALLED EXTENSIONS"))

        with engine.connect() as connection:
            rows = fetch_all_dicts(
                connection,
                """
                SELECT
                    e.extname AS extension,
                    e.extversion AS version,
                    n.nspname AS schema
                FROM pg_extension AS e
                JOIN pg_namespace AS n
                  ON n.oid = e.extnamespace
                ORDER BY e.extname
                """,
            )

            write_rows(
                handle,
                rows,
            )

        # ---------------------------------------------------------
        # Schemas
        # ---------------------------------------------------------

        handle.write(section("5. DATABASE SCHEMAS"))

        with engine.connect() as connection:
            rows = fetch_all_dicts(
                connection,
                """
                SELECT schema_name
                FROM information_schema.schemata
                ORDER BY schema_name
                """,
            )

            write_rows(
                handle,
                rows,
            )

        # ---------------------------------------------------------
        # Tables and columns
        # ---------------------------------------------------------

        handle.write(section("6. TABLES + COLUMNS"))

        with engine.connect() as connection:
            rows = fetch_all_dicts(
                connection,
                """
                SELECT
                    c.table_schema,
                    c.table_name,
                    c.ordinal_position,
                    c.column_name,
                    c.data_type,
                    c.udt_name,
                    c.is_nullable,
                    c.column_default,
                    c.character_maximum_length,
                    c.numeric_precision,
                    c.numeric_scale
                FROM information_schema.columns AS c
                JOIN information_schema.tables AS t
                  ON t.table_schema = c.table_schema
                 AND t.table_name = c.table_name
                WHERE c.table_schema NOT IN (
                    'pg_catalog',
                    'information_schema'
                )
                  AND t.table_type = 'BASE TABLE'
                ORDER BY
                    c.table_schema,
                    c.table_name,
                    c.ordinal_position
                """,
            )

            write_rows(
                handle,
                rows,
            )

        # ---------------------------------------------------------
        # Constraints
        # ---------------------------------------------------------

        handle.write(section("7. PRIMARY / UNIQUE / FOREIGN / CHECK CONSTRAINTS"))

        with engine.connect() as connection:
            rows = fetch_all_dicts(
                connection,
                """
                SELECT
                    n.nspname AS schema_name,
                    c.relname AS table_name,
                    con.conname AS constraint_name,
                    CASE con.contype
                        WHEN 'p' THEN 'PRIMARY KEY'
                        WHEN 'u' THEN 'UNIQUE'
                        WHEN 'f' THEN 'FOREIGN KEY'
                        WHEN 'c' THEN 'CHECK'
                        WHEN 'x' THEN 'EXCLUSION'
                        ELSE con.contype::text
                    END AS constraint_type,
                    pg_get_constraintdef(
                        con.oid,
                        true
                    ) AS definition
                FROM pg_constraint AS con
                JOIN pg_class AS c
                  ON c.oid = con.conrelid
                JOIN pg_namespace AS n
                  ON n.oid = c.relnamespace
                WHERE n.nspname NOT IN (
                    'pg_catalog',
                    'information_schema'
                )
                ORDER BY
                    n.nspname,
                    c.relname,
                    constraint_type,
                    con.conname
                """,
            )

            write_rows(
                handle,
                rows,
            )

        # ---------------------------------------------------------
        # Indexes
        # ---------------------------------------------------------

        handle.write(section("8. INDEXES"))

        with engine.connect() as connection:
            rows = fetch_all_dicts(
                connection,
                """
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE schemaname NOT IN (
                    'pg_catalog',
                    'information_schema'
                )
                ORDER BY
                    schemaname,
                    tablename,
                    indexname
                """,
            )

            write_rows(
                handle,
                rows,
            )

        # ---------------------------------------------------------
        # Invalid / not-ready indexes
        # ---------------------------------------------------------

        handle.write(section("9. INVALID OR NOT-READY INDEXES"))

        with engine.connect() as connection:
            rows = fetch_all_dicts(
                connection,
                """
                SELECT
                    ns.nspname AS schema_name,
                    tbl.relname AS table_name,
                    idx.relname AS index_name,
                    i.indisvalid AS is_valid,
                    i.indisready AS is_ready
                FROM pg_index AS i
                JOIN pg_class AS idx
                  ON idx.oid = i.indexrelid
                JOIN pg_class AS tbl
                  ON tbl.oid = i.indrelid
                JOIN pg_namespace AS ns
                  ON ns.oid = tbl.relnamespace
                WHERE ns.nspname NOT IN (
                    'pg_catalog',
                    'information_schema'
                )
                  AND (
                    NOT i.indisvalid
                    OR NOT i.indisready
                  )
                ORDER BY
                    ns.nspname,
                    tbl.relname,
                    idx.relname
                """,
            )

            write_rows(
                handle,
                rows,
            )

        # ---------------------------------------------------------
        # PostGIS
        # ---------------------------------------------------------

        handle.write(section("10. POSTGIS GEOMETRY COLUMNS"))

        with engine.connect() as connection:
            try:
                rows = fetch_all_dicts(
                    connection,
                    """
                    SELECT
                        f_table_schema,
                        f_table_name,
                        f_geometry_column,
                        coord_dimension,
                        srid,
                        type
                    FROM geometry_columns
                    ORDER BY
                        f_table_schema,
                        f_table_name,
                        f_geometry_column
                    """,
                )

                write_rows(
                    handle,
                    rows,
                )

            except Exception as error:
                handle.write(f"{type(error).__name__}: {error}\n")

        # ---------------------------------------------------------
        # Views
        # ---------------------------------------------------------

        handle.write(section("11. VIEWS + MATERIALIZED VIEWS"))

        with engine.connect() as connection:
            rows = fetch_all_dicts(
                connection,
                """
                SELECT
                    schemaname AS schema_name,
                    viewname AS object_name,
                    'VIEW' AS object_type,
                    definition
                FROM pg_views
                WHERE schemaname NOT IN (
                    'pg_catalog',
                    'information_schema'
                )

                UNION ALL

                SELECT
                    schemaname AS schema_name,
                    matviewname AS object_name,
                    'MATERIALIZED VIEW' AS object_type,
                    definition
                FROM pg_matviews
                WHERE schemaname NOT IN (
                    'pg_catalog',
                    'information_schema'
                )

                ORDER BY
                    schema_name,
                    object_name
                """,
            )

            write_rows(
                handle,
                rows,
            )

        # ---------------------------------------------------------
        # Sequences
        # ---------------------------------------------------------

        handle.write(section("12. SEQUENCES"))

        with engine.connect() as connection:
            rows = fetch_all_dicts(
                connection,
                """
                SELECT
                    sequence_schema,
                    sequence_name,
                    data_type,
                    start_value,
                    minimum_value,
                    maximum_value,
                    increment
                FROM information_schema.sequences
                ORDER BY
                    sequence_schema,
                    sequence_name
                """,
            )

            write_rows(
                handle,
                rows,
            )

        # ---------------------------------------------------------
        # Triggers
        # ---------------------------------------------------------

        handle.write(section("13. TRIGGERS"))

        with engine.connect() as connection:
            rows = fetch_all_dicts(
                connection,
                """
                SELECT
                    event_object_schema,
                    event_object_table,
                    trigger_name,
                    action_timing,
                    event_manipulation,
                    action_statement
                FROM information_schema.triggers
                ORDER BY
                    event_object_schema,
                    event_object_table,
                    trigger_name,
                    event_manipulation
                """,
            )

            write_rows(
                handle,
                rows,
            )

        # ---------------------------------------------------------
        # Functions / procedures / aggregates
        # ---------------------------------------------------------

        handle.write(section("14. ROUTINES / FUNCTIONS / PROCEDURES / AGGREGATES"))

        with engine.connect() as connection:
            # pg_proc also contains aggregates and window functions.
            # pg_get_functiondef() cannot be called on aggregate rows
            # (for example PostGIS ST_ClusterIntersecting), so list all
            # routine metadata first and fetch definitions only for real
            # functions/procedures.
            rows = fetch_all_dicts(
                connection,
                """
                SELECT
                    n.nspname AS schema_name,
                    p.proname AS routine_name,
                    CASE p.prokind
                        WHEN 'f' THEN 'FUNCTION'
                        WHEN 'p' THEN 'PROCEDURE'
                        WHEN 'a' THEN 'AGGREGATE'
                        WHEN 'w' THEN 'WINDOW'
                        ELSE p.prokind::text
                    END AS routine_type,
                    pg_get_function_identity_arguments(
                        p.oid
                    ) AS arguments,
                    pg_get_function_result(
                        p.oid
                    ) AS result_type,
                    EXISTS (
                        SELECT 1
                        FROM pg_depend AS d
                        WHERE d.objid = p.oid
                          AND d.classid = 'pg_proc'::regclass
                          AND d.deptype = 'e'
                    ) AS belongs_to_extension
                FROM pg_proc AS p
                JOIN pg_namespace AS n
                  ON n.oid = p.pronamespace
                WHERE n.nspname NOT IN (
                    'pg_catalog',
                    'information_schema'
                )
                ORDER BY
                    n.nspname,
                    p.proname,
                    arguments
                """,
            )

            write_rows(
                handle,
                rows,
            )

            handle.write(
                "\n--- FUNCTION / PROCEDURE DEFINITIONS "
                "(non-extension objects) ---\n"
            )

            rows = fetch_all_dicts(
                connection,
                """
                SELECT
                    n.nspname AS schema_name,
                    p.proname AS routine_name,
                    CASE p.prokind
                        WHEN 'f' THEN 'FUNCTION'
                        WHEN 'p' THEN 'PROCEDURE'
                    END AS routine_type,
                    pg_get_function_identity_arguments(
                        p.oid
                    ) AS arguments,
                    pg_get_functiondef(
                        p.oid
                    ) AS definition
                FROM pg_proc AS p
                JOIN pg_namespace AS n
                  ON n.oid = p.pronamespace
                WHERE n.nspname NOT IN (
                    'pg_catalog',
                    'information_schema'
                )
                  AND p.prokind IN ('f', 'p')
                  AND NOT EXISTS (
                        SELECT 1
                        FROM pg_depend AS d
                        WHERE d.objid = p.oid
                          AND d.classid = 'pg_proc'::regclass
                          AND d.deptype = 'e'
                  )
                ORDER BY
                    n.nspname,
                    p.proname,
                    arguments
                """,
            )

            write_rows(
                handle,
                rows,
            )

        # ---------------------------------------------------------
        # Table sizes / approximate counts
        # ---------------------------------------------------------

        handle.write(section("15. TABLE SIZES + APPROXIMATE ROW COUNTS"))

        with engine.connect() as connection:
            rows = fetch_all_dicts(
                connection,
                """
                SELECT
                    schemaname AS schema_name,
                    relname AS table_name,
                    n_live_tup AS approximate_rows,
                    pg_total_relation_size(
                        quote_ident(schemaname)
                        || '.'
                        || quote_ident(relname)
                    ) AS total_bytes,
                    pg_size_pretty(
                        pg_total_relation_size(
                            quote_ident(schemaname)
                            || '.'
                            || quote_ident(relname)
                        )
                    ) AS total_size
                FROM pg_stat_user_tables
                ORDER BY
                    schemaname,
                    relname
                """,
            )

            write_rows(
                handle,
                rows,
            )

        # ---------------------------------------------------------
        # Exact row counts
        # ---------------------------------------------------------

        handle.write(section("16. EXACT ROW COUNTS"))

        user_tables = inspector.get_table_names(schema="public")

        if args.skip_row_counts:
            handle.write("Skipped by --skip-row-counts\n")

        else:
            with engine.connect() as connection:
                for table_name in sorted(user_tables):
                    # Table names come from SQLAlchemy's DB inspector,
                    # not user input.
                    quoted = (
                        '"'
                        + table_name.replace(
                            '"',
                            '""',
                        )
                        + '"'
                    )

                    count = connection.execute(
                        text(f"SELECT COUNT(*) " f"FROM {quoted}")
                    ).scalar_one()

                    handle.write(f"{table_name}: {count}\n")

        # ---------------------------------------------------------
        # FK orphan audit
        # ---------------------------------------------------------

        handle.write(section("17. FOREIGN KEY ORPHAN AUDIT"))

        with engine.connect() as connection:
            fk_rows = fetch_all_dicts(
                connection,
                """
                SELECT
                    tc.table_schema,
                    tc.table_name,
                    tc.constraint_name,
                    kcu.column_name,
                    ccu.table_schema
                        AS foreign_table_schema,
                    ccu.table_name
                        AS foreign_table_name,
                    ccu.column_name
                        AS foreign_column_name
                FROM information_schema.table_constraints
                    AS tc
                JOIN information_schema.key_column_usage
                    AS kcu
                  ON tc.constraint_name =
                        kcu.constraint_name
                 AND tc.table_schema =
                        kcu.table_schema
                JOIN information_schema.constraint_column_usage
                    AS ccu
                  ON ccu.constraint_name =
                        tc.constraint_name
                 AND ccu.table_schema =
                        tc.table_schema
                WHERE tc.constraint_type =
                        'FOREIGN KEY'
                  AND tc.table_schema =
                        'public'
                ORDER BY
                    tc.table_name,
                    tc.constraint_name,
                    kcu.ordinal_position
                """,
            )

            # The current app uses single-column FKs. Grouping keeps the
            # report readable and avoids pretending composite FKs are simple.
            grouped: dict[
                tuple[str, str],
                list[dict],
            ] = {}

            for row in fk_rows:
                key = (
                    row["table_name"],
                    row["constraint_name"],
                )

                grouped.setdefault(
                    key,
                    [],
                ).append(row)

            for (
                table_name,
                constraint_name,
            ), columns in grouped.items():
                if len(columns) != 1:
                    handle.write(
                        f"{table_name}.{constraint_name}: "
                        "composite FK; orphan audit skipped\n"
                    )
                    continue

                row = columns[0]

                local_table = row["table_name"]

                local_column = row["column_name"]

                foreign_table = row["foreign_table_name"]

                foreign_column = row["foreign_column_name"]

                def q(identifier: str) -> str:
                    return (
                        '"'
                        + identifier.replace(
                            '"',
                            '""',
                        )
                        + '"'
                    )

                orphan_sql = (
                    f"SELECT COUNT(*) "
                    f"FROM {q(local_table)} AS child "
                    f"LEFT JOIN {q(foreign_table)} AS parent "
                    f"ON child.{q(local_column)} = "
                    f"parent.{q(foreign_column)} "
                    f"WHERE child.{q(local_column)} IS NOT NULL "
                    f"AND parent.{q(foreign_column)} IS NULL"
                )

                orphan_count = connection.execute(text(orphan_sql)).scalar_one()

                handle.write(
                    f"{local_table}.{local_column} -> "
                    f"{foreign_table}.{foreign_column}: "
                    f"orphans={orphan_count}\n"
                )

        # ---------------------------------------------------------
        # Application-specific consistency checks
        # ---------------------------------------------------------

        handle.write(section("18. FARM PLATFORM CONSISTENCY CHECKS"))

        checks = {
            "crop_cycles whose field and season belong to different farms": """
                SELECT COUNT(*)
                FROM crop_cycles AS cc
                JOIN fields AS f
                  ON f.id = cc.field_id
                JOIN seasons AS s
                  ON s.id = cc.season_id
                WHERE f.farm_id <> s.farm_id
                """,
            "activities linked to crop cycle from another field": """
                SELECT COUNT(*)
                FROM activities AS a
                JOIN crop_cycles AS cc
                  ON cc.id = a.crop_cycle_id
                WHERE a.crop_cycle_id IS NOT NULL
                  AND a.field_id <> cc.field_id
                """,
            "media linked to activity from another field": """
                SELECT COUNT(*)
                FROM media_assets AS ma
                JOIN activities AS a
                  ON a.id = ma.activity_id
                WHERE ma.activity_id IS NOT NULL
                  AND ma.field_id <> a.field_id
                """,
            "media linked to crop cycle from another field": """
                SELECT COUNT(*)
                FROM media_assets AS ma
                JOIN crop_cycles AS cc
                  ON cc.id = ma.crop_cycle_id
                WHERE ma.crop_cycle_id IS NOT NULL
                  AND ma.field_id <> cc.field_id
                """,
            "satellite observations without any metric rows": """
                SELECT COUNT(*)
                FROM satellite_observations AS so
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM satellite_metrics AS sm
                    WHERE sm.satellite_observation_id =
                        so.id
                )
                """,
            "satellite metric rows with non-GCS raster URI": """
                SELECT COUNT(*)
                FROM satellite_metrics
                WHERE raster_uri IS NULL
                   OR raster_uri NOT LIKE 'gs://%'
                """,
            "satellite metric rows outside canonical users/ hierarchy": """
                SELECT COUNT(*)
                FROM satellite_metrics
                WHERE raster_uri LIKE 'gs://%'
                  AND raster_uri NOT LIKE
                        'gs://%/users/%'
                """,
            "media outside canonical users/ hierarchy": """
                SELECT COUNT(*)
                FROM media_assets
                WHERE object_key NOT LIKE
                    'users/%'
                """,
            "media rows missing preview_object_key": """
                SELECT COUNT(*)
                FROM media_assets
                WHERE preview_object_key IS NULL
                """,
        }

        with engine.connect() as connection:
            for label, sql in checks.items():
                try:
                    count = connection.execute(text(sql)).scalar_one()

                    handle.write(f"{label}: {count}\n")

                except Exception as error:
                    handle.write(
                        f"{label}: ERROR " f"{type(error).__name__}: {error}\n"
                    )

        handle.write(
            "\n--- SATELLITE METRIC COVERAGE (INFORMATIONAL) ---\n"
        )

        with engine.connect() as connection:
            rows = fetch_all_dicts(
                connection,
                """
                SELECT
                    metric_count,
                    COUNT(*) AS observation_count
                FROM (
                    SELECT
                        so.id,
                        COUNT(sm.id) AS metric_count
                    FROM satellite_observations AS so
                    LEFT JOIN satellite_metrics AS sm
                      ON sm.satellite_observation_id = so.id
                    GROUP BY so.id
                ) AS coverage
                GROUP BY metric_count
                ORDER BY metric_count
                """,
            )

            write_rows(
                handle,
                rows,
            )

        handle.write(
            "Note: historical observations with only NDVI are valid "
            "legacy runs and are intentionally not backfilled.\n"
        )

        # ---------------------------------------------------------
        # NULL / duplicate audit for key identity columns
        # ---------------------------------------------------------

        handle.write(section("19. KEY NULL / DUPLICATE AUDIT"))

        audits = {
            "duplicate users.firebase_uid": """
                SELECT COUNT(*)
                FROM (
                    SELECT firebase_uid
                    FROM users
                    GROUP BY firebase_uid
                    HAVING COUNT(*) > 1
                ) AS x
                """,
            "duplicate users.phone_e164": """
                SELECT COUNT(*)
                FROM (
                    SELECT phone_e164
                    FROM users
                    GROUP BY phone_e164
                    HAVING COUNT(*) > 1
                ) AS x
                """,
            "duplicate satellite observation field+scene": """
                SELECT COUNT(*)
                FROM (
                    SELECT field_id, scene_id
                    FROM satellite_observations
                    GROUP BY field_id, scene_id
                    HAVING COUNT(*) > 1
                ) AS x
                """,
            "duplicate satellite metric observation+type": """
                SELECT COUNT(*)
                FROM (
                    SELECT
                        satellite_observation_id,
                        metric_type
                    FROM satellite_metrics
                    GROUP BY
                        satellite_observation_id,
                        metric_type
                    HAVING COUNT(*) > 1
                ) AS x
                """,
            "duplicate media object_key": """
                SELECT COUNT(*)
                FROM (
                    SELECT object_key
                    FROM media_assets
                    GROUP BY object_key
                    HAVING COUNT(*) > 1
                ) AS x
                """,
        }

        with engine.connect() as connection:
            for label, sql in audits.items():
                try:
                    count = connection.execute(text(sql)).scalar_one()

                    handle.write(f"{label}: {count}\n")

                except Exception as error:
                    handle.write(
                        f"{label}: ERROR " f"{type(error).__name__}: {error}\n"
                    )

        handle.write(section("20. END OF REPORT"))

        handle.write("Upload this entire file back to ChatGPT for review.\n")

    print(f"Created: {output_path}")


if __name__ == "__main__":
    main()
