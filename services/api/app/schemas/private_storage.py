"""Prevent accidentally serializing internal storage paths through metadata."""
from __future__ import annotations


def public_metadata(value):
    """Recursive safe copy; never echo private gs:// keys to public API clients.

    The private path stays in canonical model fields for the internal tiler,
    but informational metadata is filtered when serialized to JSON.
    """
    if isinstance(value, dict):
        return {key: public_metadata(item) for key, item in value.items()}
    if isinstance(value, list):
        return [public_metadata(item) for item in value]
    if isinstance(value, tuple):
        return [public_metadata(item) for item in value]
    if isinstance(value, str) and "gs://" in value:
        return "[private storage path]"
    return value
