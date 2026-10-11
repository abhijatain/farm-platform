export type CurrentUser = {
  id: string;
  phone_e164: string;
  name: string | null;
  preferred_language: string;

  created_at: string;
  updated_at: string;
};

export type Farm = {
  id: string;

  name: string;
  location_name: string | null;

  created_at: string;
  updated_at: string;
};

export type PolygonGeometry = {
  type: "Polygon";
  coordinates: number[][][];
};

export type Field = {
  id: string;
  farm_id: string;

  name: string;

  boundary: PolygonGeometry;

  area_square_metres: number;
  area_hectares: number;
  area_acres: number;

  created_at: string;
  updated_at: string;
};

export type Season = {
  id: string;
  farm_id: string;

  name: string;
  season_type: string | null;
  status: string;

  started_on: string;
  ended_on: string | null;

  created_at: string;
  updated_at: string;
};

export type CropCycle = {
  id: string;

  season_id: string;
  field_id: string;

  crop_name: string;
  variety: string | null;

  status: string;

  started_on: string;
  planted_on: string | null;

  expected_harvest_on: string | null;

  harvested_on: string | null;

  yield_kg: number | null;

  harvested_area_acres: number | null;

  moisture_percent: number | null;

  quality_grade: string | null;

  selling_price_per_kg: number | null;

  harvest_notes: string | null;

  notes: string | null;

  created_at: string;
  updated_at: string;
};

export type Activity = {
  id: string;

  field_id: string;
  crop_cycle_id: string | null;

  activity_type: string;
  occurred_at: string;

  notes: string | null;

  details: Record<string, unknown>;

  created_at: string;
  updated_at: string;
};

export type TimelineItem = {
  type: "activity";

  id: string;

  occurred_at: string;

  activity_type: string;

  notes: string | null;

  details: Record<string, unknown>;

  crop_cycle_id: string | null;

  crop_name: string | null;
  variety: string | null;

  season_id: string | null;
  season_name: string | null;
};

export type SatelliteObservation = {
  id: string;

  field_id: string;

  observed_on: string;

  source: string;

  scene_id: string;

  cloud_cover_percent: number | null;

  valid_pixel_percent: number | null;

  ndvi_mean: number | null;

  ndvi_min: number | null;

  ndvi_max: number | null;

  ndvi_std: number | null;

  ndwi_mean: number | null;

  ndvi_median: number | null;

  ndvi_raster_uri: string | null;

  resolution_m: number | null;

  pixel_count: number | null;

  valid_pixel_count: number | null;

  metadata_json: Record<string, unknown>;

  created_at: string;
  updated_at: string;
};

export type SatelliteAnomalySeverity = "low" | "moderate" | "high";

export interface SatelliteAnomalyProperties {
  id: string;

  satellite_observation_id: string;
  field_id: string;

  zone_index: number;

  index_type: string;
  anomaly_type: string;

  severity: SatelliteAnomalySeverity;

  pixel_count: number;

  area_sqm: number;
  area_acres: number;

  zone_mean_value: number;
  zone_min_value: number;

  field_mean_value: number;
  field_median_value: number;

  threshold_value: number;

  difference_from_field: number;
  percent_difference: number | null;

  detection_method: string;
}

export interface SatelliteAnomalyGeometry {
  type: "MultiPolygon";

  coordinates: number[][][][];
}

export interface SatelliteAnomalyFeature {
  type: "Feature";

  id: string;

  geometry: SatelliteAnomalyGeometry;

  properties: SatelliteAnomalyProperties;
}

export interface SatelliteAnomalyFeatureCollection {
  type: "FeatureCollection";

  features: SatelliteAnomalyFeature[];
}
