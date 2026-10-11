import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl, { type Map as MapLibreMap } from "maplibre-gl";
import { GeocodingControl } from "@maptiler/geocoding-control/maplibregl";
import type { TerraDraw } from "terra-draw";

import { listSatelliteAnomalies, listSatelliteObservations } from "../lib/api";
import type {
  Field,
  PolygonGeometry,
  SatelliteAnomalyFeatureCollection,
} from "../types/api";
import type { MapMode } from "../types/map";

import { SatelliteAnalysisPanel } from "./farm-map/SatelliteAnalysisPanel";
import {
  ANOMALY_FILL_LAYER_ID,
  ANOMALY_OUTLINE_LAYER_ID,
  METRIC_SOURCE_ID,
  applySelectedFieldStyle,
  installAnomalyLayers,
  installFieldLayers,
  installMetricLayer,
  updateFieldSource,
  updateSelectedAnomalyStyle,
} from "./farm-map/mapLayers";
import {
  EMPTY_ANOMALIES,
  getDefaultObservation,
  getMetricForObservation,
  type SatelliteMetricType,
  type SatelliteObservationWithMetrics,
} from "./farm-map/satellite";
import { zoomToAnomaly, zoomToField } from "./farm-map/mapGeometry";
import { createDrawingSystem } from "./farm-map/drawing";

type Props = {
  mapMode: MapMode;
  fields: Field[];
  selectedFieldId: string | null;
  drawing: boolean;
  onSelectField: (fieldId: string) => void;
  onPolygonFinished: (boundary: PolygonGeometry) => void;
};

const MAPTILER_KEY = import.meta.env.VITE_MAPTILER_KEY;

if (!MAPTILER_KEY) {
  throw new Error("VITE_MAPTILER_KEY is missing.");
}

const MAP_STYLES = {
  hybrid: `https://api.maptiler.com/maps/hybrid-v4/style.json?key=${MAPTILER_KEY}`,
  streets: `https://api.maptiler.com/maps/streets-v4/style.json?key=${MAPTILER_KEY}`,
};

