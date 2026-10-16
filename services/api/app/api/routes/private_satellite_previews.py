"""Serve only owner-authorized raster previews through the local tiler.

The browser never receives private GCS paths, tiler URLs, or signed storage
URLs. This endpoint accepts IDs and bounded numeric options, resolves canonical
satellite metric rows after the Firebase user owns the field, and relays a
small generated image or numeric summary from an internal loopback tiler.
"""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.core.config import settings
from app.models.satellite_metric import SatelliteMetric
from app.models.satellite_observation import SatelliteObservation
from app.services.ownership import get_owned_field

router = APIRouter(tags=["private satellite previews"])

# Color ranges match the map UI's fixed display scales, NOT agronomic
# thresholds. Never accept a user-supplied GCS URI or colormap name.
DISPLAY = {
    "ndvi": (-0.2, 0.9, "rdylgn"),
    "gndvi": (-0.2, 0.85, "rdylgn"),
    "evi2": (-0.1, 1.0, "rdylgn"),
    "savi": (-0.2, 1.0, "rdylgn"),
    "msavi": (-0.2, 1.0, "rdylgn"),
    "ndre": (-0.2, 0.65, "rdylgn"),
    "ccci": (-0.5, 1.5, "viridis"),
    "reci": (-0.5, 3.0, "viridis"),
    "mcari": (-0.1, 0.5, "viridis"),
    "ndmi": (-0.6, 0.8, "rdbu"),
    "ndwi": (-0.8, 0.8, "rdbu"),
    "bsi": (-0.6, 0.6, "viridis"),
    "ndti": (-0.4, 0.5, "viridis"),
    "sar_vv_db": (-25.0, 0.0, "viridis"),
    "sar_vh_db": (-32.0, -5.0, "viridis"),
    "sar_vv_vh_ratio": (1.0, 20.0, "viridis"),
    "sar_rvi": (0.0, 2.0, "viridis"),
    "lst_c": (10.0, 50.0, "inferno"),
}
MAX_PREVIEW_BYTES = 5 * 1024 * 1024
MAX_SUMMARY_BYTES = 1024 * 1024


def _owned_metric(
    db: DBSession,
    current_user: CurrentUser,
    field_id: UUID,
    observation_id: UUID,
    metric_type: str,
) -> SatelliteMetric:
    get_owned_field(db, current_user.id, field_id)
    if metric_type not in DISPLAY:
        raise HTTPException(status_code=404, detail="Satellite metric not found.")
    metric = db.scalar(
        select(SatelliteMetric)
        .join(
            SatelliteObservation,
            SatelliteObservation.id == SatelliteMetric.satellite_observation_id,
        )
        .where(
            SatelliteObservation.field_id == field_id,
            SatelliteObservation.id == observation_id,
            SatelliteMetric.metric_type == metric_type,
        )
    )
    if metric is None or not metric.raster_uri:
        raise HTTPException(status_code=404, detail="Satellite metric not found.")
    return metric


def _tiler_get(route: str, params: dict[str, str], *, expect_png: bool) -> bytes:
    base = settings.satellite_tiler_internal_url.rstrip("/")
    parts = urlsplit(base)
    # A misconfigured URL must not turn this endpoint into an SSRF proxy.
    if parts.scheme != "http" or parts.hostname not in {"127.0.0.1", "localhost", "::1"} or parts.username or parts.password or parts.path or parts.query:
        raise HTTPException(status_code=503, detail="Internal tiler is not safely configured.")
    uri = f"{base}{route}?{urlencode(params)}"
    expected_type = "image/png" if expect_png else "application/json"
    limit = MAX_PREVIEW_BYTES if expect_png else MAX_SUMMARY_BYTES
    try:
        with urlopen(Request(uri, headers={"Accept": expected_type}), timeout=20) as result:
            if result.status != 200 or result.headers.get_content_type() != expected_type:
                raise HTTPException(status_code=502, detail="Tiler returned an invalid response.")
            data = result.read(limit + 1)
            if len(data) > limit:
                raise HTTPException(status_code=502, detail="Tiler response exceeded size limit.")
            if expect_png and not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise HTTPException(status_code=502, detail="Tiler returned invalid PNG data.")
            return data
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Private raster preview is temporarily unavailable.") from exc


def _no_store_response(payload: bytes, *, content_type: str) -> Response:
    return Response(content=payload, media_type=content_type, headers={
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    })


@router.get("/fields/{field_id}/satellite-observations/{observation_id}/metric-preview/{metric_type}")
def metric_preview(
    field_id: UUID,
    observation_id: UUID,
    metric_type: str,
    db: DBSession,
    current_user: CurrentUser,
) -> Response:
    metric = _owned_metric(db, current_user, field_id, observation_id, metric_type)
    lo, hi, cmap = DISPLAY[metric_type]
    png = _tiler_get("/cog/preview.png", {
        "url": metric.raster_uri,
        "rescale": f"{lo},{hi}",
        "colormap_name": cmap,
        "max_size": "600",
    }, expect_png=True)
    return _no_store_response(png, content_type="image/png")


def _change_metrics(
    db: DBSession,
    current_user: CurrentUser,
    field_id: UUID,
    before_id: UUID,
    after_id: UUID,
    metric_type: str,
) -> tuple[SatelliteMetric, SatelliteMetric]:
    before = _owned_metric(db, current_user, field_id, before_id, metric_type)
    after = _owned_metric(db, current_user, field_id, after_id, metric_type)
    return before, after


@router.get("/fields/{field_id}/satellite-change-preview")
def change_preview(
    field_id: UUID,
    before_id: UUID,
    after_id: UUID,
    metric_type: str,
    db: DBSession,
    current_user: CurrentUser,
    max_abs: float = Query(gt=0.0, le=100.0),
) -> Response:
    before, after = _change_metrics(
        db, current_user, field_id, before_id, after_id, metric_type
    )
    png = _tiler_get("/change/preview.png", {
        "before": before.raster_uri,
        "after": after.raster_uri,
        "max_abs": str(max_abs),
    }, expect_png=True)
    return _no_store_response(png, content_type="image/png")


@router.get("/fields/{field_id}/satellite-change-pixels")
def change_pixels(
    field_id: UUID,
    before_id: UUID,
    after_id: UUID,
    metric_type: str,
    db: DBSession,
    current_user: CurrentUser,
    threshold: float = Query(ge=0.0, le=100.0),
) -> Response:
    before, after = _change_metrics(
        db, current_user, field_id, before_id, after_id, metric_type
    )
    payload = _tiler_get("/change/summary", {
        "before": before.raster_uri,
        "after": after.raster_uri,
        "threshold": str(threshold),
    }, expect_png=False)
    try:
        parsed = json.loads(payload)
        if not isinstance(parsed, dict):
            raise ValueError("Unexpected summary")
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=502, detail="Invalid tiler summary.") from exc
    return _no_store_response(payload, content_type="application/json")
