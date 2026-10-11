import { useEffect, useMemo, useRef, useState } from "react";

import maplibregl, {
  type GeoJSONSource,
  type Map as MapLibreMap,
} from "maplibre-gl";

import { GeocodingControl } from "@maptiler/geocoding-control/maplibregl";

import {
  TerraDraw,
  TerraDrawPolygonMode,
  TerraDrawSelectMode,
} from "terra-draw";

import { TerraDrawMapLibreGLAdapter } from "terra-draw-maplibre-gl-adapter";

import { listSatelliteAnomalies, listSatelliteObservations } from "../lib/api";

import type {
  Field,
  PolygonGeometry,
  SatelliteAnomalyFeature,
  SatelliteAnomalyFeatureCollection,
  SatelliteObservation,
} from "../types/api";

import type { MapMode } from "../types/map";

type Props = {
  mapMode: MapMode;

  fields: Field[];

  selectedFieldId: string | null;

  drawing: boolean;

  onSelectField: (fieldId: string) => void;

  onPolygonFinished: (boundary: PolygonGeometry) => void;
};

type RasterObservation = SatelliteObservation & {
  ndvi_raster_uri: string;
};

const MAPTILER_KEY = import.meta.env.VITE_MAPTILER_KEY;

const TILER_URL = import.meta.env.VITE_TILER_URL ?? "http://localhost:8081";

if (!MAPTILER_KEY) {
  throw new Error("VITE_MAPTILER_KEY is missing.");
}

const MAP_STYLES = {
  hybrid: `https://api.maptiler.com/maps/hybrid-v4/style.json?key=${MAPTILER_KEY}`,

  streets: `https://api.maptiler.com/maps/streets-v4/style.json?key=${MAPTILER_KEY}`,
};

const NDVI_SOURCE_ID = "selected-field-ndvi";

const NDVI_LAYER_ID = "selected-field-ndvi-layer";

const ANOMALY_SOURCE_ID = "satellite-anomalies";

const ANOMALY_FILL_LAYER_ID = "satellite-anomalies-fill";

const ANOMALY_OUTLINE_LAYER_ID = "satellite-anomalies-outline";

const EMPTY_ANOMALIES: SatelliteAnomalyFeatureCollection = {
  type: "FeatureCollection",

  features: [],
};

function hasNdviRaster(
  observation: SatelliteObservation,
): observation is RasterObservation {
  return (
    typeof observation.ndvi_raster_uri === "string" &&
    observation.ndvi_raster_uri.length > 0
  );
}

function getRasterObservations(
  observations: SatelliteObservation[],
): RasterObservation[] {
  return observations
    .filter(hasNdviRaster)
    .sort((first, second) =>
      second.observed_on.localeCompare(first.observed_on),
    );
}

function getDefaultObservation(
  observations: SatelliteObservation[],
): RasterObservation | null {
  const rasters = getRasterObservations(observations);

  /*
   * Prefer an observation where
   * most pixels inside the field
   * are actually valid.
   */
  const reliable = rasters.find(
    (observation) =>
      observation.valid_pixel_percent == null ||
      observation.valid_pixel_percent >= 80,
  );

  return reliable ?? rasters[0] ?? null;
}

function formatObservationDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-IN", {
    day: "2-digit",

    month: "short",

    year: "numeric",
  });
}

function buildNdviTileJsonUrl(observation: RasterObservation) {
  const params = new URLSearchParams({
    url: observation.ndvi_raster_uri,

    rescale: "0,1",

    colormap_name: "rdylgn",
  });

  return (
    `${TILER_URL}` + "/cog/WebMercatorQuad/tilejson.json?" + params.toString()
  );
}

