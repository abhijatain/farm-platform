import {
  useEffect,
  useRef,
} from "react";

import maplibregl, {
  type Map as MapLibreMap,
} from "maplibre-gl";

import {
  GeocodingControl,
} from "@maptiler/geocoding-control/maplibregl";

import type {
  TerraDraw,
} from "terra-draw";

import type {
  FarmSatelliteOverviewItem,
  Field,
  PolygonGeometry,
  SatelliteMetricType,
} from "../types/api";

import type {
  MapMode,
} from "../types/map";

import {
  FIELD_FILL_LAYER_ID,
  FIELD_OUTLINE_LAYER_ID,
  installFieldLayers,
  updateFieldSource,
} from "./farm-map/mapLayers";

import {
  buildMetricTileJsonUrl,
} from "./farm-map/satellite";

import {
  createDrawingSystem,
} from "./farm-map/drawing";

import {
  zoomToFields,
} from "./farm-map/mapGeometry";


type Props = {
  mapMode: MapMode;

  fields: Field[];

  overview:
    FarmSatelliteOverviewItem[];

  selectedMetricType:
    SatelliteMetricType;

  drawing: boolean;

  onSelectField:
    (fieldId: string) => void;

  onPolygonFinished:
    (
      boundary:
        PolygonGeometry,
    ) => void;
};


const MAPTILER_KEY =
  import.meta.env
    .VITE_MAPTILER_KEY;

const TILER_URL =
  import.meta.env
    .VITE_TILER_URL;


if (!MAPTILER_KEY) {
  throw new Error(
    "VITE_MAPTILER_KEY is missing.",
  );
}


if (!TILER_URL) {
  throw new Error(
    "VITE_TILER_URL is missing.",
  );
}


const MAP_STYLES = {
  hybrid:
    `https://api.maptiler.com/maps/hybrid-v4/style.json?key=${MAPTILER_KEY}`,

  streets:
    `https://api.maptiler.com/maps/streets-v4/style.json?key=${MAPTILER_KEY}`,
};


function sourceId(
  fieldId: string,
) {
  return (
    "farm-overview-metric-"
    + fieldId
  );
}


function layerId(
  fieldId: string,
) {
  return (
    "farm-overview-metric-layer-"
    + fieldId
  );
}


