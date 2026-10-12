import type {
  SatelliteAnomalyFeatureCollection,
  SatelliteMetricType,
  SatelliteObservation,
} from "../../types/api";

export type { SatelliteMetricType };

export type SatelliteMetric = {
  id?: string;
  metric_type: SatelliteMetricType;
  raster_uri: string;
  mean: number | null;
  median: number | null;
  min: number | null;
  max: number | null;
  std?: number | null;
  native_resolution_m: number | null;
  output_resolution_m: number | null;
  pixel_count?: number | null;
  valid_pixel_count?: number | null;
  valid_pixel_percent: number | null;
  metadata_json?: Record<string, unknown> | null;
};

// Optional during the API migration: the UI shows "no metrics" instead of crashing.
export type SatelliteObservationWithMetrics = SatelliteObservation & {
  metrics?: SatelliteMetric[];
};

export type MetricGroup =
  | "Vegetation"
  | "Chlorophyll / red edge"
  | "Moisture / water"
  | "Soil / residue";

export type MetricAnomalyDirection = "low" | "high" | "two_sided";

export type MetricDisplayConfig = {
  label: string;
  group: MetricGroup;
  description: string;
  anomalyDirection: MetricAnomalyDirection;
  displayMin: number;
  displayMax: number;
  colormap: "rdylgn" | "rdbu" | "viridis";
  gradient: string;
};

/*
 * Fixed display scales are intentional.
 *
 * They make the same colour represent approximately the same value
 * when the farmer switches observation dates. These are visualization
 * ranges, NOT agronomic thresholds or diagnostic cut-offs.
 *
 * Values outside a configured range are saturated at the end colour
 * by TiTiler's rescaling. The real scene min/max are still shown in
 * the metadata panel below the map controls.
 */
export const METRIC_CONFIG: Record<SatelliteMetricType, MetricDisplayConfig> = {
  ndvi: {
    label: "NDVI",
    group: "Vegetation",
    description: "Vegetation greenness and canopy vigor.",
    anomalyDirection: "low",
    displayMin: -0.2,
    displayMax: 0.9,
    colormap: "rdylgn",
    gradient: "linear-gradient(90deg, #d73027 0%, #fee08b 50%, #1a9850 100%)",
  },
  gndvi: {
    label: "GNDVI",
    group: "Vegetation",
    description:
      "Green-band vegetation response, sensitive to canopy condition.",
    anomalyDirection: "low",
    displayMin: -0.2,
    displayMax: 0.85,
    colormap: "rdylgn",
    gradient: "linear-gradient(90deg, #d73027 0%, #fee08b 50%, #1a9850 100%)",
  },
  evi2: {
    label: "EVI2",
    group: "Vegetation",
    description: "Vegetation signal with reduced soil/background sensitivity.",
    anomalyDirection: "low",
    displayMin: -0.1,
    displayMax: 1.0,
    colormap: "rdylgn",
    gradient: "linear-gradient(90deg, #d73027 0%, #fee08b 50%, #1a9850 100%)",
  },
  savi: {
    label: "SAVI",
    group: "Vegetation",
    description: "Vegetation index adjusted for visible soil background.",
    anomalyDirection: "low",
    displayMin: -0.2,
    displayMax: 1.0,
    colormap: "rdylgn",
    gradient: "linear-gradient(90deg, #d73027 0%, #fee08b 50%, #1a9850 100%)",
  },
  msavi: {
    label: "MSAVI",
    group: "Vegetation",
    description: "Vegetation index with adaptive soil-background adjustment.",
    anomalyDirection: "low",
    displayMin: -0.2,
    displayMax: 1.0,
    colormap: "rdylgn",
    gradient: "linear-gradient(90deg, #d73027 0%, #fee08b 50%, #1a9850 100%)",
  },
  ndre: {
    label: "NDRE",
    group: "Chlorophyll / red edge",
    description: "Red-edge vegetation response useful in denser canopies.",
    anomalyDirection: "low",
    displayMin: -0.2,
    displayMax: 0.65,
    colormap: "rdylgn",
    gradient: "linear-gradient(90deg, #d73027 0%, #fee08b 50%, #1a9850 100%)",
  },
  ccci: {
    label: "CCCI",
    group: "Chlorophyll / red edge",
    description: "Relative red-edge response normalized by NDVI.",
    anomalyDirection: "low",
    displayMin: -0.5,
    displayMax: 1.5,
    colormap: "viridis",
    gradient:
      "linear-gradient(90deg, #440154 0%, #31688e 35%, #35b779 70%, #fde725 100%)",
  },
  reci: {
    label: "RECI",
    group: "Chlorophyll / red edge",
    description: "Red-edge chlorophyll-sensitive reflectance ratio.",
    anomalyDirection: "low",
    displayMin: -0.5,
    displayMax: 3.0,
    colormap: "viridis",
    gradient:
      "linear-gradient(90deg, #440154 0%, #31688e 35%, #35b779 70%, #fde725 100%)",
  },
  mcari: {
    label: "MCARI",
    group: "Chlorophyll / red edge",
    description: "Chlorophyll-sensitive red-edge/green vegetation signal.",
    anomalyDirection: "low",
    displayMin: -0.1,
    displayMax: 0.5,
    colormap: "viridis",
    gradient:
      "linear-gradient(90deg, #440154 0%, #31688e 35%, #35b779 70%, #fde725 100%)",
  },
  ndmi: {
    label: "NDMI",
    group: "Moisture / water",
    description: "Canopy moisture-sensitive NIR/SWIR response.",
    anomalyDirection: "low",
    displayMin: -0.6,
    displayMax: 0.8,
    colormap: "rdbu",
    gradient: "linear-gradient(90deg, #b2182b 0%, #f7f7f7 50%, #2166ac 100%)",
  },
  ndwi: {
    label: "NDWI",
    group: "Moisture / water",
    description:
      "Green/NIR water-sensitive index; positive values can indicate water.",
    anomalyDirection: "two_sided",
    displayMin: -0.8,
    displayMax: 0.8,
    colormap: "rdbu",
    gradient: "linear-gradient(90deg, #b2182b 0%, #f7f7f7 50%, #2166ac 100%)",
  },
  bsi: {
    label: "BSI",
    group: "Soil / residue",
    description:
      "Bare-soil exposure signal; interpretation depends on crop stage.",
    anomalyDirection: "high",
    displayMin: -0.6,
    displayMax: 0.6,
    colormap: "viridis",
    gradient:
      "linear-gradient(90deg, #440154 0%, #31688e 35%, #35b779 70%, #fde725 100%)",
  },
  ndti: {
    label: "NDTI",
    group: "Soil / residue",
    description: "SWIR residue/tillage-sensitive surface signal.",
    anomalyDirection: "two_sided",
    displayMin: -0.4,
    displayMax: 0.5,
    colormap: "viridis",
    gradient:
      "linear-gradient(90deg, #440154 0%, #31688e 35%, #35b779 70%, #fde725 100%)",
  },
};

