import maplibregl, { type Map as MapLibreMap } from "maplibre-gl";
import type { Field, SatelliteAnomalyFeature } from "../../types/api";

type Coordinate = [number, number];

function isCoordinate(value: unknown): value is Coordinate {
  return (
    Array.isArray(value) &&
    value.length >= 2 &&
    typeof value[0] === "number" &&
    typeof value[1] === "number" &&
    Number.isFinite(value[0]) &&
    Number.isFinite(value[1])
  );
}

function extendBounds(
  bounds: maplibregl.LngLatBounds,
  coordinates: unknown,
) {
  if (isCoordinate(coordinates)) {
    bounds.extend([coordinates[0], coordinates[1]]);
    return;
  }

  if (!Array.isArray(coordinates)) {
    return;
  }

  for (const child of coordinates) {
    extendBounds(bounds, child);
  }
}

function boundsFromCoordinates(coordinates: unknown) {
  const bounds = new maplibregl.LngLatBounds();

  extendBounds(bounds, coordinates);

  return bounds.isEmpty() ? null : bounds;
}

export function zoomToFields(
  map: MapLibreMap,
  fields: Field[],
) {
  const bounds =
    new maplibregl.LngLatBounds();

  for (const field of fields) {
    extendBounds(
      bounds,
      field.boundary.coordinates,
    );
  }

  if (bounds.isEmpty()) {
    return;
  }

  map.fitBounds(
    bounds,
    {
      padding: {
        top: 86,
        bottom: 86,
        left: 86,
        right: 86,
      },
      maxZoom: 17,
      duration: 700,
    },
  );
}


export function zoomToField(map: MapLibreMap, field: Field) {
  /*
   * Backend field geometry can be Polygon or MultiPolygon.
   *
   * Do not assume coordinates[0] is always a ring. For a
   * MultiPolygon it is another polygon level, which was the
   * reason selected fields stayed centred on Chandigarh after
   * the map refactor.
   */
  const bounds = boundsFromCoordinates(field.boundary.coordinates);

  if (!bounds) {
    console.warn("Unable to calculate field bounds:", field.id);
    return;
  }

  map.fitBounds(bounds, {
    /*
     * Leave room for the satellite-analysis panel on the left
     * and the field-details panel on the right.
     */
    padding: {
      top: 100,
      bottom: 100,
      left: 340,
      right: 420,
    },
    maxZoom: 19,
    duration: 900,
  });
}

export function zoomToAnomaly(
  map: MapLibreMap,
  feature: SatelliteAnomalyFeature,
) {
  const bounds = boundsFromCoordinates(feature.geometry.coordinates);

  if (!bounds) {
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
