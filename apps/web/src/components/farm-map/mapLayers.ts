import type {
  FillLayerSpecification,
  GeoJSONSource,
  LineLayerSpecification,
  Map as MapLibreMap,
} from "maplibre-gl";
import type {
  Field,
  SatelliteAnomalyFeatureCollection,
} from "../../types/api";
import { buildMetricTileJsonUrl, type SatelliteMetric } from "./satellite";

const TILER_URL =
  import.meta.env.VITE_TILER_URL;

if (!TILER_URL) {
  throw new Error(
    "VITE_TILER_URL is missing.",
  );
}

export const FIELD_SOURCE_ID = "farm-fields";
export const FIELD_FILL_LAYER_ID = "farm-fields-fill";
export const FIELD_OUTLINE_LAYER_ID = "farm-fields-outline";
export const FIELD_LABEL_LAYER_ID = "farm-field-labels";
export const METRIC_SOURCE_ID = "selected-field-metric";
export const METRIC_LAYER_ID = "selected-field-metric-layer";
export const ANOMALY_SOURCE_ID = "satellite-anomalies";
export const ANOMALY_FILL_LAYER_ID = "satellite-anomalies-fill";
export const ANOMALY_OUTLINE_LAYER_ID = "satellite-anomalies-outline";

function buildFieldsGeoJson(fields: Field[]) {
  return {
    type: "FeatureCollection" as const,
    features: fields.map((field) => ({
      type: "Feature" as const,
      properties: {
        fieldId: field.id,
        name: field.name,
      },
      geometry: field.boundary,
    })),
  };
}

export function installFieldLayers(map: MapLibreMap, fields: Field[]) {
  const existing = map.getSource(FIELD_SOURCE_ID);

  if (existing) {
    (existing as GeoJSONSource).setData(buildFieldsGeoJson(fields));
    return;
  }

  map.addSource(FIELD_SOURCE_ID, {
    type: "geojson",
    data: buildFieldsGeoJson(fields),
  });

  map.addLayer({
    id: FIELD_FILL_LAYER_ID,
    type: "fill",
    source: FIELD_SOURCE_ID,
    paint: {
      "fill-color": "#4ade80",
      "fill-opacity": 0.28,
    },
  });

  map.addLayer({
    id: FIELD_OUTLINE_LAYER_ID,
    type: "line",
    source: FIELD_SOURCE_ID,
    paint: {
      "line-color": "#ffffff",
      "line-width": 2,
    },
  });

  map.addLayer({
    id: FIELD_LABEL_LAYER_ID,
    type: "symbol",
    source: FIELD_SOURCE_ID,
    layout: {
      "text-field": ["get", "name"],
      "text-size": 13,
      "text-anchor": "center",
    },
    paint: {
      "text-color": "#ffffff",
      "text-halo-color": "#166534",
      "text-halo-width": 2,
    },
  });
}

export function updateFieldSource(map: MapLibreMap, fields: Field[]) {
  const source = map.getSource(FIELD_SOURCE_ID);

  if (!source) {
    installFieldLayers(map, fields);
    return;
  }

  (source as GeoJSONSource).setData(buildFieldsGeoJson(fields));
}

export function applySelectedFieldStyle(
  map: MapLibreMap,
  selectedFieldId: string | null,
  metricEnabled: boolean,
) {
  if (map.getLayer(FIELD_OUTLINE_LAYER_ID)) {
    map.setPaintProperty(FIELD_OUTLINE_LAYER_ID, "line-width", [
      "case",
      ["==", ["get", "fieldId"], selectedFieldId ?? ""],
      5,
      2,
    ]);
  }

  if (map.getLayer(FIELD_FILL_LAYER_ID)) {
    map.setPaintProperty(FIELD_FILL_LAYER_ID, "fill-opacity", [
      "case",
      ["==", ["get", "fieldId"], selectedFieldId ?? ""],
      metricEnabled ? 0 : 0.5,
      0.28,
    ]);
  }
}

