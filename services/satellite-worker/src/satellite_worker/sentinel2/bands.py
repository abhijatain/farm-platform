"""Define Sentinel-2 spectral bands, naming and native pixel resolution."""

from __future__ import annotations

from dataclasses import dataclass

import pystac
from rasterio.enums import Resampling


@dataclass(frozen=True)
class SentinelBandDefinition:
    name: str

    candidates: tuple[str, ...]

    native_resolution_m: float

    resampling: Resampling


BANDS: dict[str, SentinelBandDefinition] = {
    "blue": SentinelBandDefinition(
        name="blue",
        candidates=(
            "blue",
            "B02",
            "b02",
        ),
        native_resolution_m=10.0,
        resampling=Resampling.bilinear,
    ),
    "green": SentinelBandDefinition(
        name="green",
        candidates=(
            "green",
            "B03",
            "b03",
        ),
        native_resolution_m=10.0,
        resampling=Resampling.bilinear,
    ),
    "red": SentinelBandDefinition(
        name="red",
        candidates=(
            "red",
            "B04",
            "b04",
        ),
        native_resolution_m=10.0,
        resampling=Resampling.bilinear,
    ),
    "rededge1": SentinelBandDefinition(
        name="rededge1",
        candidates=(
            "rededge1",
            "rededge",
            "B05",
            "b05",
        ),
        native_resolution_m=20.0,
        resampling=Resampling.bilinear,
    ),
    "nir": SentinelBandDefinition(
        name="nir",
        candidates=(
            "nir",
            "B08",
            "b08",
        ),
        native_resolution_m=10.0,
        resampling=Resampling.bilinear,
    ),
    "swir1": SentinelBandDefinition(
        name="swir1",
        candidates=(
            "swir16",
            "swir1",
            "B11",
            "b11",
        ),
        native_resolution_m=20.0,
        resampling=Resampling.bilinear,
    ),
    "swir2": SentinelBandDefinition(
        name="swir2",
        candidates=(
            "swir22",
            "swir2",
            "B12",
            "b12",
        ),
        native_resolution_m=20.0,
        resampling=Resampling.bilinear,
    ),
    "scl": SentinelBandDefinition(
        name="scl",
        candidates=(
            "scl",
            "SCL",
        ),
        native_resolution_m=20.0,
        resampling=Resampling.nearest,
    ),
}


def get_band_definition(
    band_name: str,
) -> SentinelBandDefinition:
    try:
        return BANDS[band_name]

    except KeyError as error:
        supported = ", ".join(sorted(BANDS.keys()))

        raise ValueError(
            f"Unknown Sentinel-2 band "
            f"{band_name!r}. "
            f"Supported bands: {supported}"
        ) from error


def get_band_asset(
    item: pystac.Item,
    band_name: str,
) -> tuple[
    str,
    pystac.Asset,
    SentinelBandDefinition,
]:
    definition = get_band_definition(band_name)

    for candidate in definition.candidates:
        asset = item.assets.get(candidate)

        if asset is not None:
            return (
                candidate,
                asset,
                definition,
            )

    raise KeyError(
        f"Scene {item.id!r} does not "
        f"contain a usable asset for "
        f"band {band_name!r}. "
        f"Tried: "
        f"{definition.candidates}"
    )