export default function FarmOverviewMap({
  mapMode,
  fields,
  overview,
  selectedMetricType,
  drawing,
  onSelectField,
  onPolygonFinished,
}: Props) {
  const containerRef =
    useRef<HTMLDivElement | null>(
      null,
    );

  const mapRef =
    useRef<MapLibreMap | null>(
      null,
    );

  const drawRef =
    useRef<TerraDraw | null>(
      null,
    );

  const fieldsRef =
    useRef(
      fields,
    );

  const overviewRef =
    useRef(
      overview,
    );

  const drawingRef =
    useRef(
      drawing,
    );

  const selectFieldRef =
    useRef(
      onSelectField,
    );

  const polygonFinishedRef =
    useRef(
      onPolygonFinished,
    );

  const mapModeRef =
    useRef<MapMode>(
      mapMode,
    );

  fieldsRef.current =
    fields;

  overviewRef.current =
    overview;

  drawingRef.current =
    drawing;

  selectFieldRef.current =
    onSelectField;

  polygonFinishedRef.current =
    onPolygonFinished;


  function clearMetricLayers(
    map: MapLibreMap,
  ) {
    for (
      const field
      of fieldsRef.current
    ) {
      const metricLayer =
        layerId(
          field.id,
        );

      const metricSource =
        sourceId(
          field.id,
        );

      if (
        map.getLayer(
          metricLayer,
        )
      ) {
        map.removeLayer(
          metricLayer,
        );
      }

      if (
        map.getSource(
          metricSource,
        )
      ) {
        map.removeSource(
          metricSource,
        );
      }
    }
  }


  function installMetricLayers(
    map: MapLibreMap,
  ) {
    clearMetricLayers(
      map,
    );

    for (
      const item
      of overviewRef.current
    ) {
      const metricSource =
        sourceId(
          item.field_id,
        );

      const metricLayer =
        layerId(
          item.field_id,
        );

      if (
        map.getSource(
          metricSource,
        )
      ) {
        continue;
      }

      map.addSource(
        metricSource,
        {
          type:
            "raster",

          url:
            buildMetricTileJsonUrl(
              TILER_URL,
              item.metric,
            ),
        },
      );

      const layer = {
        id:
          metricLayer,

        type:
          "raster" as const,

        source:
          metricSource,

        paint: {
          "raster-opacity":
            0.78,

          "raster-resampling":
            "nearest" as const,

          "raster-fade-duration":
            0,
        },
      };

      if (
        map.getLayer(
          FIELD_OUTLINE_LAYER_ID,
        )
      ) {
        map.addLayer(
          layer,
          FIELD_OUTLINE_LAYER_ID,
        );
      } else {
        map.addLayer(
          layer,
        );
      }
    }

    if (
      map.getLayer(
        FIELD_FILL_LAYER_ID,
      )
    ) {
      map.setPaintProperty(
        FIELD_FILL_LAYER_ID,
        "fill-opacity",
        overviewRef.current
          .length > 0
          ? 0.08
          : 0.28,
      );
    }
  }


  function recreateDrawingSystem(
    map: MapLibreMap,
  ) {
    try {
      drawRef.current
        ?.stop();
    } catch {
      // Ignore stale TerraDraw cleanup.
    }

    drawRef.current =
      createDrawingSystem({
        map,

        drawing:
          drawingRef.current,

        onPolygonFinished:
          (
            boundary,
          ) =>
            polygonFinishedRef
              .current(
                boundary,
              ),
      });
  }


  function restoreLayers(
    map: MapLibreMap,
  ) {
    installFieldLayers(
      map,
      fieldsRef.current,
    );

    installMetricLayers(
      map,
    );

    recreateDrawingSystem(
      map,
    );
  }


  useEffect(() => {
    if (
      !containerRef.current
    ) {
      return;
    }

    const map =
      new maplibregl.Map({
        container:
          containerRef.current,

        style:
          MAP_STYLES[
            mapModeRef.current
          ],

        center: [
          76.7794,
          30.7333,
        ],

        zoom:
          10.5,
      });

    mapRef.current =
      map;

    map.addControl(
      new maplibregl
        .NavigationControl(),
      "bottom-right",
    );

    map.addControl(
      new maplibregl
        .GeolocateControl({
          positionOptions: {
            enableHighAccuracy:
              true,
          },

          trackUserLocation:
            false,

          showUserLocation:
            true,
        }),
      "bottom-right",
    );

    map.addControl(
      new GeocodingControl({
        apiKey:
          MAPTILER_KEY,
      }),
      "top-right",
    );

    map.once(
      "load",
      () => {
        map.resize();

        restoreLayers(
          map,
        );

        if (
          fieldsRef.current
            .length > 0
        ) {
          zoomToFields(
            map,
            fieldsRef.current,
          );
        }
      },
    );

    map.on(
      "click",
      (
        event,
      ) => {
        if (
          drawingRef.current
        ) {
          return;
        }

        if (
          !map.getLayer(
            FIELD_FILL_LAYER_ID,
          )
        ) {
          return;
        }

        const hits =
          map.queryRenderedFeatures(
            event.point,
            {
              layers: [
                FIELD_FILL_LAYER_ID,
              ],
            },
          );

        const fieldId =
          hits[
            0
          ]?.properties
            ?.fieldId;

        if (
          typeof fieldId
          === "string"
        ) {
          selectFieldRef.current(
            fieldId,
          );
        }
      },
    );

    map.on(
      "mousemove",
      (
        event,
      ) => {
        if (
          drawingRef.current
          || !map.getLayer(
            FIELD_FILL_LAYER_ID,
          )
        ) {
          map.getCanvas()
            .style.cursor =
              drawingRef.current
                ? "crosshair"
                : "";

          return;
        }

        const hits =
          map.queryRenderedFeatures(
            event.point,
            {
              layers: [
                FIELD_FILL_LAYER_ID,
              ],
            },
          );

        map.getCanvas()
          .style.cursor =
            hits.length > 0
              ? "pointer"
              : "";
      },
    );

    return () => {
      try {
        drawRef.current
          ?.stop();
      } catch {
        // Ignore TerraDraw cleanup on unmount.
      }

      map.remove();

      mapRef.current =
        null;

      drawRef.current =
        null;
    };
  }, []);


  useEffect(() => {
    const container =
      containerRef.current;

    const map =
      mapRef.current;

    if (
      !container
      || !map
      || typeof ResizeObserver
        === "undefined"
    ) {
      return;
    }

    const observer =
      new ResizeObserver(
        () => {
          map.resize();
        },
      );

    observer.observe(
      container,
    );

    return () => {
      observer.disconnect();
    };
  }, []);


  useEffect(() => {
    const map =
      mapRef.current;

    if (
      !map
      || !map.getSource(
        "farm-fields",
      )
    ) {
      return;
    }

    updateFieldSource(
      map,
      fields,
    );

    fieldsRef.current =
      fields;

    window.requestAnimationFrame(
      () => {
        map.resize();

        if (
          fields.length > 0
        ) {
          zoomToFields(
            map,
            fields,
          );
        }
      },
    );
  }, [
    fields,
  ]);


  useEffect(() => {
    overviewRef.current =
      overview;

    const map =
      mapRef.current;

    if (
      !map
      || !map.isStyleLoaded()
    ) {
      return;
    }

    installMetricLayers(
      map,
    );
  }, [
    overview,
    selectedMetricType,
  ]);


  useEffect(() => {
    drawingRef.current =
      drawing;

    if (
      !drawRef.current
    ) {
      return;
    }

    try {
      drawRef.current.setMode(
        drawing
          ? "polygon"
          : "select",
      );
    } catch (
      error
    ) {
      console.error(
        "Unable to change field drawing mode:",
        error,
      );
    }
  }, [
    drawing,
  ]);


  useEffect(() => {
    const map =
      mapRef.current;

    if (
      !map
      || mapModeRef.current
        === mapMode
    ) {
      return;
    }

    mapModeRef.current =
      mapMode;

    map.setStyle(
      MAP_STYLES[
        mapMode
      ],
    );

    map.once(
      "style.load",
      () => {
        restoreLayers(
          map,
        );

        if (
          fieldsRef.current
            .length > 0
        ) {
          zoomToFields(
            map,
            fieldsRef.current,
          );
        }
      },
    );
  }, [
    mapMode,
  ]);


  return (
    <div className="home-map">
      <div
        ref={containerRef}
        className="home-map-canvas"
      />
    </div>
  );
}