export default function FarmMap({
  mapMode,

  fields,

  selectedFieldId,

  drawing,

  onSelectField,

  onPolygonFinished,
}: Props) {
  /*
   * ========================================
   * MAP REFS
   * ========================================
   */

  const containerRef = useRef<HTMLDivElement | null>(null);

  const mapRef = useRef<MapLibreMap | null>(null);

  const drawRef = useRef<TerraDraw | null>(null);

  /*
   * ========================================
   * SATELLITE STATE
   * ========================================
   */

  const [satelliteObservations, setSatelliteObservations] = useState<
    SatelliteObservation[]
  >([]);

  const [selectedObservationId, setSelectedObservationId] = useState<
    string | null
  >(null);

  const [ndviEnabled, setNdviEnabled] = useState(false);

  const [ndviOpacity, setNdviOpacity] = useState(0.72);

  const [satelliteLoading, setSatelliteLoading] = useState(false);

  const [satelliteError, setSatelliteError] = useState<string | null>(null);

  /*
   * ========================================
   * ANOMALY STATE
   * ========================================
   */

  const [anomalyData, setAnomalyData] =
    useState<SatelliteAnomalyFeatureCollection>(EMPTY_ANOMALIES);

  const [selectedAnomalyId, setSelectedAnomalyId] = useState<string | null>(
    null,
  );

  const [anomalyLoading, setAnomalyLoading] = useState(false);

  const [anomalyError, setAnomalyError] = useState<string | null>(null);

  /*
   * ========================================
   * REFS FOR MAPLIBRE CALLBACKS
   * ========================================
   *
   * MapLibre event callbacks are created
   * once. These refs let those callbacks
   * always read the latest React state.
   */

  const fieldsRef = useRef(fields);

  const drawingRef = useRef(drawing);

  const selectFieldRef = useRef(onSelectField);

  const polygonFinishedRef = useRef(onPolygonFinished);

  const selectedFieldIdRef = useRef<string | null>(selectedFieldId);

  const satelliteObservationsRef = useRef<SatelliteObservation[]>(
    satelliteObservations,
  );

  const selectedObservationIdRef = useRef<string | null>(selectedObservationId);

  const ndviEnabledRef = useRef(ndviEnabled);

  const ndviOpacityRef = useRef(ndviOpacity);

  const anomalyDataRef =
    useRef<SatelliteAnomalyFeatureCollection>(EMPTY_ANOMALIES);

  const selectedAnomalyIdRef = useRef<string | null>(null);

  /*
   * Used so the first render does not
   * unnecessarily call map.setStyle().
   */
  const previousMapModeRef = useRef<MapMode>(mapMode);

  /*
   * Keep refs current.
   */

  fieldsRef.current = fields;

  drawingRef.current = drawing;

  selectFieldRef.current = onSelectField;

  polygonFinishedRef.current = onPolygonFinished;

  selectedFieldIdRef.current = selectedFieldId;

  satelliteObservationsRef.current = satelliteObservations;

  selectedObservationIdRef.current = selectedObservationId;

  ndviEnabledRef.current = ndviEnabled;

  ndviOpacityRef.current = ndviOpacity;

  anomalyDataRef.current = anomalyData;

  selectedAnomalyIdRef.current = selectedAnomalyId;

  /*
   * ========================================
   * DERIVED DATA
   * ========================================
   */

  const rasterObservations = getRasterObservations(satelliteObservations);

  const selectedRasterObservation =
    rasterObservations.find(
      (observation) => observation.id === selectedObservationId,
    ) ?? null;

  const selectedAnomaly = useMemo(
    () =>
      anomalyData.features.find(
        (feature) => feature.id === selectedAnomalyId,
      ) ?? null,

    [anomalyData, selectedAnomalyId],
  );

  /*
   * ========================================
   * FIELD GEOJSON
   * ========================================
   */

  function buildFieldsGeoJson(): any {
    return {
      type: "FeatureCollection",

      features: fieldsRef.current.map((field) => ({
        type: "Feature",

        properties: {
          fieldId: field.id,

          name: field.name,
        },

        geometry: field.boundary,
      })),
    };
  }

  /*
   * ========================================
   * FIELD LAYERS
   * ========================================
   */

  function installFieldLayers(map: MapLibreMap) {
    const existingSource = map.getSource("farm-fields");

    if (existingSource) {
      (existingSource as GeoJSONSource).setData(buildFieldsGeoJson());

      return;
    }

    map.addSource("farm-fields", {
      type: "geojson",

      data: buildFieldsGeoJson(),
    });

    map.addLayer({
      id: "farm-fields-fill",

      type: "fill",

      source: "farm-fields",

      paint: {
        "fill-color": "#4ade80",

        "fill-opacity": 0.28,
      },
    });

    map.addLayer({
      id: "farm-fields-outline",

      type: "line",

      source: "farm-fields",

      paint: {
        "line-color": "#ffffff",

        "line-width": 2,
      },
    });

    map.addLayer({
      id: "farm-field-labels",

      type: "symbol",

      source: "farm-fields",

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

  /*
   * Highlight selected field.
   *
   * When NDVI is active the green field fill
   * becomes transparent. Otherwise green
   * would show through cloudy / nodata areas
   * and falsely look like healthy vegetation.
   */

  function applySelectedFieldStyle(map: MapLibreMap) {
    if (map.getLayer("farm-fields-outline")) {
      map.setPaintProperty(
        "farm-fields-outline",

        "line-width",

        [
          "case",

          ["==", ["get", "fieldId"], selectedFieldIdRef.current ?? ""],

          5,

          2,
        ],
      );
    }

    if (map.getLayer("farm-fields-fill")) {
      map.setPaintProperty(
        "farm-fields-fill",

        "fill-opacity",

        [
          "case",

          ["==", ["get", "fieldId"], selectedFieldIdRef.current ?? ""],

          ndviEnabledRef.current ? 0 : 0.5,

          0.28,
        ],
      );
    }
  }

  /*
   * ========================================
   * NDVI RASTER
   * ========================================
   */

  function removeNdviLayer(map: MapLibreMap) {
    if (map.getLayer(NDVI_LAYER_ID)) {
      map.removeLayer(NDVI_LAYER_ID);
    }

    if (map.getSource(NDVI_SOURCE_ID)) {
      map.removeSource(NDVI_SOURCE_ID);
    }
  }

  function getCurrentRasterObservation(): RasterObservation | null {
    const observations = getRasterObservations(
      satelliteObservationsRef.current,
    );

    const selected = observations.find(
      (observation) => observation.id === selectedObservationIdRef.current,
    );

    return selected ?? null;
  }

  function installNdviLayer(map: MapLibreMap) {
    removeNdviLayer(map);

    if (!ndviEnabledRef.current) {
      return;
    }

    if (!selectedFieldIdRef.current) {
      return;
    }

    const observation = getCurrentRasterObservation();

    if (!observation) {
      console.warn("NDVI enabled but no raster observation is selected.");

      return;
    }

    const tileJsonUrl = buildNdviTileJsonUrl(observation);

    console.log("Installing NDVI raster:", {
      observation: observation.id,

      raster: observation.ndvi_raster_uri,

      tileJsonUrl,
    });

    map.addSource(NDVI_SOURCE_ID, {
      type: "raster",

      /*
       * TiTiler TileJSON supplies:
       *
       * - tile URL
       * - bounds
       * - tile size
       * - min zoom
       * - max zoom
       *
       * Therefore do not hard-code tileSize.
       */
      url: tileJsonUrl,
    });

    const layer = {
      id: NDVI_LAYER_ID,

      type: "raster" as const,

      source: NDVI_SOURCE_ID,

      paint: {
        "raster-opacity": ndviOpacityRef.current,

        "raster-resampling": "nearest" as const,

        "raster-fade-duration": 0,
      },
    };

    if (map.getLayer("farm-fields-outline")) {
      map.addLayer(
        layer,

        "farm-fields-outline",
      );
    } else {
      map.addLayer(layer);
    }
  }

  /*
   * ========================================
   * ANOMALY / STRESS ZONES
   * ========================================
   */

  function removeAnomalyLayers(map: MapLibreMap) {
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

  function installAnomalyLayers(map: MapLibreMap) {
    removeAnomalyLayers(map);

    /*
     * Stress polygons are shown only while
     * NDVI mode is active.
     */
    if (!ndviEnabledRef.current) {
      return;
    }

    const data = anomalyDataRef.current;

    map.addSource(ANOMALY_SOURCE_ID, {
      type: "geojson",

      data: data as any,
    });

    const fillLayer = {
      id: ANOMALY_FILL_LAYER_ID,

      type: "fill" as const,

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

    const outlineLayer = {
      id: ANOMALY_OUTLINE_LAYER_ID,

      type: "line" as const,

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

          ["==", ["get", "id"], selectedAnomalyIdRef.current ?? ""],

          5,

          2.5,
        ],

        "line-opacity": 0.98,
      },
    };

    /*
     * Keep anomaly polygons:
     *
     * above NDVI raster
     * below field boundary
     */

    if (map.getLayer("farm-fields-outline")) {
      map.addLayer(
        fillLayer,

        "farm-fields-outline",
      );

      map.addLayer(
        outlineLayer,

        "farm-fields-outline",
      );
    } else {
      map.addLayer(fillLayer);

      map.addLayer(outlineLayer);
    }
  }

  /*
   * ========================================
   * ZOOM HELPERS
   * ========================================
   */

  function zoomToField(field: Field) {
    const map = mapRef.current;

    if (!map) {
      return;
    }

    const ring = field.boundary.coordinates[0];

    if (!ring || ring.length === 0) {
      return;
    }

    const first = ring[0];

    const bounds = new maplibregl.LngLatBounds(
      [first[0], first[1]],

      [first[0], first[1]],
    );

    for (const coordinate of ring) {
      bounds.extend([coordinate[0], coordinate[1]]);
    }

    map.fitBounds(bounds, {
      padding: {
        top: 90,

        bottom: 90,

        left: 90,

        right: 420,
      },

      maxZoom: 19,

      duration: 900,
    });
  }

  function zoomToAnomaly(feature: SatelliteAnomalyFeature) {
    const map = mapRef.current;

    if (!map) {
      return;
    }

    const bounds = new maplibregl.LngLatBounds();

    /*
     * MultiPolygon:
     *
     * polygon
     *   -> ring
     *      -> coordinate
     */

    for (const polygon of feature.geometry.coordinates) {
      for (const ring of polygon) {
        for (const coordinate of ring) {
          bounds.extend([coordinate[0], coordinate[1]]);
        }
      }
    }

    if (bounds.isEmpty()) {
      return;
    }

    map.fitBounds(bounds, {
      padding: {
        top: 120,

        bottom: 120,

        left: 340,

        right: 420,
      },

      maxZoom: 20,

      duration: 700,
    });
  }

  /*
   * ========================================
   * TERRA DRAW
   * ========================================
   */

  function createDrawingSystem(map: MapLibreMap) {
    try {
      drawRef.current?.stop();
    } catch (error) {
      console.warn("Unable to stop previous TerraDraw instance:", error);
    }

    const draw = new TerraDraw({
      adapter: new TerraDrawMapLibreGLAdapter({
        map,
      }),

      modes: [
        new TerraDrawPolygonMode({
          showCoordinatePoints: true,
        }),

        new TerraDrawSelectMode({
          flags: {
            polygon: {
              feature: {
                draggable: true,

                coordinates: {
                  draggable: true,

                  deletable: true,

                  midpoints: true,
                },
              },
            },
          },
        }),
      ],
    });

    draw.start();

    try {
      draw.setMode(drawingRef.current ? "polygon" : "select");
    } catch (error) {
      console.error("Unable to set TerraDraw mode:", error);
    }

    draw.on(
      "finish",

      (id, context) => {
        if (context.action !== "draw") {
          return;
        }

        const feature = draw
          .getSnapshot()
          .find((candidate) => candidate.id === id);

        if (!feature || feature.geometry.type !== "Polygon") {
          return;
        }

        const boundary: PolygonGeometry = {
          type: "Polygon",

          coordinates: feature.geometry.coordinates as number[][][],
        };

        polygonFinishedRef.current(boundary);

        draw.clear();

        try {
          draw.setMode("select");
        } catch (error) {
          console.error("Unable to leave polygon mode:", error);
        }
      },
    );

    drawRef.current = draw;
  }

  /*
   * ========================================
   * LOAD SATELLITE OBSERVATIONS
   * ========================================
   */

  useEffect(() => {
    let cancelled = false;

    /*
     * Clear old field satellite state
     * immediately when changing fields.
     */

    setSatelliteObservations([]);

    setSelectedObservationId(null);

    setSatelliteError(null);

    setAnomalyData(EMPTY_ANOMALIES);

    setSelectedAnomalyId(null);

    setAnomalyError(null);

    if (!selectedFieldId) {
      setSatelliteLoading(false);

      setNdviEnabled(false);

      return;
    }

    setSatelliteLoading(true);

    void listSatelliteObservations(selectedFieldId)
      .then((observations) => {
        if (cancelled) {
          return;
        }

        setSatelliteObservations(observations);

        const defaultObservation = getDefaultObservation(observations);

        setSelectedObservationId(defaultObservation?.id ?? null);

        /*
         * No real raster means NDVI
         * cannot stay enabled.
         */

        if (!defaultObservation) {
          setNdviEnabled(false);
        }
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }

        console.error("Unable to load satellite observations:", error);

        setSatelliteError("Unable to load satellite observations.");

        setNdviEnabled(false);
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

  /*
   * ========================================
   * LOAD ANOMALY POLYGONS
   * ========================================
   *
   * Every satellite observation can have
   * different stress zones.
   *
   * Changing observation therefore replaces
   * the anomaly GeoJSON completely.
   */

  useEffect(() => {
    setAnomalyData(EMPTY_ANOMALIES);

    setSelectedAnomalyId(null);

    setAnomalyError(null);

    if (!selectedObservationId) {
      setAnomalyLoading(false);

      return;
    }

    let cancelled = false;

    setAnomalyLoading(true);

    async function loadAnomalies() {
      try {
        const result = await listSatelliteAnomalies(selectedObservationId!);

        if (cancelled) {
          return;
        }

        setAnomalyData(result);

        setSelectedAnomalyId(null);
      } catch (error) {
        if (cancelled) {
          return;
        }

        console.error("Failed to load satellite anomalies:", error);

        setAnomalyData(EMPTY_ANOMALIES);

        setSelectedAnomalyId(null);

        setAnomalyError("Unable to load potential stress zones.");
      } finally {
        if (!cancelled) {
          setAnomalyLoading(false);
        }
      }
    }

    void loadAnomalies();

    return () => {
      cancelled = true;
    };
  }, [selectedObservationId]);

  /*
   * ========================================
   * CREATE MAP ONCE
   * ========================================
   */

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    const map = new maplibregl.Map({
      container: containerRef.current,

      style: MAP_STYLES[mapMode],

      center: [76.7794, 30.7333],

      zoom: 11,
    });

    mapRef.current = map;

    map.on(
      "load",

      () => {
        console.log("MapLibre loaded", {
          zoom: map.getZoom(),

          center: map.getCenter().toArray(),
        });
      },
    );

    map.on(
      "error",

      (event) => {
        console.error("MapLibre error:", event.error ?? event);
      },
    );

    map.on(
      "sourcedata",

      (event) => {
        if (event.sourceId === NDVI_SOURCE_ID && event.isSourceLoaded) {
          console.log("NDVI raster source loaded.");
        }
      },
    );

    map.addControl(
      new maplibregl.NavigationControl(),

      "bottom-right",
    );

    map.addControl(
      new maplibregl.GeolocateControl({
        positionOptions: {
          enableHighAccuracy: true,
        },

        trackUserLocation: false,

        showUserLocation: true,
      }),

      "bottom-right",
    );

    map.addControl(
      new GeocodingControl({
        apiKey: MAPTILER_KEY,

        maplibregl,
      }),

      "top-right",
    );

    map.once(
      "load",

      () => {
        /*
         * Important because this map lives
         * inside the dashboard layout.
         */
        map.resize();

        installFieldLayers(map);

        applySelectedFieldStyle(map);

        installNdviLayer(map);

        installAnomalyLayers(map);

        createDrawingSystem(map);

        /*
         * If fields were already available
         * before the map loaded, zoom to the
         * selected one now.
         */

        if (selectedFieldIdRef.current) {
          const field = fieldsRef.current.find(
            (candidate) => candidate.id === selectedFieldIdRef.current,
          );

          if (field) {
            zoomToField(field);
          }
        }
      },
    );

    /*
     * ====================================
     * MAP CLICK
     * ====================================
     *
     * Priority:
     *
     * 1. anomaly polygon
     * 2. normal field
     */

    map.on(
      "click",

      (event) => {
        if (drawingRef.current) {
          return;
        }

        /*
         * Stress zone first.
         */

        if (map.getLayer(ANOMALY_FILL_LAYER_ID)) {
          const anomalyHits = map.queryRenderedFeatures(
            event.point,

            {
              layers: [ANOMALY_FILL_LAYER_ID],
            },
          );

          if (anomalyHits.length > 0) {
            const anomalyId = anomalyHits[0].properties?.id;

            if (typeof anomalyId === "string") {
              setSelectedAnomalyId(anomalyId);

              return;
            }
          }
        }

        /*
         * Normal field selection.
         */

        if (!map.getLayer("farm-fields-fill")) {
          return;
        }

        const fieldHits = map.queryRenderedFeatures(
          event.point,

          {
            layers: ["farm-fields-fill"],
          },
        );

        const fieldId = fieldHits[0]?.properties?.fieldId;

        if (typeof fieldId === "string") {
          selectFieldRef.current(fieldId);
        }
      },
    );

    /*
     * Pointer cursor over anomaly zones.
     */

    map.on(
      "mousemove",

      (event) => {
        if (!map.getLayer(ANOMALY_FILL_LAYER_ID)) {
          map.getCanvas().style.cursor = "";

          return;
        }

        const hits = map.queryRenderedFeatures(
          event.point,

          {
            layers: [ANOMALY_FILL_LAYER_ID],
          },
        );

        map.getCanvas().style.cursor = hits.length > 0 ? "pointer" : "";
      },
    );

    return () => {
      try {
        drawRef.current?.stop();
      } catch {
        /*
         * Ignore TerraDraw cleanup
         * problems during unmount.
         */
      }

      map.remove();

      mapRef.current = null;

      drawRef.current = null;
    };
  }, []);

  /*
   * ========================================
   * UPDATE FIELD GEOJSON
   * ========================================
   */

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !map.isStyleLoaded()) {
      return;
    }

    const source = map.getSource("farm-fields");

    if (source) {
      (source as GeoJSONSource).setData(buildFieldsGeoJson());
    }

    applySelectedFieldStyle(map);
  }, [fields]);

  /*
   * ========================================
   * TERRA DRAW MODE
   * ========================================
   */

  useEffect(() => {
    drawingRef.current = drawing;

    const draw = drawRef.current;

    if (!draw) {
      return;
    }

    try {
      draw.setMode(drawing ? "polygon" : "select");
    } catch (error) {
      console.error("Failed to switch drawing mode:", error);
    }
  }, [drawing]);

  /*
   * ========================================
   * ZOOM TO SELECTED FIELD
   * ========================================
   */

  useEffect(() => {
    if (!selectedFieldId) {
      return;
    }

    const field = fields.find((candidate) => candidate.id === selectedFieldId);

    if (!field) {
      return;
    }

    const map = mapRef.current;

    if (!map) {
      return;
    }

    const performZoom = () => {
      zoomToField(field);
    };

    if (map.loaded()) {
      performZoom();
    } else {
      map.once("load", performZoom);
    }

    return () => {
      map.off("load", performZoom);
    };
  }, [selectedFieldId, fields]);

  /*
   * ========================================
   * SELECTED FIELD STYLE
   * ========================================
   */

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !map.isStyleLoaded()) {
      return;
    }

    applySelectedFieldStyle(map);
  }, [selectedFieldId, ndviEnabled]);

  /*
   * ========================================
   * INSTALL / UPDATE NDVI
   * ========================================
   */

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !map.isStyleLoaded()) {
      return;
    }

    installNdviLayer(map);

    applySelectedFieldStyle(map);
  }, [
    selectedFieldId,

    satelliteObservations,

    selectedObservationId,

    ndviEnabled,

    ndviOpacity,
  ]);

  /*
   * ========================================
   * INSTALL / UPDATE ANOMALY LAYERS
   * ========================================
   */

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !map.isStyleLoaded()) {
      return;
    }

    installAnomalyLayers(map);
  }, [anomalyData, ndviEnabled]);

  /*
   * ========================================
   * SELECTED ANOMALY HIGHLIGHT
   * ========================================
   */

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !map.getLayer(ANOMALY_OUTLINE_LAYER_ID)) {
      return;
    }

    map.setPaintProperty(
      ANOMALY_OUTLINE_LAYER_ID,

      "line-width",

      ["case", ["==", ["get", "id"], selectedAnomalyId ?? ""], 5, 2.5],
    );
  }, [selectedAnomalyId]);

  /*
   * ========================================
   * SWITCH MAPTILER STYLE
   * ========================================
   *
   * map.setStyle() destroys our custom
   * sources/layers, therefore restore:
   *
   * - field GeoJSON
   * - NDVI raster
   * - anomaly polygons
   * - TerraDraw
   */

  useEffect(() => {
    const map = mapRef.current;

    if (!map) {
      return;
    }

    if (previousMapModeRef.current === mapMode) {
      return;
    }

    previousMapModeRef.current = mapMode;

    map.setStyle(MAP_STYLES[mapMode]);

    map.once(
      "style.load",

      () => {
        installFieldLayers(map);

        installNdviLayer(map);

        installAnomalyLayers(map);

        applySelectedFieldStyle(map);

        createDrawingSystem(map);

        if (selectedFieldIdRef.current) {
          const field = fieldsRef.current.find(
            (candidate) => candidate.id === selectedFieldIdRef.current,
          );

          if (field) {
            zoomToField(field);
          }
        }
      },
    );
  }, [mapMode]);

  /*
   * ========================================
   * RENDER
   * ========================================
   */

  return (
    <div className="farm-map">
      <div ref={containerRef} className="map-canvas" />

      {selectedFieldId && !drawing && (
        <div className="ndvi-map-panel">
          <div className="ndvi-map-panel-header">
            <div>
              <span className="ndvi-map-eyebrow">FIELD ANALYSIS</span>

              <strong>Satellite layer</strong>
            </div>

            {selectedRasterObservation?.resolution_m != null && (
              <span className="ndvi-resolution-badge">
                {selectedRasterObservation.resolution_m.toFixed(0)}m
              </span>
            )}
          </div>

          <div className="ndvi-layer-switch">
            <button
              type="button"
              className={!ndviEnabled ? "active" : ""}
              onClick={() => setNdviEnabled(false)}
            >
              Normal
            </button>

            <button
              type="button"
              className={ndviEnabled ? "active" : ""}
              disabled={satelliteLoading || rasterObservations.length === 0}
              onClick={() => setNdviEnabled(true)}
            >
              NDVI
            </button>
          </div>

          {satelliteLoading && (
            <p className="ndvi-map-message">Loading satellite data…</p>
          )}

          {satelliteError && (
            <p className="ndvi-map-message error">{satelliteError}</p>
          )}

          {!satelliteLoading &&
            !satelliteError &&
            rasterObservations.length === 0 && (
              <p className="ndvi-map-message">
                No processed NDVI raster is available for this field.
              </p>
            )}

          {rasterObservations.length > 0 && (
            <>
              <label className="ndvi-map-field">
                <span>Observation</span>

                <select
                  value={selectedObservationId ?? ""}
                  onChange={(event) => {
                    setSelectedObservationId(event.target.value);

                    setSelectedAnomalyId(null);
                  }}
                >
                  {rasterObservations.map((observation) => (
                    <option key={observation.id} value={observation.id}>
                      {formatObservationDate(observation.observed_on)}

                      {observation.valid_pixel_percent != null
                        ? ` · ${observation.valid_pixel_percent.toFixed(0)}% valid`
                        : ""}
                    </option>
                  ))}
                </select>
              </label>

              {ndviEnabled && (
                <>
                  <div className="ndvi-opacity-row">
                    <span>Opacity</span>

                    <strong>{Math.round(ndviOpacity * 100)}%</strong>
                  </div>

                  <input
                    className="ndvi-opacity-slider"
                    type="range"
                    min="0.2"
                    max="1"
                    step="0.05"
                    value={ndviOpacity}
                    onChange={(event) =>
                      setNdviOpacity(Number(event.target.value))
                    }
                  />

                  <div className="ndvi-map-legend">
                    <span>Low</span>

                    <div className="ndvi-map-gradient" />

                    <span>High</span>
                  </div>

                  <div className="ndvi-map-scale">
                    <span>0.0</span>

                    <span>0.5</span>

                    <span>1.0</span>
                  </div>
                </>
              )}

              {selectedRasterObservation && (
                <div className="ndvi-map-metadata">
                  {selectedRasterObservation.ndvi_mean != null && (
                    <span>
                      Mean{" "}
                      <strong>
                        {selectedRasterObservation.ndvi_mean.toFixed(2)}
                      </strong>
                    </span>
                  )}

                  {selectedRasterObservation.ndvi_median != null && (
                    <span>
                      Median{" "}
                      <strong>
                        {selectedRasterObservation.ndvi_median.toFixed(2)}
                      </strong>
                    </span>
                  )}

                  {selectedRasterObservation.valid_pixel_percent != null && (
                    <span>
                      Valid{" "}
                      <strong>
                        {selectedRasterObservation.valid_pixel_percent.toFixed(
                          0,
                        )}
                        %
                      </strong>
                    </span>
                  )}
                </div>
              )}

              {ndviEnabled && (
                <div className="anomaly-section">
                  <div className="anomaly-section-header">
                    <span>Potential stress zones</span>

                    <strong>{anomalyData.features.length}</strong>
                  </div>

                  {anomalyLoading && (
                    <p className="anomaly-hint">Analysing detected zones…</p>
                  )}

                  {anomalyError && (
                    <p className="ndvi-map-message error">{anomalyError}</p>
                  )}

                  {!anomalyLoading &&
                    !anomalyError &&
                    anomalyData.features.length === 0 && (
                      <p className="anomaly-empty">
                        No significant low-NDVI zones were detected for this
                        observation.
                      </p>
                    )}

                  {!anomalyLoading && anomalyData.features.length > 0 && (
                    <p className="anomaly-hint">
                      Colored outlines mark areas performing below this
                      field&apos;s normal NDVI baseline. Click a zone on the map
                      for details.
                    </p>
                  )}

                  {selectedAnomaly && (
                    <div
                      className={`anomaly-detail severity-${selectedAnomaly.properties.severity}`}
                    >
                      <div className="anomaly-detail-title">
                        <div>
                          <span>
                            Zone {selectedAnomaly.properties.zone_index}
                          </span>

                          <strong>Potential stress</strong>
                        </div>

                        <span
                          className={`anomaly-severity severity-${selectedAnomaly.properties.severity}`}
                        >
                          {selectedAnomaly.properties.severity}
                        </span>
                      </div>

                      <div className="anomaly-stats">
                        <div>
                          <span>Area</span>

                          <strong>
                            {selectedAnomaly.properties.area_acres.toFixed(2)}{" "}
                            ac
                          </strong>
                        </div>

                        <div>
                          <span>Zone NDVI</span>

                          <strong>
                            {selectedAnomaly.properties.zone_mean_value.toFixed(
                              2,
                            )}
                          </strong>
                        </div>

                        <div>
                          <span>Field median</span>

                          <strong>
                            {selectedAnomaly.properties.field_median_value.toFixed(
                              2,
                            )}
                          </strong>
                        </div>

                        <div>
                          <span>Difference</span>

                          <strong>
                            {selectedAnomaly.properties.percent_difference !=
                            null
                              ? `${selectedAnomaly.properties.percent_difference.toFixed(0)}%`
                              : "—"}
                          </strong>
                        </div>

                        <div>
                          <span>Pixels</span>

                          <strong>
                            {selectedAnomaly.properties.pixel_count}
                          </strong>
                        </div>

                        <div>
                          <span>Lowest NDVI</span>

                          <strong>
                            {selectedAnomaly.properties.zone_min_value.toFixed(
                              2,
                            )}
                          </strong>
                        </div>
                      </div>

                      <button
                        type="button"
                        className="anomaly-zoom-button"
                        onClick={() => zoomToAnomaly(selectedAnomaly)}
                      >
                        Zoom to area
                      </button>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
