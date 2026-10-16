"""Owner/URL/response boundary checks for private satellite preview routes."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import private_satellite_previews as previews


def test_denied_owner_prevents_any_metric_read_or_upstream(monkeypatch):
    field_id, observation_id = uuid4(), uuid4()
    user = SimpleNamespace(id=uuid4())
    db = SimpleNamespace(scalar=lambda _: pytest.fail("Unowned metric must not be queried"))

    def reject(*_args, **_kwargs):
        raise HTTPException(status_code=404, detail="Field not found.")

    monkeypatch.setattr(previews, "get_owned_field", reject)
    monkeypatch.setattr(previews, "_tiler_get", lambda *_a, **_k: pytest.fail("Do not call tiler"))
    with pytest.raises(HTTPException) as exc:
        previews.metric_preview(field_id, observation_id, "ndvi", db, user)
    assert exc.value.status_code == 404


def test_unsupported_metric_does_not_contact_tiler(monkeypatch):
    field_id, observation_id = uuid4(), uuid4()
    user = SimpleNamespace(id=uuid4())
    db = SimpleNamespace(scalar=lambda _: pytest.fail("Unsupported metric must not query"))
    monkeypatch.setattr(previews, "get_owned_field", lambda *_a, **_k: None)
    with pytest.raises(HTTPException) as exc:
        previews.metric_preview(field_id, observation_id, "unknown_index", db, user)
    assert exc.value.status_code == 404


def test_private_preview_uses_canonical_database_uri_not_request_uri(monkeypatch):
    field_id, observation_id = uuid4(), uuid4()
    user = SimpleNamespace(id=uuid4())
    canonical = "gs://private-bucket/users/owned/farms/test/ndvi.tif"
    db = SimpleNamespace(scalar=lambda _: SimpleNamespace(raster_uri=canonical))
    calls = []
    monkeypatch.setattr(previews, "get_owned_field", lambda *_a, **_k: None)

    def capture(route, params, *, expect_png):
        calls.append((route, params.copy(), expect_png))
        return b"\x89PNG\r\n\x1a\n..."

    monkeypatch.setattr(previews, "_tiler_get", capture)
    response = previews.metric_preview(field_id, observation_id, "ndvi", db, user)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert calls[0][1]["url"] == canonical
    assert calls[0][1]["colormap_name"] == "rdylgn"
    assert calls[0][1]["rescale"] == "-0.2,0.9"
    assert calls[0][2] is True


def test_reject_arbitrary_tiler_host_without_network(monkeypatch):
    monkeypatch.setattr(previews.settings, "satellite_tiler_internal_url", "https://example.net")
    monkeypatch.setattr(previews, "urlopen", lambda *_a, **_k: pytest.fail("SSRF blocked"))
    with pytest.raises(HTTPException) as exc:
        previews._tiler_get("/cog/preview.png", {"url": "gs://secret"}, expect_png=True)
    assert exc.value.status_code == 503


def test_change_preview_checks_both_observations(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    ids = [uuid4(), uuid4(), uuid4()]
    checked = []

    def resolve(db, current_user, field_id, observation_id, metric_type):
        checked.append(observation_id)
        if observation_id == ids[2]:
            raise HTTPException(status_code=404, detail="Metric not found")
        return SimpleNamespace(raster_uri=str(observation_id))

    monkeypatch.setattr(previews, "_owned_metric", resolve)
    monkeypatch.setattr(previews, "_tiler_get", lambda *_a, **_k: pytest.fail("No unauthorized rendering"))
    with pytest.raises(HTTPException) as exc:
        previews.change_preview(ids[0], ids[1], ids[2], "ndvi", None, user, max_abs=0.25)
    assert exc.value.status_code == 404
    assert checked == [ids[1], ids[2]]