export const METRIC_GROUPS: Array<{
  label: MetricGroup;
  metrics: SatelliteMetricType[];
}> = [
  {
    label: "Vegetation",
    metrics: ["ndvi", "gndvi", "evi2", "savi", "msavi"],
  },
  {
    label: "Chlorophyll / red edge",
    metrics: ["ndre", "ccci", "reci", "mcari"],
  },
  {
    label: "Moisture / water",
    metrics: ["ndmi", "ndwi"],
  },
  {
    label: "Soil / residue",
    metrics: ["bsi", "ndti"],
  },
];

// Kept as a flat list for any other UI that wants all metrics.
export const METRIC_OPTIONS = METRIC_GROUPS.flatMap((group) =>
  group.metrics.map((metricType) => ({
    value: metricType,
    label: METRIC_CONFIG[metricType].label,
  })),
);

export const EMPTY_ANOMALIES: SatelliteAnomalyFeatureCollection = {
  type: "FeatureCollection",
  features: [],
};

function metricsOf(observation: SatelliteObservationWithMetrics) {
  return observation.metrics ?? [];
}

export function getMetricConfig(metricType: SatelliteMetricType) {
  return METRIC_CONFIG[metricType];
}

export function getMetricAnomalyDescription(metricType: SatelliteMetricType) {
  const config = getMetricConfig(metricType);

  if (config.anomalyDirection === "low") {
    return (
      `Areas with unusually low ${config.label} values ` +
      "relative to the rest of this field."
    );
  }

  if (config.anomalyDirection === "high") {
    return (
      `Areas with unusually high ${config.label} values ` +
      "relative to the rest of this field."
    );
  }

  return (
    `Areas with unusually low or high ${config.label} values ` +
    "relative to the rest of this field."
  );
}

export function getMetricFromObservation(
  observation: SatelliteObservationWithMetrics,
  metricType: SatelliteMetricType,
): SatelliteMetric | null {
  return (
    metricsOf(observation).find(
      (metric) => metric.metric_type === metricType,
    ) ?? null
  );
}

export function getMetricForObservation(
  observations: SatelliteObservationWithMetrics[],
  observationId: string | null,
  metricType: SatelliteMetricType,
): SatelliteMetric | null {
  if (!observationId) {
    return null;
  }

  const observation = observations.find(
    (candidate) => candidate.id === observationId,
  );

  return observation ? getMetricFromObservation(observation, metricType) : null;
}

export function getObservationsForMetric(
  observations: SatelliteObservationWithMetrics[],
  metricType: SatelliteMetricType,
) {
  return observations
    .filter((observation) => {
      const metric = getMetricFromObservation(observation, metricType);
      return Boolean(metric?.raster_uri);
    })
    .sort((a, b) => b.observed_on.localeCompare(a.observed_on));
}

export function getDefaultObservation(
  observations: SatelliteObservationWithMetrics[],
  metricType: SatelliteMetricType,
): SatelliteObservationWithMetrics | null {
  const available = getObservationsForMetric(observations, metricType);

  return (
    available.find((observation) => {
      const metric = getMetricFromObservation(observation, metricType);
      return (
        metric?.valid_pixel_percent == null || metric.valid_pixel_percent >= 80
      );
    }) ??
    available[0] ??
    null
  );
}

export function formatObservationDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function formatMetricValue(value: number | null, digits = 2) {
  return value == null || !Number.isFinite(value) ? "—" : value.toFixed(digits);
}

export function buildMetricTileJsonUrl(
  tilerUrl: string,
  metric: SatelliteMetric,
) {
  const config = getMetricConfig(metric.metric_type);

  const params = new URLSearchParams({
    url: metric.raster_uri,
    rescale: `${config.displayMin},${config.displayMax}`,
    colormap_name: config.colormap,
  });

  return `${tilerUrl}/cog/WebMercatorQuad/tilejson.json?${params.toString()}`;
}
