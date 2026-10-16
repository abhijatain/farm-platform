"""Explicit, guarded reset of a dedicated Farm Platform test deployment.

Default is a READ-ONLY inventory:
  uv run python -m app.cli.reset_test_data

If Firebase/GCS will be cleaned manually, inventory and reset only the DB:
  uv run python -m app.cli.reset_test_data --database-only
  uv run python -m app.cli.reset_test_data --database-only --apply \\
    --confirm-db-host "POSTGRES_HOST" --confirm-db-name "DB_NAME" \\
    --acknowledge "PERMANENTLY ERASE FARM PLATFORM DATABASE DATA"

To execute, all three *actual* resource names and the literal acknowledgement
must be supplied. Never run for a shared Firebase project, shared GCS bucket
or a DB that contains non-Farm-Platform tables.

  uv run python -m app.cli.reset_test_data --apply \
    --confirm-db-host "POSTGRES_HOST" --confirm-db-name "DB_NAME" \
    --confirm-firebase-project "FIREBASE_PROJECT_ID" \
    --confirm-gcs-bucket "EXCLUSIVE_TEST_BUCKET" \
    --acknowledge "PERMANENTLY ERASE ALL DEMO USERS DATA AND OBJECTS"

Keeps Alembic/PostGIS schema. Does not delete Firebase project, GCS bucket,
or Firebase/Meta provider configuration. Google Cloud retention/soft-delete
policies may prevent immediately irreversible object deletion.
Stop API and all workers before applying.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

ACKNOWLEDGEMENT = "PERMANENTLY ERASE ALL DEMO USERS DATA AND OBJECTS"
DATABASE_ACKNOWLEDGEMENT = "PERMANENTLY ERASE FARM PLATFORM DATABASE DATA"
ALLOWED_ENVIRONMENTS = frozenset({"development", "test", "testing", "demo", "staging"})
PROTECTED_TABLES = frozenset({"alembic_version", "spatial_ref_sys"})

# PR #16's WhatsApp outbox migration was run locally before that PR was
# abandoned. The table is legitimately ours, but its ORM model/migration is
# absent from main. Permit a DATA-ONLY reset of that exact known table if it
# structurally matches the original migration; reject any other orphan table.
LEGACY_OUTBOX_COLUMNS = frozenset({
    "id", "inbound_message_id", "user_id", "recipient_wa_id",
    "phone_number_id", "payload", "status", "attempts", "available_at",
    "reply_before", "lease_until", "sent_at", "meta_message_id",
    "last_error", "created_at",
})



@dataclass(frozen=True)
class ResetTargets:
    db_host: str
    db_name: str
    firebase_project: str
    gcs_bucket: str
    environment: str


def read_targets(settings) -> ResetTargets:
    from sqlalchemy.engine import make_url
    url = make_url(settings.database_url)
    return ResetTargets(
        db_host=url.host or "localhost",
        db_name=url.database or "",
        firebase_project=settings.firebase_project_id,
        gcs_bucket=settings.gcs_bucket_name,
        environment=settings.environment.strip().lower(),
    )


def validate_apply_targets(target: ResetTargets, args) -> None:
    """An explicit approval of every unique resource prevents wrong-project wipes."""
    if target.environment not in ALLOWED_ENVIRONMENTS:
        raise RuntimeError(
            "Refusing reset outside a named nonproduction environment; "
            "create a separate test project instead of bypassing this check."
        )
    required = {
        "--confirm-db-host": (args.confirm_db_host, target.db_host),
        "--confirm-db-name": (args.confirm_db_name, target.db_name),
        "--confirm-firebase-project": (args.confirm_firebase_project, target.firebase_project),
        "--confirm-gcs-bucket": (args.confirm_gcs_bucket, target.gcs_bucket),
    }
    mismatched=[key for key,(supplied,actual) in required.items()
                if not supplied or supplied != actual]
    if mismatched:
        raise RuntimeError("Resource identifiers missing or mismatched: " + ", ".join(mismatched))
    if args.acknowledge != ACKNOWLEDGEMENT:
        raise RuntimeError("Irreversible erase acknowledgement is missing or incorrect.")


def validate_database_only_targets(target: ResetTargets, args) -> None:
    """Authorize JUST the known nonproduction PostgreSQL database."""
    if target.environment not in ALLOWED_ENVIRONMENTS:
        raise RuntimeError("Refusing database reset outside a nonproduction environment.")
    if not args.confirm_db_host or args.confirm_db_host != target.db_host:
        raise RuntimeError("Database host confirmation missing or mismatched.")
    if not args.confirm_db_name or args.confirm_db_name != target.db_name:
        raise RuntimeError("Database name confirmation missing or mismatched.")
    if args.acknowledge != DATABASE_ACKNOWLEDGEMENT:
        raise RuntimeError("Database-only irreversible erase acknowledgement is incorrect.")
    if args.confirm_firebase_project or args.confirm_gcs_bucket:
        raise RuntimeError("Database-only mode does not accept cloud deletion arguments.")


def verify_legacy_whatsapp_outbox(inspector) -> bool:
    """Verify the abandoned PR #16 outbox before allowing its rows to be erased.

    Require the original migration's exact set of columns, UUID id PK,
    and user_id -> users.id foreign key. This does NOT adopt its migration
    or silently allow arbitrary unknown tables.
    """
    columns = {str(row["name"]) for row in inspector.get_columns(
        "whatsapp_outbox", schema="public"
    )}
    primary = inspector.get_pk_constraint("whatsapp_outbox", schema="public")
    foreign_keys = inspector.get_foreign_keys("whatsapp_outbox", schema="public")
    owned_by_users = any(
        fk.get("referred_table") == "users"
        and fk.get("constrained_columns") == ["user_id"]
        and fk.get("referred_columns") == ["id"]
        for fk in foreign_keys
    )
    return (
        columns == LEGACY_OUTBOX_COLUMNS
        and primary.get("constrained_columns") == ["id"]
        and owned_by_users
    )


def application_tables(engine):
    """Only wipe registered app tables and structurally verified legacy outbox."""
    from sqlalchemy import inspect
    import app.models  # noqa: F401 — register all application models
    from app.db.base import Base

    inspector = inspect(engine)
    expected = set(Base.metadata.tables.keys())
    existing = set(inspector.get_table_names(schema="public"))
    missing = expected - existing
    legacy: set[str] = set()
    if "whatsapp_outbox" in existing and "whatsapp_outbox" not in expected:
        if not verify_legacy_whatsapp_outbox(inspector):
            raise RuntimeError(
                "Unknown whatsapp_outbox schema; data reset refused. "
                "Inspect the table and its foreign keys before proceeding."
            )
        legacy.add("whatsapp_outbox")
    unexpected = existing - expected - PROTECTED_TABLES - legacy
    if missing or unexpected:
        raise RuntimeError(
            "Database schema mismatch; no tables will be cleared. "
            f"Missing models: {sorted(missing)}; unexpected public tables: {sorted(unexpected)}"
        )
    if not expected:
        raise RuntimeError("No application tables found; refusing to erase.")
    if legacy:
        print("Recognized legacy Farm Platform WhatsApp outbox; its rows will be included.")
    return sorted(expected | legacy)


def db_inventory(engine,tables):
    from sqlalchemy import text
    with engine.connect() as conn:
        return {t:conn.scalar(text(f'SELECT COUNT(*) FROM "public"."{t}"')) for t in tables}


def firebase_app_and_user_count(settings):
    from firebase_admin import auth
    from app.core.firebase import get_firebase_app
    app = get_firebase_app()
    # The Firebase app must be configured for exactly the target project.
    if app.project_id != settings.firebase_project_id:
        raise RuntimeError("Firebase Admin app project does not match configured project.")
    return app, sum(1 for _ in auth.list_users(app=app).iterate_all())


def gcs_client_and_object_count(settings):
    from app.storage.gcs import GCSStorage
    gcs = GCSStorage(
        bucket_name=settings.gcs_bucket_name,
        project_id=settings.gcs_project_id,
        credentials_path=settings.gcs_credentials_path,
    )
    bucket = gcs.bucket
    bucket.reload(client=gcs.client)
    count = sum(1 for _ in gcs.client.list_blobs(bucket, versions=True))
    return gcs, count


def delete_bucket_objects(gcs) -> int:
    """Remove every accessible generation, not only current objects."""
    removed = 0
    for blob in gcs.client.list_blobs(gcs.bucket, versions=True):
        if blob.generation is None:
            raise RuntimeError("GCS object has no generation; refusing ambiguous deletion.")
        blob.delete(client=gcs.client, if_generation_match=int(blob.generation))
        removed += 1
    return removed


def delete_firebase_users(app) -> int:
    from firebase_admin import auth
    removed = 0
    batch = []
    def flush():
        nonlocal removed
        if not batch:
            return
        result = auth.delete_users(batch, app=app)
        removed += result.success_count
        if result.failure_count:
            raise RuntimeError(
                f"Firebase partially deleted users ({result.success_count} successful, "
                f"{result.failure_count} failures). Re-run inventory and investigate."
            )
        batch.clear()
    for user in auth.list_users(app=app).iterate_all():
        batch.append(user.uid)
        if len(batch) >= 1000:
            flush()
    flush()
    return removed


def truncate_application_data(engine,tables) -> None:
    # All known Farm Platform tables are included in the same transaction;
    # intentionally NO CASCADE, so external dependent tables cause refusal.
    # The schema, PostGIS spatial_ref_sys and alembic_version are preserved.
    names = ", ".join(f'"public"."{name}"' for name in tables)
    with engine.begin() as conn:
        conn.exec_driver_sql(f"TRUNCATE TABLE {names} RESTART IDENTITY")


def run_database_only(args, target: ResetTargets, engine) -> int:
    """Inventory or delete ONLY PostgreSQL app rows. Never contact Firebase/GCS."""
    if args.apply:
        validate_database_only_targets(target, args)
    tables = application_tables(engine)
    counts = db_inventory(engine, tables)
    print("DATABASE application rows:", counts)
    print("Firebase Auth users: NOT checked or changed (manual cleanup).")
    print("GCS objects: NOT checked or changed (manual cleanup).")
    print("Database schema, PostGIS and Alembic history will be preserved.")
    if not args.apply:
        print("DRY RUN ONLY. No data was deleted.")
        return 0

    truncate_application_data(engine, tables)
    after = db_inventory(engine, tables)
    if any(after.values()):
        raise RuntimeError(f"Database-only reset verification failed: {after}")
    print("PASS: 0 Farm Platform application rows in PostgreSQL.")
    print("Firebase users and GCS must be verified/deleted separately.")
    return 0


def run(args) -> int:
    from app.core.config import settings
    from app.db.session import engine

    targets=read_targets(settings)
    print("RESET TARGETS (passwords and phone numbers not shown)")
    print("  Database host:",targets.db_host)
    print("  Database name:",targets.db_name)
    print("  Firebase project:",targets.firebase_project)
    print("  GCS bucket:",targets.gcs_bucket)
    print("  Environment:",targets.environment)

    if args.database_only:
        return run_database_only(args, targets, engine)

    # On --apply, validate all identifiers BEFORE talking to Firebase or GCS.
    if args.apply:
        validate_apply_targets(targets,args)

    tables=application_tables(engine)
    records=db_inventory(engine,tables)
    print("DATABASE:",records)
    print("Connecting to configured Firebase and GCS for a read-only inventory...")
    app,user_count=firebase_app_and_user_count(settings)
    gcs,object_count=gcs_client_and_object_count(settings)
    print("FIREBASE users:",user_count)
    print("GCS active + noncurrent object generations:",object_count)
    print("Schema and migration history will be preserved.")

    if not args.apply:
        print("DRY RUN ONLY. Nothing was deleted.")
        print("Stop API, satellite workers, media workers and any scheduled jobs before applying.")
        print("WARNING: GCS retention/soft-delete policies may retain recoverable versions after delete.")
        return 0

    print("ERASING the explicitly confirmed Firebase project, GCS bucket, and DB.")
    print("All target resources must be exclusively owned by this demo deployment.")
    removed_objects=delete_bucket_objects(gcs)
    removed_users=delete_firebase_users(app)
    truncate_application_data(engine,tables)

    print("Deleted object generations:",removed_objects)
    print("Deleted Firebase Auth users:",removed_users)
    print("Truncated Farm Platform data tables:",len(tables))
    # Verify actual API-visible state; soft-deleted/retained objects may not
    # appear in ordinary listings and remain controlled by GCS bucket policy.
    remaining_db=db_inventory(engine,tables)
    _app,remaining_users=firebase_app_and_user_count(settings)
    _gcs,remaining_objects=gcs_client_and_object_count(settings)
    if any(remaining_db.values()) or remaining_users or remaining_objects:
        raise RuntimeError(
            "Reset did not verify empty; check DB, Firebase and GCS counts. "
            "Some resources may be protected by retention policies."
        )
    print("PASS: 0 application rows, 0 Firebase Auth users, 0 listed GCS object generations.")
    print("Next: sign in with a real test phone again, then run seed_four_crop_demo.")
    return 0


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply",action="store_true",help="Erase confirmed targets; default is read-only.")
    parser.add_argument("--database-only",action="store_true",help="Skip all Firebase/GCS calls; inventory/erase PostgreSQL application rows only.")
    parser.add_argument("--confirm-db-host")
    parser.add_argument("--confirm-db-name")
    parser.add_argument("--confirm-firebase-project")
    parser.add_argument("--confirm-gcs-bucket")
    parser.add_argument("--acknowledge")
    args=parser.parse_args()
    raise SystemExit(run(args))


if __name__=="__main__":
    main()
