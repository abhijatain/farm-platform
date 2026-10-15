"""Apply correct reflectance scaling and upstream data offsets."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pystac


class AmbiguousReflectanceCalibrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReflectanceCalibration:
    scale: float

    advertised_offset: float

    effective_offset: float

    boa_offset_applied: bool | None

    processing_baseline: str | None

    method: str


def _get_raster_metadata(
    asset: pystac.Asset,
) -> dict:
    raster_bands = asset.extra_fields.get("raster:bands") or []

    if not raster_bands:
        raise RuntimeError(
            "Sentinel asset does not "
            "contain raster:bands "
            "metadata. Refusing to "
            "guess reflectance scaling."
        )

    return raster_bands[0]


def get_reflectance_calibration(
    *,
    item: pystac.Item,
    asset: pystac.Asset,
) -> ReflectanceCalibration:
    metadata = _get_raster_metadata(asset)

    raw_scale = metadata.get("scale")

    if raw_scale is None:
        raise RuntimeError("Sentinel asset does not " "declare a raster scale.")

    scale = float(raw_scale)

    advertised_offset = float(
        metadata.get(
            "offset",
            0.0,
        )
    )

    boa_offset_applied_raw = item.properties.get("earthsearch:" "boa_offset_applied")

    if isinstance(
        boa_offset_applied_raw,
        bool,
    ):
        boa_offset_applied = boa_offset_applied_raw

    else:
        boa_offset_applied = None

    processing_baseline_raw = item.properties.get("s2:" "processing_baseline")

    processing_baseline = (
        str(processing_baseline_raw) if (processing_baseline_raw is not None) else None
    )

    collection_id = item.collection_id or ""

    # -----------------------------------------
    # Legacy Earth Search Sentinel-2 L2A COGs
    # -----------------------------------------
    #
    # We already verified one of our 2026
    # scenes experimentally:
    #
    #   earthsearch:boa_offset_applied = True
    #   raster offset = -0.1
    #
    # Applying -0.1 again produced severely
    # saturated NDVI.
    #
    # Therefore when Earth Search explicitly
    # says the BOA offset has already been
    # applied to the COG values, we apply
    # only the multiplicative scale.
    #
    if collection_id == "sentinel-2-l2a" and boa_offset_applied is True:
        return ReflectanceCalibration(
            scale=scale,
            advertised_offset=(advertised_offset),
            effective_offset=0.0,
            boa_offset_applied=True,
            processing_baseline=(processing_baseline),
            method=("earthsearch_legacy_cog_" "boa_offset_already_applied"),
        )

    # No additive offset is required.
    if advertised_offset == 0.0:
        return ReflectanceCalibration(
            scale=scale,
            advertised_offset=0.0,
            effective_offset=0.0,
            boa_offset_applied=(boa_offset_applied),
            processing_baseline=(processing_baseline),
            method="stac_scale_only",
        )

    # -----------------------------------------
    # Ambiguous legacy Earth Search case
    # -----------------------------------------
    #
    # There have been reported inconsistencies
    # between the older collection's
    # boa_offset_applied flag and the actual
    # stored COG values.
    #
    # For NDVI-style normalized differences
    # we may be able to work directly from
    # the harmonized DN values.
    #
    # But for EVI2/SAVI/MSAVI/MCARI, guessing
    # the physical reflectance calibration
    # would be scientifically unsafe.
    #
    if collection_id == "sentinel-2-l2a" and advertised_offset != 0.0:
        raise (
            AmbiguousReflectanceCalibrationError(
                "Ambiguous reflectance "
                f"calibration for scene "
                f"{item.id!r}. "
                "The legacy Earth Search "
                "sentinel-2-l2a asset "
                f"advertises offset "
                f"{advertised_offset}, "
                "but "
                "earthsearch:"
                "boa_offset_applied is "
                f"{boa_offset_applied!r}. "
                "Refusing to guess."
            )
        )

    # -----------------------------------------
    # Other providers / future collections
    # -----------------------------------------
    #
    # For non-legacy Earth Search assets,
    # respect the STAC Raster Extension.
    #
    return ReflectanceCalibration(
        scale=scale,
        advertised_offset=(advertised_offset),
        effective_offset=(advertised_offset),
        boa_offset_applied=(boa_offset_applied),
        processing_baseline=(processing_baseline),
        method="stac_scale_and_offset",
    )


def to_reflectance(
    *,
    item: pystac.Item,
    asset: pystac.Asset,
    data: np.ndarray,
) -> tuple[
    np.ndarray,
    ReflectanceCalibration,
]:
    calibration = get_reflectance_calibration(
        item=item,
        asset=asset,
    )

    reflectance = (
        data.astype(
            np.float32,
            copy=False,
        )
        * calibration.scale
        + calibration.effective_offset
    )

    return (
        reflectance.astype(
            np.float32,
            copy=False,
        ),
        calibration,
    )


def print_reflectance_diagnostics(
    *,
    name: str,
    values: np.ndarray,
    valid_mask: np.ndarray,
    calibration: ReflectanceCalibration,
) -> None:
    valid_values = values[valid_mask & np.isfinite(values)]

    print()
    print(f"{name} reflectance")

    print(
        "  scale:",
        calibration.scale,
    )

    print(
        "  advertised offset:",
        calibration.advertised_offset,
    )

    print(
        "  effective offset:",
        calibration.effective_offset,
    )

    print(
        "  BOA offset applied:",
        calibration.boa_offset_applied,
    )

    print(
        "  baseline:",
        calibration.processing_baseline,
    )

    print(
        "  method:",
        calibration.method,
    )

    if valid_values.size == 0:
        print("  no valid values")

        return

    print(
        "  min:",
        float(np.min(valid_values)),
    )

    print(
        "  median:",
        float(np.median(valid_values)),
    )

    print(
        "  max:",
        float(np.max(valid_values)),
    )
