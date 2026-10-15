"""Protect upload policy and activity delta semantics after helper extraction."""

import pytest
from fastapi import HTTPException

from app.services.activity_satellite import (
    _comparison_status,
    _percent_change,
)
from app.services.media_uploads import (
    _media_type_info,
    _normalized_content_type,
    _validate_size,
)


def test_upload_type_normalization_is_stable():
    assert _normalized_content_type(" IMAGE/JPEG ; charset=binary ") == "image/jpeg"
    assert _media_type_info("image/jpeg") == ("image", ".jpg")
    assert _media_type_info("video/quicktime") == ("video", ".mov")


def test_unsupported_upload_is_rejected():
    with pytest.raises(HTTPException) as result:
        _media_type_info("application/x-executable")
    assert result.value.status_code == 422


def test_image_size_over_limit_is_rejected(monkeypatch):
    from app.services.media_uploads import settings

    monkeypatch.setattr(settings, "media_max_image_bytes", 1000)
    _validate_size(media_type="image", size_bytes=1000)
    with pytest.raises(HTTPException) as result:
        _validate_size(media_type="image", size_bytes=1001)
    assert result.value.status_code == 413


def test_activity_percent_deltas_do_not_divide_by_near_zero():
    assert _percent_change(None, 1.0) is None
    assert _percent_change(0.001, 1.0) is None
    assert _percent_change(-10.0, -15.0) == -50.0
    assert _comparison_status(before=None, after=None) == "missing_both"
    assert _comparison_status(before=None, after=object()) == "missing_before"
    assert _comparison_status(before=object(), after=None) == "missing_after"
