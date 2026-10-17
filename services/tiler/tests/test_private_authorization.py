"""Raw TiTiler endpoints are never available without an API-to-tiler secret."""
from pydantic import SecretStr
from fastapi.testclient import TestClient

from farm_tiler.main import app
from farm_tiler.config import settings


def test_tiler_rejects_public_access_to_every_cog_and_change_route(monkeypatch):
    monkeypatch.setattr(settings, "satellite_tiler_shared_token", SecretStr("test-secret-long-enough"))
    with TestClient(app) as client:
        for path in (
            "/cog/info?url=gs://private-bucket/users/a/test.tif",
            "/cog/tiles/WebMercatorQuad/1/0/0.png?url=gs://private-bucket/users/a/test.tif",
            "/change/summary?before=x&after=y&threshold=0.5",
            "/change/preview.png?before=x&after=y&max_abs=0.3",
        ):
            assert client.get(path).status_code == 401
            assert client.get(path, headers={"X-Farm-Internal-Token":"wrong"}).status_code == 401


def test_tiler_fails_closed_if_shared_secret_missing(monkeypatch):
    monkeypatch.setattr(settings, "satellite_tiler_shared_token", None)
    with TestClient(app) as client:
        assert client.get("/cog/info", headers={"X-Farm-Internal-Token": "anything"}).status_code == 503
        assert client.get("/health").status_code == 200
