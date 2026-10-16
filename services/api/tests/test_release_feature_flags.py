"""Production feature gates must hide optional integrations, not only their UI."""
from fastapi import APIRouter

from app.api.router import api_router, include_whatsapp_routes
from app.core.config import Settings, settings


def test_whatsapp_is_off_by_default():
    config = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://unused:unused@localhost/unused",
        firebase_project_id="unit-test",
        gcs_bucket_name="unit-test",
        whatsapp_enabled=False,
    )
    assert config.whatsapp_enabled is False


def test_whatsapp_disabled_has_no_registered_routes():
    router = APIRouter()
    include_whatsapp_routes(router, enabled=False)
    assert router.routes == []
    if not settings.whatsapp_enabled:
        paths = [route.path for route in api_router.routes]
        assert not any("/whatsapp" in path for path in paths)
        assert "/auth/me" in paths
        assert "/farms" in paths


def test_whatsapp_enabled_registers_exact_routes():
    router = APIRouter()
    include_whatsapp_routes(router, enabled=True)
    paths = {route.path for route in router.routes}
    assert "/webhooks/whatsapp" in paths
    assert "/whatsapp/link" in paths
    assert "/whatsapp/link/start" in paths
