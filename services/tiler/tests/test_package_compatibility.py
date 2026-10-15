"""Guard TiTiler public import paths after service/storage segregation."""

from farm_tiler import change, gcs_path
from farm_tiler.services import change as change_service
from farm_tiler.storage import gcs_path as private_storage


def test_old_tiler_raster_and_path_imports_stay_compatible():
    assert change.read_change_raster is change_service.read_change_raster
    assert change.summarize_change is change_service.summarize_change
    assert gcs_path.DatasetPathParams is private_storage.DatasetPathParams
