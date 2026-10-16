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