export default function FarmMap({
  mapMode,
  fields,
  selectedFieldId,
  drawing,
  onSelectField,
  onPolygonFinished,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const drawRef = useRef<TerraDraw | null>(null);

  const [satelliteObservations, setSatelliteObservations] = useState<
    SatelliteObservationWithMetrics[]
  >([]);
  const [selectedObservationId, setSelectedObservationId] = useState<
    string | null
  >(null);
  const [selectedMetricType, setSelectedMetricType] =
    useState<SatelliteMetricType>("ndvi");
  const [metricEnabled, setMetricEnabled] = useState(false);
  const [metricOpacity, setMetricOpacity] = useState(0.72);
  const [satelliteLoading, setSatelliteLoading] = useState(false);
  const [satelliteError, setSatelliteError] = useState<string | null>(null);

  const [anomalyData, setAnomalyData] =
    useState<SatelliteAnomalyFeatureCollection>(EMPTY_ANOMALIES);
  const [selectedAnomalyId, setSelectedAnomalyId] = useState<string | null>(
    null,
  );
  const [anomalyLoading, setAnomalyLoading] = useState(false);
  const [anomalyError, setAnomalyError] = useState<string | null>(null);

  // Refs let MapLibre callbacks created once read current React state.
  const fieldsRef = useRef(fields);
  const drawingRef = useRef(drawing);
  const selectFieldRef = useRef(onSelectField);
  const polygonFinishedRef = useRef(onPolygonFinished);
  const selectedFieldIdRef = useRef<string | null>(selectedFieldId);
  const satelliteObservationsRef = useRef<SatelliteObservationWithMetrics[]>(
    satelliteObservations,
  );
  const selectedObservationIdRef = useRef<string | null>(selectedObservationId);
  const selectedMetricTypeRef = useRef<SatelliteMetricType>(selectedMetricType);
  const metricEnabledRef = useRef(metricEnabled);
  const metricOpacityRef = useRef(metricOpacity);
  const anomalyDataRef =
    useRef<SatelliteAnomalyFeatureCollection>(EMPTY_ANOMALIES);
  const selectedAnomalyIdRef = useRef<string | null>(selectedAnomalyId);
  const previousMapModeRef = useRef<MapMode>(mapMode);

  fieldsRef.current = fields;
  drawingRef.current = drawing;
  selectFieldRef.current = onSelectField;
  polygonFinishedRef.current = onPolygonFinished;
  selectedFieldIdRef.current = selectedFieldId;
  satelliteObservationsRef.current = satelliteObservations;
  selectedObservationIdRef.current = selectedObservationId;
  selectedMetricTypeRef.current = selectedMetricType;
  metricEnabledRef.current = metricEnabled;
  metricOpacityRef.current = metricOpacity;
  anomalyDataRef.current = anomalyData;
  selectedAnomalyIdRef.current = selectedAnomalyId;

  const selectedMetric = getMetricForObservation(
    satelliteObservations,
    selectedObservationId,
    selectedMetricType,
  );

  const selectedAnomaly = useMemo(
    () =>
      anomalyData.features.find(
        (feature) => feature.id === selectedAnomalyId,
      ) ?? null,
    [anomalyData, selectedAnomalyId],
  );

  function getCurrentMetricFromRefs() {
    return getMetricForObservation(
      satelliteObservationsRef.current,
      selectedObservationIdRef.current,
      selectedMetricTypeRef.current,
    );
  }

  function recreateDrawingSystem(map: MapLibreMap) {
    try {
      drawRef.current?.stop();
    } catch (error) {
      console.warn("Unable to stop previous TerraDraw instance:", error);
    }

    drawRef.current = createDrawingSystem({
      map,
      drawing: drawingRef.current,
      onPolygonFinished: (boundary) => polygonFinishedRef.current(boundary),
    });
  }

  function restoreCustomLayers(map: MapLibreMap) {
    installFieldLayers(map, fieldsRef.current);
    installMetricLayer(
      map,
      metricEnabledRef.current ? getCurrentMetricFromRefs() : null,
      metricOpacityRef.current,
    );
    installAnomalyLayers(
      map,
      anomalyDataRef.current,
      metricEnabledRef.current && selectedMetricTypeRef.current === "ndvi",
      selectedAnomalyIdRef.current,
    );
    applySelectedFieldStyle(
      map,
      selectedFieldIdRef.current,
      metricEnabledRef.current,
    );
    recreateDrawingSystem(map);
  }

  // Load observations for the selected field.
  useEffect(() => {
    let cancelled = false;

    setSatelliteObservations([]);
    setSelectedObservationId(null);
    setSatelliteError(null);
    setAnomalyData(EMPTY_ANOMALIES);
    setSelectedAnomalyId(null);
    setAnomalyError(null);

    if (!selectedFieldId) {
      setSatelliteLoading(false);
      setMetricEnabled(false);
      return;
    }

    setSatelliteLoading(true);

    void listSatelliteObservations(selectedFieldId)
      .then((observations) => {
        if (cancelled) {
          return;
        }

        setSatelliteObservations(observations);

        const defaultObservation = getDefaultObservation(
          observations,
          selectedMetricTypeRef.current,
        );

        setSelectedObservationId(defaultObservation?.id ?? null);

        if (!defaultObservation) {
          setMetricEnabled(false);
        }
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }

        console.error("Unable to load satellite observations:", error);
        setSatelliteError("Unable to load satellite observations.");
        setMetricEnabled(false);
      })
      .finally(() => {
        if (!cancelled) {
          setSatelliteLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedFieldId]);

  // Existing anomaly polygons are NDVI-only until 8H.
  useEffect(() => {
    setAnomalyData(EMPTY_ANOMALIES);
    setSelectedAnomalyId(null);
    setAnomalyError(null);

    if (!selectedObservationId || selectedMetricType !== "ndvi") {
      setAnomalyLoading(false);
      return;
    }

    let cancelled = false;
    setAnomalyLoading(true);

    void listSatelliteAnomalies(selectedObservationId)
      .then((result) => {
        if (!cancelled) {
          setAnomalyData(result);
        }
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }

        console.error("Failed to load satellite anomalies:", error);
        setAnomalyData(EMPTY_ANOMALIES);
        setAnomalyError("Unable to load potential stress zones.");
      })
      .finally(() => {
        if (!cancelled) {
          setAnomalyLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedObservationId, selectedMetricType]);

  // Create MapLibre once.
  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLES[previousMapModeRef.current],
      center: [76.7794, 30.7333],
      zoom: 11,
    });

    mapRef.current = map;

    map.on("error", (event) => {
      console.error("MapLibre error:", event.error ?? event);
    });

    map.on("sourcedata", (event) => {
      if (event.sourceId === METRIC_SOURCE_ID && event.isSourceLoaded) {
        console.log("Satellite metric raster source loaded.");
      }
    });

    map.addControl(new maplibregl.NavigationControl(), "bottom-right");
    map.addControl(
      new maplibregl.GeolocateControl({
        positionOptions: { enableHighAccuracy: true },
        trackUserLocation: false,
        showUserLocation: true,
      }),
      "bottom-right",
    );
    map.addControl(
      new GeocodingControl({ apiKey: MAPTILER_KEY, maplibregl }),
      "top-right",
    );

    map.once("load", () => {
      map.resize();
      restoreCustomLayers(map);

      const field = fieldsRef.current.find(
        (candidate) => candidate.id === selectedFieldIdRef.current,
      );

      if (field) {
        zoomToField(map, field);
      }
    });

    map.on("click", (event) => {
      if (drawingRef.current) {
        return;
      }

      if (map.getLayer(ANOMALY_FILL_LAYER_ID)) {
        const anomalyHits = map.queryRenderedFeatures(event.point, {
          layers: [ANOMALY_FILL_LAYER_ID],
        });
        const anomalyId = anomalyHits[0]?.properties?.id;

        if (typeof anomalyId === "string") {
          setSelectedAnomalyId(anomalyId);
          return;
        }
      }

      if (!map.getLayer("farm-fields-fill")) {
        return;
      }

      const fieldHits = map.queryRenderedFeatures(event.point, {
        layers: ["farm-fields-fill"],
      });
      const fieldId = fieldHits[0]?.properties?.fieldId;

      if (typeof fieldId === "string") {
        selectFieldRef.current(fieldId);
      }
    });

    map.on("mousemove", (event) => {
      if (!map.getLayer(ANOMALY_FILL_LAYER_ID)) {
        map.getCanvas().style.cursor = "";
        return;
      }

      const hits = map.queryRenderedFeatures(event.point, {
        layers: [ANOMALY_FILL_LAYER_ID],
      });
      map.getCanvas().style.cursor = hits.length > 0 ? "pointer" : "";
    });

    return () => {
      try {
        drawRef.current?.stop();
      } catch {
        // Ignore TerraDraw cleanup problems during unmount.
      }

      map.remove();
      mapRef.current = null;
      drawRef.current = null;
    };
  }, []);

  /*
   * Keep MapLibre's internal canvas size synchronized with dashboard layout
   * changes. This matters when the field/details panels change the map width.
   */
  useEffect(() => {
    const container = containerRef.current;
    const map = mapRef.current;

    if (!container || !map || typeof ResizeObserver === "undefined") {
      return;
    }

    const observer = new ResizeObserver(() => {
      map.resize();
    });

    observer.observe(container);

    return () => {
      observer.disconnect();
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !map.getSource("farm-fields")) {
      return;
    }

    updateFieldSource(map, fields);
    applySelectedFieldStyle(map, selectedFieldId, metricEnabled);
  }, [fields, selectedFieldId, metricEnabled]);

  useEffect(() => {
    drawingRef.current = drawing;

    if (!drawRef.current) {
      return;
    }

    try {
      drawRef.current.setMode(drawing ? "polygon" : "select");
    } catch (error) {
      console.error("Failed to switch drawing mode:", error);
    }
  }, [drawing]);

  useEffect(() => {
    if (!selectedFieldId) {
      return;
    }

    const field = fields.find((candidate) => candidate.id === selectedFieldId);
    const map = mapRef.current;

    if (!field || !map) {
      return;
    }

    /*
     * Camera movement does not depend on MapLibre's source/tile loading state.
     * Waiting for map.loaded()/isStyleLoaded() can block forever while raster
     * tiles are loading, which is why switching the base style used to be the
     * only action that triggered the zoom.
     *
     * Two animation frames give React/layout changes (including side panels)
     * time to settle before fitBounds measures the map canvas.
     */
    let secondFrameId = 0;

    const firstFrameId = window.requestAnimationFrame(() => {
      secondFrameId = window.requestAnimationFrame(() => {
        map.resize();
        map.stop();
        zoomToField(map, field);
      });
    });

    return () => {
      window.cancelAnimationFrame(firstFrameId);

      if (secondFrameId) {
        window.cancelAnimationFrame(secondFrameId);
      }
    };
  }, [selectedFieldId, fields]);

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !map.getSource("farm-fields")) {
      return;
    }

    installMetricLayer(
      map,
      metricEnabled ? selectedMetric : null,
      metricOpacity,
    );
    applySelectedFieldStyle(map, selectedFieldId, metricEnabled);
  }, [
    selectedFieldId,
    selectedMetric,
    selectedMetricType,
    metricEnabled,
    metricOpacity,
  ]);

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !map.getSource("farm-fields")) {
      return;
    }

    installAnomalyLayers(
      map,
      anomalyData,
      metricEnabled && selectedMetricType === "ndvi",
      selectedAnomalyId,
    );
  }, [anomalyData, metricEnabled, selectedMetricType]);

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !map.getLayer(ANOMALY_OUTLINE_LAYER_ID)) {
      return;
    }

    updateSelectedAnomalyStyle(map, selectedAnomalyId);
  }, [selectedAnomalyId]);

  // setStyle() removes custom sources/layers, so restore them afterwards.
  useEffect(() => {
    const map = mapRef.current;

    if (!map || previousMapModeRef.current === mapMode) {
      return;
    }

    previousMapModeRef.current = mapMode;
    map.setStyle(MAP_STYLES[mapMode]);

    map.once("style.load", () => {
      restoreCustomLayers(map);

      const field = fieldsRef.current.find(
        (candidate) => candidate.id === selectedFieldIdRef.current,
      );

      if (field) {
        zoomToField(map, field);
      }
    });
  }, [mapMode]);

  function handleMetricTypeChange(metricType: SatelliteMetricType) {
    setSelectedMetricType(metricType);
    setSelectedAnomalyId(null);

    const currentMetric = getMetricForObservation(
      satelliteObservations,
      selectedObservationId,
      metricType,
    );

    if (currentMetric) {
      return;
    }

    const fallbackObservation = getDefaultObservation(
      satelliteObservations,
      metricType,
    );

    setSelectedObservationId(fallbackObservation?.id ?? null);

    if (!fallbackObservation) {
      setMetricEnabled(false);
    }
  }

  return (
    <div className="farm-map">
      <div ref={containerRef} className="map-canvas" />

      {selectedFieldId && !drawing && (
        <SatelliteAnalysisPanel
          observations={satelliteObservations}
          selectedObservationId={selectedObservationId}
          selectedMetricType={selectedMetricType}
          metricEnabled={metricEnabled}
          metricOpacity={metricOpacity}
          satelliteLoading={satelliteLoading}
          satelliteError={satelliteError}
          anomalyData={anomalyData}
          anomalyLoading={anomalyLoading}
          anomalyError={anomalyError}
          selectedAnomaly={selectedAnomaly}
          onSelectObservation={(observationId) => {
            setSelectedObservationId(observationId);
            setSelectedAnomalyId(null);
          }}
          onSelectMetricType={handleMetricTypeChange}
          onMetricEnabledChange={setMetricEnabled}
          onMetricOpacityChange={setMetricOpacity}
          onZoomToAnomaly={(feature) => {
            const map = mapRef.current;

            if (map) {
              zoomToAnomaly(map, feature);
            }
          }}
        />
      )}
    </div>
  );
}
