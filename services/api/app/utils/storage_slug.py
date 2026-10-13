
from __future__ import annotations

import re
import unicodedata


def make_storage_slug(
    value: str,
    *,
    fallback: str,
    max_length: int = 60,
) -> str:
    """Create a stable human-readable path slug."""
    normalized = unicodedata.normalize("NFKD", value)

    ascii_value = (
        normalized
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )

    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        ascii_value,
    ).strip("-")

    if not slug:
        slug = fallback

    return (
        slug[:max_length]
        .strip("-")
        or fallback
    )
