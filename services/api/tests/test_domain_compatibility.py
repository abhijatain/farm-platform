"""Protect canonical API domain modules and their legacy import paths.

A route refactor must not split classes or helpers into two incompatible
implementations just because a Python module was relocated.
"""

from app.domains.activities import satellite as activities
from app.domains.crops import phenology
from app.domains.media import processing, uploads
from app.domains.satellite import change, ingestion, radar_screening, timeline, trends
from app.services import (
    activity_satellite,
    crop_phenology,
    media_processing,
    media_uploads,
    radar_screening as old_radar,
    satellite_change,
    satellite_ingestion,
    satellite_timeline,
    satellite_trends,
)


def test_activity_and_crop_compatibility():
    assert activity_satellite._percent_change is activities._percent_change
    assert crop_phenology.resolve_profile is phenology.resolve_profile


def test_media_compatibility():
    assert media_processing.process_media_asset is processing.process_media_asset
    assert media_uploads._media_type_info is uploads._media_type_info
    assert media_uploads.settings is uploads.settings


def test_satellite_domain_compatibility():
    assert old_radar.build_radar_screening is radar_screening.build_radar_screening
    assert satellite_change.build_field_satellite_change is change.build_field_satellite_change
    assert satellite_ingestion.enqueue_initial_satellite_backfill is ingestion.enqueue_initial_satellite_backfill
    assert satellite_timeline.get_field_satellite_timeline is timeline.get_field_satellite_timeline
    assert satellite_trends.get_field_satellite_trends is trends.get_field_satellite_trends
