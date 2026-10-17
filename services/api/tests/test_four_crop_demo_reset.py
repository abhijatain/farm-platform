"""The dangerous test reset must require exact resource identifiers.

No Firebase, GCS, or PostgreSQL connection is made in these unit tests.
"""
from argparse import Namespace

import pytest

from app.cli.reset_test_data import (
    ACKNOWLEDGEMENT, ResetTargets, read_targets, validate_apply_targets,
)


@pytest.fixture
def targets():
    return ResetTargets(
        db_host="127.0.0.1", db_name="farm_test", firebase_project="farm-test-project",
        gcs_bucket="farm-test-private-bucket", environment="test",
    )


def args(**overrides):
    values = dict(
        confirm_db_host="127.0.0.1", confirm_db_name="farm_test",
        confirm_firebase_project="farm-test-project",
        confirm_gcs_bucket="farm-test-private-bucket",
        acknowledge=ACKNOWLEDGEMENT,
    )
    values.update(overrides)
    return Namespace(**values)


def test_exact_confirmation_required(targets):
    validate_apply_targets(targets,args())
    for argument in ("confirm_db_host","confirm_db_name",
                     "confirm_firebase_project","confirm_gcs_bucket","acknowledge"):
        with pytest.raises(RuntimeError):
            validate_apply_targets(targets,args(**{argument:"incorrect"}))


def test_refuses_production_even_if_confirmed(targets):
    from dataclasses import replace
    with pytest.raises(RuntimeError,match="nonproduction"):
        validate_apply_targets(replace(targets,environment="production"),args())


def test_db_url_never_prints_password():
    class Config:
        database_url="postgresql+psycopg://farmer:secret_password@db.internal:5432/farm_test"
        firebase_project_id="farm-test-project"
        gcs_bucket_name="farm-test-private-bucket"
        environment="test"
    got=read_targets(Config)
    assert got.db_host=="db.internal"
    assert got.db_name=="farm_test"
    assert "secret_password" not in str(got)


def test_exact_known_whatsapp_outbox_schema_is_recognized():
    from app.cli.reset_test_data import (
        LEGACY_OUTBOX_COLUMNS, verify_legacy_whatsapp_outbox,
    )

    class Inspector:
        def get_columns(self, table, schema):
            assert table == "whatsapp_outbox" and schema == "public"
            return [{"name": name} for name in sorted(LEGACY_OUTBOX_COLUMNS)]

        def get_pk_constraint(self, table, schema):
            return {"constrained_columns": ["id"]}

        def get_foreign_keys(self, table, schema):
            return [{"referred_table": "users",
                     "constrained_columns": ["user_id"],
                     "referred_columns": ["id"]}]

    assert verify_legacy_whatsapp_outbox(Inspector()) is True


def test_unknown_whatsapp_outbox_layout_is_not_whitelisted():
    from app.cli.reset_test_data import (
        LEGACY_OUTBOX_COLUMNS, verify_legacy_whatsapp_outbox,
    )
    class WrongInspector:
        def get_columns(self, table, schema):
            return [{"name": name} for name in LEGACY_OUTBOX_COLUMNS - {"payload"}]
        def get_pk_constraint(self, table, schema):
            return {"constrained_columns": ["id"]}
        def get_foreign_keys(self, table, schema):
            return []
    assert verify_legacy_whatsapp_outbox(WrongInspector()) is False


def test_database_only_requires_exact_db_approval(targets):
    from app.cli.reset_test_data import (
        DATABASE_ACKNOWLEDGEMENT, validate_database_only_targets,
    )
    good = args(
        confirm_firebase_project=None,
        confirm_gcs_bucket=None,
        acknowledge=DATABASE_ACKNOWLEDGEMENT,
    )
    validate_database_only_targets(targets, good)
    for flag in ("confirm_db_host", "confirm_db_name", "acknowledge"):
        wrong = Namespace(**{**vars(good), flag: "wrong"})
        with pytest.raises(RuntimeError):
            validate_database_only_targets(targets, wrong)
    with pytest.raises(RuntimeError, match="cloud"):
        validate_database_only_targets(
            targets, Namespace(**{**vars(good), "confirm_gcs_bucket": "farm-test-private-bucket"})
        )


def test_database_only_never_connects_to_cloud(monkeypatch, targets, capsys):
    from app.cli import reset_test_data as reset
    sentinel_engine = object()
    monkeypatch.setattr(reset, "application_tables", lambda engine: ["users", "fields"])
    monkeypatch.setattr(reset, "db_inventory", lambda engine, tables: {"users": 2, "fields": 9})
    def forbidden(*_a, **_kw):
        raise AssertionError("database-only must not contact cloud services")
    monkeypatch.setattr(reset, "firebase_app_and_user_count", forbidden)
    monkeypatch.setattr(reset, "gcs_client_and_object_count", forbidden)
    monkeypatch.setattr(reset, "truncate_application_data", forbidden)
    data = args(database_only=True, apply=False)
    assert reset.run_database_only(data, targets, sentinel_engine) == 0
    stdout = capsys.readouterr().out
    assert "2" in stdout and "9" in stdout
    assert "DRY RUN ONLY" in stdout


def test_database_only_apply_truncates_only_verified_app_tables(monkeypatch, targets):
    from app.cli import reset_test_data as reset
    from app.cli.reset_test_data import DATABASE_ACKNOWLEDGEMENT
    engine = object()
    state = {"deleted": False}
    monkeypatch.setattr(reset, "application_tables", lambda _: ["users", "fields", "whatsapp_outbox"])
    monkeypatch.setattr(reset, "db_inventory", lambda _engine, _tables: {
        "users": 0 if state["deleted"] else 2,
        "fields": 0 if state["deleted"] else 9,
        "whatsapp_outbox": 0,
    })
    def truncate(_engine, tables):
        assert _engine is engine
        assert tables == ["users", "fields", "whatsapp_outbox"]
        state["deleted"] = True
    monkeypatch.setattr(reset, "truncate_application_data", truncate)
    def forbidden(*_args, **_kwargs):
        raise AssertionError("cloud access forbidden during database-only reset")
    monkeypatch.setattr(reset, "firebase_app_and_user_count", forbidden)
    monkeypatch.setattr(reset, "gcs_client_and_object_count", forbidden)
    data = args(
        database_only=True, apply=True,
        confirm_firebase_project=None, confirm_gcs_bucket=None,
        acknowledge=DATABASE_ACKNOWLEDGEMENT,
    )
    assert reset.run_database_only(data, targets, engine) == 0
    assert state["deleted"] is True


def test_database_only_refuses_production_even_if_confirmed(targets):
    from dataclasses import replace
    from app.cli.reset_test_data import (
        DATABASE_ACKNOWLEDGEMENT, validate_database_only_targets,
    )
    inputs = args(
        confirm_firebase_project=None, confirm_gcs_bucket=None,
        acknowledge=DATABASE_ACKNOWLEDGEMENT,
    )
    with pytest.raises(RuntimeError, match="nonproduction"):
        validate_database_only_targets(replace(targets, environment="production"), inputs)
