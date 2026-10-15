"""Validate that canonical business-domain APIs are importable and callable.

These assertions exercise the maintained package paths; old service facades
must not be needed to load the FastAPI application or processing modules.
"""

from app.domains.activities.satellite import _percent_change
from app.domains.crops.phenology import resolve_profile
from app.domains.media.processing import process_media_asset
from app.domains.media.uploads import _media_type_info
from app.domains.satellite.change import build_field_satellite_change
from app.domains.satellite.ingestion import enqueue_initial_satellite_backfill
from app.domains.satellite.radar_screening import build_radar_screening
from app.domains.satellite.timeline import get_field_satellite_timeline
from app.domains.satellite.trends import get_field_satellite_trends


def test_domain_modules_have_explicit_reusable_entrypoints():
    for function in (
        _percent_change,
        resolve_profile,
        process_media_asset,
        _media_type_info,
        build_field_satellite_change,
        enqueue_initial_satellite_backfill,
        build_radar_screening,
        get_field_satellite_timeline,
        get_field_satellite_trends,
    ):
        assert callable(function)


def test_activity_and_media_rules_use_canonical_paths():
    assert _percent_change(-10.0, -15.0) == -50.0
    assert _media_type_info("image/jpeg") == ("image", ".jpg")
