"""Initialize the API storage package and its stable imports."""

from app.storage.gcs import GCSObjectInfo, GCSStorage
from app.storage.service import get_storage


__all__ = [
    "GCSObjectInfo",
    "GCSStorage",
    "get_storage",
]
