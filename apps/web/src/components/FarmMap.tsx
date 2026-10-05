import {
  useEffect,
  useRef,
} from "react";

import maplibregl, {
  type GeoJSONSource,
  type Map as MapLibreMap,
} from "maplibre-gl";

import {
  GeocodingControl,
} from "@maptiler/geocoding-control/maplibregl";

import {
  TerraDraw,
  TerraDrawPolygonMode,
  TerraDrawSelectMode,
} from "terra-draw";

import {
  TerraDrawMapLibreGLAdapter,
} from "terra-draw-maplibre-gl-adapter";

import type {
  Field,
  PolygonGeometry,
} from "../types/api";

import type {
  MapMode,
} from "../types/map";


type Props = {
  mapMode: MapMode;

  fields: Field[];

  selectedFieldId:
    string | null;

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


if (!MAPTILER_KEY) {
  throw new Error(
    "VITE_MAPTILER_KEY is missing.",
  );
}


const MAP_STYLES = {
  hybrid:
    `https://api.maptiler.com/maps/hybrid-v4/style.json?key=${MAPTILER_KEY}`,

  streets:
    `https://api.maptiler.com/maps/streets-v4/style.json?key=${MAPTILER_KEY}`,
};


export default function FarmMap({
  mapMode,
  fields,
  selectedFieldId,
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


  /*
   * Refs let MapLibre callbacks always use
   * the newest React values.
   */
  const fieldsRef =
    useRef(fields);

  const drawingRef =
    useRef(drawing);

  const selectFieldRef =
    useRef(onSelectField);

  const polygonFinishedRef =
    useRef(onPolygonFinished);


  fieldsRef.current =
    fields;

  drawingRef.current =
    drawing;

  selectFieldRef.current =
    onSelectField;

  polygonFinishedRef.current =
    onPolygonFinished;


  /*
   * Convert backend fields to a GeoJSON
   * FeatureCollection for MapLibre.
   */
  function buildFieldsGeoJson(): any {

    return {
      type:
        "FeatureCollection",

      features:
        fieldsRef.current.map(
          (field) => ({
            type:
              "Feature",

            properties: {
              fieldId:
                field.id,

              name:
                field.name,
            },

            geometry:
              field.boundary,
          }),
        ),
    };
  }


  /*
   * Add/update our saved field layers.
   */
  function installFieldLayers(
    map:
      MapLibreMap,
  ) {

    const existingSource =
      map.getSource(
        "farm-fields",
      );


    if (existingSource) {

      (
        existingSource as GeoJSONSource
      ).setData(
        buildFieldsGeoJson(),
      );

      return;
    }


    map.addSource(
      "farm-fields",
      {
        type:
          "geojson",

        data:
          buildFieldsGeoJson(),
      },
    );


    map.addLayer({
      id:
        "farm-fields-fill",

      type:
        "fill",

      source:
        "farm-fields",

      paint: {
        "fill-color":
          "#4ade80",

        "fill-opacity":
          0.28,
      },
    });


    map.addLayer({
      id:
        "farm-fields-outline",

      type:
        "line",

      source:
        "farm-fields",

      paint: {
        "line-color":
          "#ffffff",

        "line-width":
          2,
      },
    });


    map.addLayer({
      id:
        "farm-field-labels",

      type:
        "symbol",

      source:
        "farm-fields",

      layout: {
        "text-field":
          ["get", "name"],

        "text-size":
          13,

        "text-anchor":
          "center",
      },

      paint: {
        "text-color":
          "#ffffff",

        "text-halo-color":
          "#166534",

        "text-halo-width":
          2,
      },
    });
  }


  /*
   * Calculate bounding box of a field
   * and zoom the map to it.
   */
  function zoomToField(
    field:
      Field,
  ) {

    const map =
      mapRef.current;


    if (!map) {
      return;
    }


    const ring =
      field
        .boundary
        .coordinates[0];


    if (
      !ring ||
      ring.length === 0
    ) {
      return;
    }


    const first =
      ring[0];


    const bounds =
      new maplibregl
        .LngLatBounds(
          [
            first[0],
            first[1],
          ],
          [
            first[0],
            first[1],
          ],
        );


    for (
      const coordinate
      of ring
    ) {

      bounds.extend([
        coordinate[0],
        coordinate[1],
      ]);

    }


    map.fitBounds(
      bounds,
      {
        /*
         * Right padding accounts for the
         * field details panel.
         */
        padding: {
          top: 90,
          bottom: 90,
          left: 90,
          right: 420,
        },

        maxZoom: 18,

        duration: 900,
      },
    );
  }


  /*
   * Create/recreate Terra Draw.
   */
  function createDrawingSystem(
    map:
      MapLibreMap,
  ) {

    try {

      drawRef.current
        ?.stop();

    } catch (
      error
    ) {

      console.warn(
        "Unable to stop previous TerraDraw instance:",
        error,
      );

    }


    const draw =
      new TerraDraw({

        adapter:
          new TerraDrawMapLibreGLAdapter({
            map,
          }),

        modes: [

          new TerraDrawPolygonMode({
            showCoordinatePoints:
              true,
          }),


          new TerraDrawSelectMode({
            flags: {
              polygon: {
                feature: {
                  draggable:
                    true,

                  coordinates: {
                    draggable:
                      true,

                    deletable:
                      true,

                    midpoints:
                      true,
                  },
                },
              },
            },
          }),

        ],
      });


    draw.start();


    /*
     * Important:
     * keep the map visible.
     * We only change TerraDraw's mode.
     */
    try {

      draw.setMode(
        drawingRef.current
          ? "polygon"
          : "select",
      );

    } catch (
      error
    ) {

      console.error(
        "Unable to set TerraDraw mode:",
        error,
      );

    }


    draw.on(
      "finish",

      (
        id,
        context,
      ) => {

        /*
         * Ignore selection/edit events.
         * We only care about newly drawn
         * polygons.
         */
        if (
          context.action !==
            "draw"
        ) {
          return;
        }


        const feature =
          draw
            .getSnapshot()
            .find(
              (
                candidate,
              ) =>
                candidate.id
                  === id,
            );


        if (
          !feature ||
          feature.geometry.type
            !== "Polygon"
        ) {
          return;
        }


        const boundary:
          PolygonGeometry = {

          type:
            "Polygon",

          coordinates:
            feature.geometry.coordinates as number[][][],
        };


        polygonFinishedRef
          .current(
            boundary,
          );


        /*
         * Remove temporary drawing.
         * Saved field will be loaded from
         * the backend afterwards.
         */
        draw.clear();


        try {

          draw.setMode(
            "select",
          );

        } catch (
          error
        ) {

          console.error(
            "Unable to leave polygon mode:",
            error,
          );

        }

      },
    );


    drawRef.current =
      draw;
  }


  /*
   * Create MapLibre once.
   */
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
          MAP_STYLES.hybrid,

        center: [
          76.7794,
          30.7333,
        ],

        zoom: 11,

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

        maplibregl,

      }),

      "top-right",

    );


    map.once(
      "load",

      () => {

        installFieldLayers(
          map,
        );

        createDrawingSystem(
          map,
        );

      },
    );


    /*
     * Clicking a stored field selects it.
     */
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
            "farm-fields-fill",
          )
        ) {
          return;
        }


        const result =
          map.queryRenderedFeatures(
            event.point,

            {
              layers: [
                "farm-fields-fill",
              ],
            },
          );


        const fieldId =
          result[0]
            ?.properties
            ?.fieldId;


        if (
          typeof fieldId
            === "string"
        ) {

          selectFieldRef
            .current(
              fieldId,
            );

        }

      },
    );


    return () => {

      try {

        drawRef.current
          ?.stop();

      } catch {
        // Ignore cleanup errors.
      }


      map.remove();

      mapRef.current =
        null;

      drawRef.current =
        null;

    };

  }, []);


  /*
   * Update saved-field GeoJSON whenever
   * backend field data changes.
   */
  useEffect(() => {

    const map =
      mapRef.current;


    if (
      !map ||
      !map.isStyleLoaded()
    ) {
      return;
    }


    const source =
      map.getSource(
        "farm-fields",
      );


    if (source) {

      (
        source as GeoJSONSource
      ).setData(
        buildFieldsGeoJson(),
      );

    }

  }, [
    fields,
  ]);


  /*
   * Add Field button:
   *
   * DO NOT hide/unmount the map.
   * Just change TerraDraw mode.
   */
  useEffect(() => {

    drawingRef.current =
      drawing;


    const draw =
      drawRef.current;


    if (!draw) {
      return;
    }


    try {

      draw.setMode(
        drawing
          ? "polygon"
          : "select",
      );

    } catch (
      error
    ) {

      console.error(
        "Failed to switch drawing mode:",
        error,
      );

    }

  }, [
    drawing,
  ]);


  /*
   * Automatically zoom when user selects
   * an existing field from sidebar or map.
   */
  useEffect(() => {

    if (
      !selectedFieldId
    ) {
      return;
    }


    const field =
      fields.find(
        (
          candidate,
        ) =>
          candidate.id ===
            selectedFieldId,
      );


    if (!field) {
      return;
    }


    zoomToField(
      field,
    );

  }, [
    selectedFieldId,
    fields,
  ]);


  /*
   * Highlight selected field.
   */
  useEffect(() => {

    const map =
      mapRef.current;


    if (
      !map ||
      !map.getLayer(
        "farm-fields-outline",
      )
    ) {
      return;
    }


    map.setPaintProperty(

      "farm-fields-outline",

      "line-width",

      [
        "case",

        [
          "==",

          [
            "get",
            "fieldId",
          ],

          selectedFieldId
            ?? "",
        ],

        5,

        2,
      ],

    );


    map.setPaintProperty(

      "farm-fields-fill",

      "fill-opacity",

      [
        "case",

        [
          "==",

          [
            "get",
            "fieldId",
          ],

          selectedFieldId
            ?? "",
        ],

        0.5,

        0.28,
      ],

    );

  }, [
    selectedFieldId,
    fields,
  ]);


  /*
   * Switch map/satellite style.
   *
   * setStyle() destroys custom sources/layers,
   * therefore we restore them after style.load.
   */
  useEffect(() => {

    const map =
      mapRef.current;


    if (!map) {
      return;
    }


    map.setStyle(
      MAP_STYLES[
        mapMode
      ],
    );


    map.once(
      "style.load",

      () => {

        installFieldLayers(
          map,
        );

        createDrawingSystem(
          map,
        );


        if (
          selectedFieldId
        ) {

          const field =
            fieldsRef
              .current
              .find(
                (
                  candidate,
                ) =>
                  candidate.id ===
                    selectedFieldId,
              );


          if (field) {

            zoomToField(
              field,
            );

          }

        }

      },
    );

  }, [
    mapMode,
  ]);


  return (
    <div
      className="farm-map"
    >

      <div
        ref={
          containerRef
        }

        className="map-canvas"
      />

    </div>
  );
}
