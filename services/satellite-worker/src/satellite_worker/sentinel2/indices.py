from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MetricDefinition:
    name: str

    bands: tuple[str, ...]

    native_resolution_m: float

    formula_version: str

    normalized_difference: bool = False


METRIC_DEFINITIONS: dict[
    str,
    MetricDefinition,
] = {
    # =====================================================
    # FIRST BATCH
    # =====================================================
    "ndvi": MetricDefinition(
        name="ndvi",
        bands=(
            "red",
            "nir",
        ),
        native_resolution_m=10.0,
        formula_version="ndvi_v1",
        normalized_difference=True,
    ),
    "ndre": MetricDefinition(
        name="ndre",
        bands=(
            "rededge1",
            "nir",
        ),
        native_resolution_m=20.0,
        formula_version="ndre_v1",
        normalized_difference=True,
    ),
    "ndmi": MetricDefinition(
        name="ndmi",
        bands=(
            "nir",
            "swir1",
        ),
        native_resolution_m=20.0,
        formula_version="ndmi_v1",
        normalized_difference=True,
    ),
    "gndvi": MetricDefinition(
        name="gndvi",
        bands=(
            "green",
            "nir",
        ),
        native_resolution_m=10.0,
        formula_version="gndvi_v1",
        normalized_difference=True,
    ),
    "evi2": MetricDefinition(
        name="evi2",
        bands=(
            "red",
            "nir",
        ),
        native_resolution_m=10.0,
        formula_version="evi2_v1",
    ),
    # =====================================================
    # SECOND BATCH
    # =====================================================
    "ndwi": MetricDefinition(
        name="ndwi",
        bands=(
            "green",
            "nir",
        ),
        native_resolution_m=10.0,
        formula_version="ndwi_mcf_v1",
        normalized_difference=True,
    ),
    "savi": MetricDefinition(
        name="savi",
        bands=(
            "red",
            "nir",
        ),
        native_resolution_m=10.0,
        formula_version="savi_l05_v1",
    ),
    "msavi": MetricDefinition(
        name="msavi",
        bands=(
            "red",
            "nir",
        ),
        native_resolution_m=10.0,
        formula_version="msavi2_v1",
    ),
    "bsi": MetricDefinition(
        name="bsi",
        bands=(
            "blue",
            "red",
            "nir",
            "swir1",
        ),
        native_resolution_m=20.0,
        formula_version="bsi_v1",
        normalized_difference=True,
    ),
    "ndti": MetricDefinition(
        name="ndti",
        bands=(
            "swir1",
            "swir2",
        ),
        native_resolution_m=20.0,
        formula_version="ndti_v1",
        normalized_difference=True,
    ),
    "ccci": MetricDefinition(
        name="ccci",
        bands=(
            "red",
            "rededge1",
            "nir",
        ),
        native_resolution_m=20.0,
        formula_version="ccci_ndre_over_ndvi_v1",
    ),
    "reci": MetricDefinition(
        name="reci",
        bands=(
            "rededge1",
            "nir",
        ),
        native_resolution_m=20.0,
        formula_version="reci_v1",
    ),
    "mcari": MetricDefinition(
        name="mcari",
        bands=(
            "green",
            "red",
            "rededge1",
        ),
        native_resolution_m=20.0,
        formula_version="mcari_v1",
    ),
}


def normalized_difference(
    first: np.ndarray,
    second: np.ndarray,
) -> tuple[
    np.ndarray,
    np.ndarray,
]:
    denominator = first + second

    valid = np.isfinite(first) & np.isfinite(second) & (np.abs(denominator) > 1e-8)

    result = np.full(
        first.shape,
        np.nan,
        dtype=np.float32,
    )

    result[valid] = (first[valid] - second[valid]) / denominator[valid]

    physical = np.isfinite(result) & (result >= -1.0) & (result <= 1.0)

    valid &= physical

    result[~valid] = np.nan

    return (
        result,
        valid,
    )


