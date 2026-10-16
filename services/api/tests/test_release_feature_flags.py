"""Production feature gates hide optional integrations without disabling auth."""
from unittest.mock import Mock

from fastapi import APIRouter

from app.api.router import include_whatsapp_routes
from app.core.config import Settings, settings


def test_whatsapp_defaults_off():
    assert Settings.model_fields["whatsapp_enabled"].default is False
    assert Settings(
        _env_file=None,
        database_url="postgresql+psycopg://unused:unused@localhost/unused",
        firebase_project_id="unit-test",
        gcs_bucket_name="unit-test",
        whatsapp_enabled=False,
    ).whatsapp_enabled is False


def test_whatsapp_disabled_registers_no_optional_routes():
    router = Mock(spec=APIRouter)
    include_whatsapp_routes(router, enabled=False)
    router.include_router.assert_not_called()

    if not settings.whatsapp_enabled:
        from app.main import app
        paths = app.openapi()["paths"]
        assert not any("/whatsapp" in path for path in paths)
        assert "/api/v1/auth/me" in paths
        assert "/api/v1/farms" in paths


def test_whatsapp_enabled_registers_both_routers():
    router = Mock(spec=APIRouter)
    include_whatsapp_routes(router, enabled=True)
    prefixes = [call.args[0].prefix for call in router.include_router.call_args_list]
    assert prefixes == ["/webhooks/whatsapp", "/whatsapp/link"]
