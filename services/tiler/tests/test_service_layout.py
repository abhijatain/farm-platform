"""Validate canonical raster change and private GCS path modules.

There are no alternative top-level tiler imports: APIs use these packages
directly, and both are independently testable.
"""

from farm_tiler.services.change import read_change_raster, summarize_change
from farm_tiler.storage.gcs_path import DatasetPathParams


def test_tiler_has_distinct_processing_and_storage_components():
    assert callable(read_change_raster)
    assert callable(summarize_change)
    assert callable(DatasetPathParams)