def calculate_metric(
    *,
    metric_type: str,
    reflectance: dict[
        str,
        np.ndarray,
    ],
) -> tuple[
    np.ndarray,
    np.ndarray,
]:

    # =====================================================
    # NDVI
    # =====================================================

    if metric_type == "ndvi":
        return normalized_difference(
            reflectance["nir"],
            reflectance["red"],
        )

    # =====================================================
    # NDRE
    # =====================================================

    if metric_type == "ndre":
        return normalized_difference(
            reflectance["nir"],
            reflectance["rededge1"],
        )

    # =====================================================
    # NDMI
    # =====================================================

    if metric_type == "ndmi":
        return normalized_difference(
            reflectance["nir"],
            reflectance["swir1"],
        )

    # =====================================================
    # GNDVI
    # =====================================================

    if metric_type == "gndvi":
        return normalized_difference(
            reflectance["nir"],
            reflectance["green"],
        )

    # =====================================================
    # EVI2
    #
    # 2.5 * (NIR - RED)
    # -----------------------------
    # NIR + 2.4 * RED + 1
    #
    # Requires reflectance values.
    # =====================================================

    if metric_type == "evi2":
        nir = reflectance["nir"]

        red = reflectance["red"]

        denominator = nir + 2.4 * red + 1.0

        valid = np.isfinite(nir) & np.isfinite(red) & (np.abs(denominator) > 1e-8)

        result = np.full(
            nir.shape,
            np.nan,
            dtype=np.float32,
        )

        result[valid] = 2.5 * (nir[valid] - red[valid]) / denominator[valid]

        valid &= np.isfinite(result)

        result[~valid] = np.nan

        return (
            result,
            valid,
        )

    # =====================================================
    # NDWI
    #
    # McFeeters NDWI:
    #
    # GREEN - NIR
    # -----------
    # GREEN + NIR
    #
    # This version is primarily sensitive to water.
    #
    # Do not confuse this with Gao NDWI/NDMI,
    # which uses NIR and SWIR.
    # =====================================================

    if metric_type == "ndwi":
        return normalized_difference(
            reflectance["green"],
            reflectance["nir"],
        )

    # =====================================================
    # SAVI
    #
    # L = 0.5
    #
    # (1 + L) * (NIR - RED)
    # ----------------------
    # NIR + RED + L
    #
    # Useful when soil background is important.
    # =====================================================

    if metric_type == "savi":
        nir = reflectance["nir"]

        red = reflectance["red"]

        soil_factor = 0.5

        denominator = nir + red + soil_factor

        valid = np.isfinite(nir) & np.isfinite(red) & (np.abs(denominator) > 1e-8)

        result = np.full(
            nir.shape,
            np.nan,
            dtype=np.float32,
        )

        result[valid] = (
            (1.0 + soil_factor) * (nir[valid] - red[valid]) / denominator[valid]
        )

        valid &= np.isfinite(result)

        result[~valid] = np.nan

        return (
            result,
            valid,
        )

    # =====================================================
    # MSAVI2
    #
    # 2NIR + 1 -
    # sqrt(
    #     (2NIR + 1)^2
    #     - 8(NIR - RED)
    # )
    # -------------------------
    #            2
    #
    # Unlike SAVI, this estimates the soil
    # adjustment dynamically.
    # =====================================================

    if metric_type == "msavi":
        nir = reflectance["nir"]

        red = reflectance["red"]

        discriminant = (2.0 * nir + 1.0) ** 2 - 8.0 * (nir - red)

        valid = (
            np.isfinite(nir)
            & np.isfinite(red)
            & np.isfinite(discriminant)
            & (discriminant >= 0.0)
        )

        result = np.full(
            nir.shape,
            np.nan,
            dtype=np.float32,
        )

        result[valid] = ((2.0 * nir[valid] + 1.0) - np.sqrt(discriminant[valid])) / 2.0

        valid &= np.isfinite(result)

        result[~valid] = np.nan

        return (
            result,
            valid,
        )

    # =====================================================
    # BSI
    #
    # (SWIR1 + RED) - (NIR + BLUE)
    # --------------------------------
    # (SWIR1 + RED) + (NIR + BLUE)
    #
    # Higher values can correspond to more
    # exposed/bare soil, but interpretation
    # must consider crop stage.
    # =====================================================

    if metric_type == "bsi":
        swir1 = reflectance["swir1"]

        red = reflectance["red"]

        nir = reflectance["nir"]

        blue = reflectance["blue"]

        first = swir1 + red

        second = nir + blue

        return normalized_difference(
            first,
            second,
        )

    # =====================================================
    # NDTI
    #
    # SWIR1 - SWIR2
    # -------------
    # SWIR1 + SWIR2
    #
    # Often used in residue/tillage analysis.
    # =====================================================

    if metric_type == "ndti":
        return normalized_difference(
            reflectance["swir1"],
            reflectance["swir2"],
        )

        # =====================================================
    # CCCI
    #
    # NDRE
    # ----
    # NDVI
    #
    # CCCI becomes unstable when NDVI is close to zero,
    # so pixels with |NDVI| < 0.10 are deliberately
    # rejected.
    # =====================================================

    if metric_type == "ccci":
        nir = reflectance["nir"]

        red = reflectance["red"]

        rededge1 = reflectance["rededge1"]

        ndvi, ndvi_valid = normalized_difference(
            nir,
            red,
        )

        ndre, ndre_valid = normalized_difference(
            nir,
            rededge1,
        )

        valid = (
            ndvi_valid
            & ndre_valid
            & np.isfinite(ndvi)
            & np.isfinite(ndre)
            & (np.abs(ndvi) >= 0.10)
        )

        result = np.full(
            nir.shape,
            np.nan,
            dtype=np.float32,
        )

        result[valid] = ndre[valid] / ndvi[valid]

        valid &= np.isfinite(result)

        result[~valid] = np.nan

        return (
            result,
            valid,
        )

    # =====================================================
    # RECI
    #
    # NIR
    # -------- - 1
    # RedEdge1
    #
    # Red Edge Chlorophyll Index.
    # =====================================================

    if metric_type == "reci":
        nir = reflectance["nir"]

        rededge1 = reflectance["rededge1"]

        valid = np.isfinite(nir) & np.isfinite(rededge1) & (rededge1 > 1e-6)

        result = np.full(
            nir.shape,
            np.nan,
            dtype=np.float32,
        )

        result[valid] = nir[valid] / rededge1[valid] - 1.0

        valid &= np.isfinite(result)

        result[~valid] = np.nan

        return (
            result,
            valid,
        )

    # =====================================================
    # MCARI
    #
    # [
    #   (RE - RED)
    #   - 0.2 * (RE - GREEN)
    # ]
    # *
    # (RE / RED)
    #
    # This explicitly uses our MCARI v1 formula.
    # =====================================================

    if metric_type == "mcari":
        green = reflectance["green"]

        red = reflectance["red"]

        rededge1 = reflectance["rededge1"]

        valid = (
            np.isfinite(green) & np.isfinite(red) & np.isfinite(rededge1) & (red > 1e-6)
        )

        result = np.full(
            red.shape,
            np.nan,
            dtype=np.float32,
        )

        result[valid] = (
            (rededge1[valid] - red[valid]) - 0.2 * (rededge1[valid] - green[valid])
        ) * (rededge1[valid] / red[valid])

        valid &= np.isfinite(result)

        result[~valid] = np.nan

        return (
            result,
            valid,
        )

    raise ValueError(f"Unsupported metric: " f"{metric_type}")
