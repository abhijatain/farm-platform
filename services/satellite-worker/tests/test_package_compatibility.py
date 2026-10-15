"""Verify the sole supported sensor and maintenance command entry points.

Workers and scheduled jobs must use the canonical packages, not deleted
top-level module shims.
"""

import importlib
import subprocess
import sys

import pytest

from satellite_worker.processing.anomaly import detect_metric_anomalies
from satellite_worker.processing.anomaly_rules import METRIC_ANOMALY_RULES
from satellite_worker.processing.raster import write_derived_metric_cog
from satellite_worker.sources.sentinel2.indices import calculate_metric
from satellite_worker.sources.sentinel2.processor import process_metrics
from satellite_worker.storage.rasters import publish_metric_rasters


def test_canonical_satellite_processing_imports():
    for api in (
        detect_metric_anomalies,
        write_derived_metric_cog,
        calculate_metric,
        process_metrics,
        publish_metric_rasters,
    ):
        assert callable(api)
    assert METRIC_ANOMALY_RULES


@pytest.mark.parametrize("module_name", [
    "satellite_worker.sources.sentinel2.pipeline",
    "satellite_worker.sources.sentinel1.pipeline",
    "satellite_worker.sources.landsat.pipeline",
    "satellite_worker.ingestion.worker",
    "satellite_worker.cli.process_all_fields",
    "satellite_worker.cli.backfill_metric_anomalies",
    "satellite_worker.cli.refresh_storage_manifests",
])
def test_supported_module_cli_help(module_name):
    result = subprocess.run(
        [sys.executable, "-m", module_name, "--help"],
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()


def test_installed_console_command_targets_canonical_worker():
    from importlib.metadata import distribution

    scripts = distribution("satellite-worker").entry_points
    worker = next(x for x in scripts if x.name == "satellite-ingestion-worker")
    assert worker.value == "satellite_worker.ingestion.worker:main"
