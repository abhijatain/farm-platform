"""Define index-specific spatial anomaly limits and allowed modes."""

from dataclasses import dataclass
from typing import Literal


AnomalyDirection = Literal[
    "low",
    "high",
    "two_sided",
]


@dataclass(frozen=True)
class MetricAnomalyRule:
    metric_type: str

    direction: AnomalyDirection

    minimum_difference: float

    label: str


METRIC_ANOMALY_RULES = {
    "ndvi": MetricAnomalyRule(
        metric_type="ndvi",
        direction="low",
        minimum_difference=0.08,
        label="Low vegetation response",
    ),
    "gndvi": MetricAnomalyRule(
        metric_type="gndvi",
        direction="low",
        minimum_difference=0.06,
        label="Low green vegetation response",
    ),
    "evi2": MetricAnomalyRule(
        metric_type="evi2",
        direction="low",
        minimum_difference=0.05,
        label="Low vegetation response",
    ),
    "savi": MetricAnomalyRule(
        metric_type="savi",
        direction="low",
        minimum_difference=0.06,
        label="Low soil-adjusted vegetation response",
    ),
    "msavi": MetricAnomalyRule(
        metric_type="msavi",
        direction="low",
        minimum_difference=0.06,
        label="Low soil-adjusted vegetation response",
    ),
    "ndre": MetricAnomalyRule(
        metric_type="ndre",
        direction="low",
        minimum_difference=0.05,
        label="Low red-edge response",
    ),
    "ccci": MetricAnomalyRule(
        metric_type="ccci",
        direction="low",
        minimum_difference=0.08,
        label="Low relative chlorophyll response",
    ),
    "reci": MetricAnomalyRule(
        metric_type="reci",
        direction="low",
        minimum_difference=0.10,
        label="Low red-edge chlorophyll response",
    ),
    "mcari": MetricAnomalyRule(
        metric_type="mcari",
        direction="low",
        minimum_difference=0.02,
        label="Low chlorophyll-related response",
    ),
    "ndmi": MetricAnomalyRule(
        metric_type="ndmi",
        direction="low",
        minimum_difference=0.08,
        label="Low moisture-related response",
    ),
    "bsi": MetricAnomalyRule(
        metric_type="bsi",
        direction="high",
        minimum_difference=0.08,
        label="High bare-soil response",
    ),
    "ndwi": MetricAnomalyRule(
        metric_type="ndwi",
        direction="two_sided",
        minimum_difference=0.10,
        label="Unusual water-related response",
    ),
    "ndti": MetricAnomalyRule(
        metric_type="ndti",
        direction="two_sided",
        minimum_difference=0.08,
        label="Unusual residue/tillage response",
    ),
    "lst_c": MetricAnomalyRule(
        metric_type="lst_c",
        direction="high",
        minimum_difference=2.0,
        label="High land-surface temperature",
    ),
}
