"""Protect satellite sensor, storage, ingestion, and command relocation aliases.

These aliases support previously documented `python -m satellite_worker.*`
commands while the actual code lives in responsibility-based packages.
"""

import subprocess
import sys

import pytest

from satellite_worker import (
    anomaly,
    anomaly_rules,
    gcs_client,
    multisource_raster,
    raster_storage,
    stac,
    storage_context,
    storage_layout,
    storage_manifests,
)
from satellite_worker import sentinel2
from satellite_worker.ingestion import worker
from satellite_worker.processing import anomaly as processing_anomaly
from satellite_worker.processing import anomaly_rules as processing_rules
from satellite_worker.processing import raster
from satellite_worker.sources import stac as sources_stac
from satellite_worker.sources.sentinel2 import indices, processor
from satellite_worker.storage import (
    context,
    gcs,
    layout,
    manifests,
    rasters,
)


def test_legacy_worker_helpers_reexport_canonical_implementations():
    assert anomaly.detect_metric_anomalies is processing_anomaly.detect_metric_anomalies
    assert anomaly_rules.METRIC_ANOMALY_RULES is processing_rules.METRIC_ANOMALY_RULES
    assert multisource_raster.write_derived_metric_cog is raster.write_derived_metric_cog
    assert raster_storage.publish_metric_rasters is rasters.publish_metric_rasters
    assert gcs_client.gcs_bucket is gcs.gcs_bucket
    assert stac.search_sentinel2 is sources_stac.search_sentinel2
    assert storage_context.get_field_storage_context is context.get_field_storage_context
    assert storage_layout.satellite_metric_key is layout.satellite_metric_key
    assert storage_manifests.write_satellite_manifest_from_database is manifests.write_satellite_manifest_from_database


def test_legacy_sentinel2_helpers_are_still_available():
    from satellite_worker.sentinel2.indices import calculate_metric
    from satellite_worker.sentinel2.processor import process_metrics
    assert calculate_metric is indices.calculate_metric
    assert process_metrics is processor.process_metrics


@pytest.mark.parametrize("entrypoint", [
    "satellite_worker.process_field",
    "satellite_worker.process_sentinel1_field",
    "satellite_worker.process_landsat_field",
    "satellite_worker.ingestion_worker",
    "satellite_worker.process_all_fields",
    "satellite_worker.backfill_metric_anomalies",
    "satellite_worker.refresh_storage_manifests",
    # The queue now invokes the canonical commands; check their CLI contracts too.
    "satellite_worker.sources.sentinel2.pipeline",
    "satellite_worker.sources.sentinel1.pipeline",
    "satellite_worker.sources.landsat.pipeline",
])
def test_existing_cli_entrypoint_help(entrypoint):
    result = subprocess.run(
        [sys.executable, "-m", entrypoint, "--help"],
        capture_output=True, text=True, timeout=25, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()