export function removeMetricLayer(map: MapLibreMap) {
  if (map.getLayer(METRIC_LAYER_ID)) {
    map.removeLayer(METRIC_LAYER_ID);
  }

  if (map.getSource(METRIC_SOURCE_ID)) {
    map.removeSource(METRIC_SOURCE_ID);
  }
}

export function installMetricLayer(
  map: MapLibreMap,
  metric: SatelliteMetric | null,
  opacity: number,
) {
  removeMetricLayer(map);

  if (!metric) {
    return;
  }

  map.addSource(METRIC_SOURCE_ID, {
    type: "raster",
    // TileJSON supplies tile URL, bounds and tile size.
    url: buildMetricTileJsonUrl(TILER_URL, metric),
  });

  const layer = {
    id: METRIC_LAYER_ID,
    type: "raster" as const,
    source: METRIC_SOURCE_ID,
    paint: {
      "raster-opacity": opacity,
      "raster-resampling": "nearest" as const,
      "raster-fade-duration": 0,
    },
  };

  if (map.getLayer(FIELD_OUTLINE_LAYER_ID)) {
    map.addLayer(layer, FIELD_OUTLINE_LAYER_ID);
  } else {
    map.addLayer(layer);
  }
}

export function removeAnomalyLayers(map: MapLibreMap) {
  if (map.getLayer(ANOMALY_OUTLINE_LAYER_ID)) {
    map.removeLayer(ANOMALY_OUTLINE_LAYER_ID);
  }

  if (map.getLayer(ANOMALY_FILL_LAYER_ID)) {
    map.removeLayer(ANOMALY_FILL_LAYER_ID);
  }

  if (map.getSource(ANOMALY_SOURCE_ID)) {
    map.removeSource(ANOMALY_SOURCE_ID);
  }
}

export function installAnomalyLayers(
  map: MapLibreMap,
  data: SatelliteAnomalyFeatureCollection,
  visible: boolean,
  selectedAnomalyId: string | null,
) {
  removeAnomalyLayers(map);

  if (!visible) {
    return;
  }

  map.addSource(ANOMALY_SOURCE_ID, {
    type: "geojson",
    data: data as any,
  });

  const fillLayer: FillLayerSpecification = {
    id: ANOMALY_FILL_LAYER_ID,
    type: "fill",
    source: ANOMALY_SOURCE_ID,
    paint: {
      "fill-color": [
        "match",
        ["get", "severity"],
        "high",
        "#d73027",
        "moderate",
        "#f39c12",
        "low",
        "#f1c40f",
        "#d73027",
      ],
      "fill-opacity": 0.3,
    },
  };

  const outlineLayer: LineLayerSpecification = {
    id: ANOMALY_OUTLINE_LAYER_ID,
    type: "line",
    source: ANOMALY_SOURCE_ID,
    paint: {
      "line-color": [
        "match",
        ["get", "severity"],
        "high",
        "#a50026",
        "moderate",
        "#c86d00",
        "low",
        "#a58b00",
        "#a50026",
      ],
      "line-width": [
        "case",
        ["==", ["get", "id"], selectedAnomalyId ?? ""],
        5,
        2.5,
      ],
      "line-opacity": 0.98,
    },
  };

  if (map.getLayer(FIELD_OUTLINE_LAYER_ID)) {
    map.addLayer(fillLayer, FIELD_OUTLINE_LAYER_ID);
    map.addLayer(outlineLayer, FIELD_OUTLINE_LAYER_ID);
  } else {
    map.addLayer(fillLayer);
    map.addLayer(outlineLayer);
  }
}

export function updateSelectedAnomalyStyle(
  map: MapLibreMap,
  selectedAnomalyId: string | null,
) {
  if (!map.getLayer(ANOMALY_OUTLINE_LAYER_ID)) {
    return;
  }

  map.setPaintProperty(ANOMALY_OUTLINE_LAYER_ID, "line-width", [
    "case",
    ["==", ["get", "id"], selectedAnomalyId ?? ""],
    5,
    2.5,
  ]);
}
