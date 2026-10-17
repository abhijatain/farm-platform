"""Prevent private GCS object locations or signed URLs leaking through API metadata."""

from __future__ import annotations


_PRIVATE_STORAGE_MARKERS = (
    "gs://",
    "storage.googleapis.com/",
    ".storage.googleapis.com/",
    "storage.cloud.google.com/",
    "x-goog-signature=",
    "x-goog-credential=",
)


def public_metadata(value):
    """Recursively redact internal storage paths and GCS signed URL strings.

    Canonical raster locations remain on internal ORM models. Public API
    response serializers must not disclose them, including in nested metadata,
    worker error descriptions, or dictionary keys.
    """
    if isinstance(value, dict):
        return {public_metadata(key): public_metadata(item) for key, item in value.items()}
    if isinstance(value, list):
        return [public_metadata(item) for item in value]
    if isinstance(value, tuple):
        return [public_metadata(item) for item in value]
    if isinstance(value, str) and any(
        marker in value.lower() for marker in _PRIVATE_STORAGE_MARKERS
    ):
        return "[private storage path]"
    return value
