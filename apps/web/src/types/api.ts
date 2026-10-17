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

export type SatelliteMetricType =
  | "ndvi"
  | "ndre"
  | "ndmi"
  | "gndvi"
  | "evi2"
  | "ndwi"
  | "savi"
  | "msavi"
  | "bsi"
  | "ndti"
  | "ccci"
  | "reci"
  | "mcari"
  | "sar_vv_db"
  | "sar_vh_db"
  | "sar_vv_vh_ratio"
  | "sar_rvi"
  | "lst_c";

export type SatelliteMetric = {
  id: string;
  satellite_observation_id: string;

  metric_type: SatelliteMetricType;

  has_raster: boolean;

  mean: number | null;
  median: number | null;

  min: number | null;
  max: number | null;

  std: number | null;

  native_resolution_m: number | null;
  output_resolution_m: number | null;

  pixel_count: number | null;
  valid_pixel_count: number | null;
  valid_pixel_percent: number | null;

  metadata_json: Record<string, unknown>;
};

export type SatelliteObservation = {
  id: string;

  field_id: string;

  observed_on: string;

  source: string;
  scene_id: string;

  cloud_cover_percent: number | null;

  metadata_json: Record<string, unknown>;

  metrics: SatelliteMetric[];

  created_at: string;
  updated_at: string;
};

export type SatelliteSourceKind =
  | "optical"
  | "radar"
  | "thermal"
  | "other";

export type SatelliteTimelineStatus =
  | "usable"
  | "cloud_skipped"
  | "unusable"
  | "skipped"
  | "unavailable";

export type SatelliteTimelineMetricSummary = {
  metric_type: SatelliteMetricType;

  mean: number | null;
  median: number | null;

  valid_pixel_percent: number | null;

  has_raster: boolean;
};

export type SatelliteTimelineEvent = {
  observation_id: string;

  observed_on: string;

  source: string;
  source_kind: SatelliteSourceKind;

  scene_id: string;

  status: SatelliteTimelineStatus;
  processing_status: string | null;

  cloud_cover_percent: number | null;
  field_cloud_cover_percent: number | null;

  cloud_independent: boolean;

  metric_types: SatelliteMetricType[];

  representative_metric:
    SatelliteTimelineMetricSummary | null;
};

export type SatelliteTimelineSelectionMatch = {
  observation_id: string;

  observed_on: string;
  days_from_target: number;

  source: string;
  source_kind: SatelliteSourceKind;

  metric_type: SatelliteMetricType;

  median: number | null;
  mean: number | null;

  valid_pixel_percent: number | null;

  has_raster: boolean;
};

export type SatelliteTimelineSelection = {
  target_date: string;

  preferred_metric_type: SatelliteMetricType;
  minimum_valid_percent: number;
  search_window_days: number;

  optical_unavailable_on_target: boolean;

  preferred_metric:
    SatelliteTimelineSelectionMatch | null;

  radar_fallback:
    SatelliteTimelineSelectionMatch | null;

  recommended_kind:
    | "preferred_metric"
    | "radar_fallback"
    | "none";

  recommended:
    SatelliteTimelineSelectionMatch | null;

  recommendation_reason: string | null;
};

export type FieldSatelliteTimeline = {
  field_id: string;

  events: SatelliteTimelineEvent[];

  selection: SatelliteTimelineSelection;
};

export type SatelliteChangeMode =
  | "previous"
  | "crop_start"
  | "days_7"
  | "days_14"
  | "days_30"
  | "custom";

export type SatelliteChangeObservation = {
  observation_id: string;

  observed_on: string;

  source: string;
  scene_id: string;

  orbit_state: string | null;
  relative_orbit: number | null;
  platform: string | null;

  metric_type: SatelliteMetricType;

  valid_pixel_percent: number | null;

  mean: number | null;
  median: number | null;

  minimum: number | null;
  maximum: number | null;
  std: number | null;

  has_raster: boolean;

  native_resolution_m: number | null;
  output_resolution_m: number | null;
};

export type SatelliteChangeScalarSummary = {
  days_between: number | null;

  mean_change: number | null;
  mean_percent_change: number | null;

  median_change: number | null;
  median_percent_change: number | null;
};

export type SatelliteChangeAnomalySummary = {
  persistence_basis: string;

  before_anomaly_area_sqm: number | null;
  before_anomaly_area_acres: number | null;

  after_anomaly_area_sqm: number | null;
  after_anomaly_area_acres: number | null;

  persistent_area_sqm: number | null;
  persistent_area_acres: number | null;

  resolved_area_sqm: number | null;
  resolved_area_acres: number | null;

  new_area_sqm: number | null;
  new_area_acres: number | null;

  persistent_geometry: SatelliteAnomalyGeometry | null;
  resolved_geometry: SatelliteAnomalyGeometry | null;
  new_geometry: SatelliteAnomalyGeometry | null;
};

export type FieldSatelliteChange = {
  field_id: string;

  metric_type: SatelliteMetricType;
  mode: SatelliteChangeMode;
  status:
    | "complete"
    | "missing_current"
    | "missing_baseline";

  requested_to_date: string | null;
  requested_from_date: string | null;

  baseline_target_date: string | null;

  crop_cycle_id: string | null;
  crop_reference_date: string | null;

  minimum_valid_percent: number;
  date_tolerance_days: number;

  pixel_change_threshold: number;
  pixel_change_display_max: number;

  before: SatelliteChangeObservation | null;
  after: SatelliteChangeObservation | null;

  scalar: SatelliteChangeScalarSummary;
  anomalies: SatelliteChangeAnomalySummary;
};

export type SatellitePixelChangeSummary = {
  threshold: number;

  valid_pixel_count: number;

  mean_change: number;
  median_change: number;

  minimum_change: number;
  maximum_change: number;

  valid_area_sqm: number;
  valid_area_acres: number;

  increased_pixel_count: number;
  increased_percent: number;
  increased_area_sqm: number;
  increased_area_acres: number;

  decreased_pixel_count: number;
  decreased_percent: number;
  decreased_area_sqm: number;
  decreased_area_acres: number;

  stable_pixel_count: number;
  stable_percent: number;
  stable_area_sqm: number;
  stable_area_acres: number;
};

export type SatelliteTrendPoint = {
  observation_id: string;
  observed_on: string;

  source: string;
  metric_type: SatelliteMetricType;

  mean: number | null;
  median: number | null;
  valid_pixel_percent: number | null;

  orbit_state: string | null;
  relative_orbit: number | null;
  platform: string | null;
  radar_orbit_key: string | null;

  anomaly_zone_count: number;
  anomaly_area_acres: number;
};

export type SatelliteTrendActivity = {
  id: string;
  occurred_at: string;

  activity_type: string;
  notes: string | null;

  crop_cycle_id: string | null;
};

export type FieldSatelliteTrends = {
  field_id: string;
  crop_cycle_id: string | null;

  start_date: string;
  end_date: string;

  metric_types: SatelliteMetricType[];

  points: SatelliteTrendPoint[];
  activities: SatelliteTrendActivity[];
};

export type SatelliteIngestionJobStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed";

export type SatelliteIngestionJob = {
  id: string;
  field_id: string;

  job_type: "initial_backfill" | "incremental";

  start_date: string;
  end_date: string;

  status: SatelliteIngestionJobStatus;

  attempts: number;
  max_attempts: number;

  available_at: string;

  started_at: string | null;
  completed_at: string | null;

  last_error: string | null;

  created_at: string;
  updated_at: string;
};

export type SatelliteAnomalySeverity =
  | "low"
  | "moderate"
  | "high";

export type SatelliteAnomalyType =
  | "below_field_baseline"
  | "above_field_baseline";

export interface SatelliteAnomalyProperties {
  id: string;

  satellite_observation_id: string;
  field_id: string;

  zone_index: number;

  index_type: SatelliteMetricType;
  anomaly_type: SatelliteAnomalyType;

  severity: SatelliteAnomalySeverity;

  pixel_count: number;

  area_sqm: number;
  area_acres: number;

  zone_mean_value: number;
  zone_min_value: number;
  zone_max_value: number | null;

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

export type ActivitySatelliteComparisonStatus =
  | "complete"
  | "missing_before"
  | "missing_after"
  | "missing_both";

export type ActivitySatelliteObservationMatch = {
  observation_id: string;

  observed_on: string;
  days_from_activity: number;

  source: string;
  scene_id: string;

  metric_type: SatelliteMetricType;

  valid_pixel_percent: number;

  mean: number | null;
  median: number | null;
  minimum: number | null;
  maximum: number | null;
  std: number | null;

  has_raster: boolean;

  native_resolution_m: number | null;
  output_resolution_m: number | null;

  anomaly_zone_count: number;
  anomaly_area_sqm: number;
  anomaly_area_acres: number;
};

export type ActivitySatelliteComparison = {
  status: ActivitySatelliteComparisonStatus;

  mean_change: number | null;
  mean_percent_change: number | null;

  median_change: number | null;
  median_percent_change: number | null;

  anomaly_zone_count_change: number | null;

  anomaly_area_sqm_change: number | null;
  anomaly_area_acres_change: number | null;

  percent_change_minimum_baseline_abs: number;
};

export type ActivitySatelliteSpatialComparison = {
  status: ActivitySatelliteComparisonStatus;

  persistence_basis: string;

  before_anomaly_area_sqm: number | null;
  before_anomaly_area_acres: number | null;

  after_anomaly_area_sqm: number | null;
  after_anomaly_area_acres: number | null;

  persistent_area_sqm: number | null;
  persistent_area_acres: number | null;

  resolved_area_sqm: number | null;
  resolved_area_acres: number | null;

  new_area_sqm: number | null;
  new_area_acres: number | null;

  persistent_geometry: SatelliteAnomalyGeometry | null;
  resolved_geometry: SatelliteAnomalyGeometry | null;
  new_geometry: SatelliteAnomalyGeometry | null;
};

export type ActivitySatelliteContext = {
  activity_id: string;
  field_id: string;

  activity_type: string;
  occurred_at: string;

  metric_type: SatelliteMetricType;

  search_window_days: number;
  minimum_valid_percent: number;

  before: ActivitySatelliteObservationMatch | null;
  after: ActivitySatelliteObservationMatch | null;

  comparison: ActivitySatelliteComparison;
  spatial_comparison: ActivitySatelliteSpatialComparison;
};


/* Modeled weather is field-level context, not a satellite observation. */
export type FieldWeatherDay = {
  date: string;
  source: "historical" | "historical_forecast" | "recent_model" | "forecast";
  precipitation_mm: number | null;
  temperature_max_c: number | null;
  temperature_min_c: number | null;
  relative_humidity_mean_percent: number | null;
  wind_speed_max_kmh: number | null;
  reference_et0_mm: number | null;
  weather_code: number | null;
};

export type FieldWeather = {
  field_id: string;
  provider: string;
  latitude: number;
  longitude: number;
  timezone: string;
  start_date: string;
  end_date: string;
  forecast_end_date: string | null;
  days: FieldWeatherDay[];
  warnings: string[];
};

/** Provisional day milestones must not be mistaken for confirmed growth. */
export type CropStageDefinition = {
  code: string;
  label: string;
  approx_days_after_planting: number | null;
  bbch_reference: string | null;
};

export type CropStageObservation = {
  id: string;
  crop_cycle_id: string;
  stage_code: string;
  observed_on: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type CropGrowth = {
  crop_cycle_id: string;
  crop_name: string;
  profile_key: string;
  profile_version: string;
  planting_date: string | null;
  as_of: string;
  days_after_planting: number | null;
  stages: CropStageDefinition[];
  observations: CropStageObservation[];
  latest_recorded_stage: string | null;
  provisional_stage: string | null;
  degree_day_base_c: number | null;
  accumulated_gdd_c_days: number | null;
  gdd_days_available: number;
  gdd_days_expected: number;
  warnings: string[];
};


/* Exploratory field-median screening; never a diagnosis or persistent alert. */
export type RadarScreenMetric = {
  metric_type: "sar_vh_db" | "sar_vv_db" | "sar_rvi";
  unit: string;
  status: "unusual_variation" | "within_reference_range" | "insufficient_baseline" | "unverified_stage" | "unsupported_crop";
  latest_value: number;
  reference_median: number | null;
  difference: number | null;
  screening_threshold: number | null;
  baseline_passes: number;
  required_baseline_passes: number;
};
export type RadarOrbitScreen = {
  radar_orbit_key: string;
  orbit_state: string;
  relative_orbit: number;
  platform: string | null;
  observed_on: string;
  stage_code: string | null;
  stage_label: string | null;
  stage_source: "farmer_confirmed" | "provisional" | "unknown";
  status: "review_variation" | "within_reference_range" | "insufficient_evidence";
  metrics: RadarScreenMetric[];
  weather: {
    precipitation_3_day_mm: number | null;
    days_available: number;
    days_required: number;
    wet_weather_context: boolean | null;
  };
  optical: {
    metric_type: "ndvi" | "ndmi";
    observed_on: string;
    value: number;
    days_from_radar: number;
  }[];
  nearby_activities: string[];
  explanations: string[];
};
export type CropRadarScreening = {
  crop_cycle_id: string;
  field_id: string;
  crop_name: string;
  profile_key: string;
  as_of: string;
  analysis_version: string;
  minimum_valid_coverage_percent: number;
  minimum_prior_same_stage_passes: number;
  orbits: RadarOrbitScreen[];
  warnings: string[];
  statement: string;
};


/** Historical field-relative anomaly frequencies; NOT measured yield/productivity. */
export type RelativeZone = {
  id: string;
  classification: string;
  stability: string;
  stability_score: number;
  centroid: number[];
  visit_point: number[];
  area_acres: number;
  geometry: { type: "Polygon" | "MultiPolygon"; coordinates: number[][][] | number[][][][] };
  interpretation: string;
};
export type TrackedZone = {
  id: string;
  anomaly_type: string;
  transition: "new" | "persistent" | "recurring" | "resolved";
  recent_dates: string[];
  area_acres: number;
  geometry: RelativeZone["geometry"];
};
export type FieldSpatialHistory = {
  field_id: string;
  metric_type: "ndvi" | "ndmi" | "ndre";
  history_years: number;
  status: "insufficient_history" | "short_history" | "candidate_zones";
  observation_count: number;
  year_count: number;
  years: number[];
  date_range: string[] | null;
  minimum_valid_percent: number;
  cell_size_m: number | null;
  zone_model: string;
  recent_dates: string[];
  zones: RelativeZone[];
  tracking: TrackedZone[];
  warnings: string[];
};

export type SensorComparison = {
  status: "complete" | "one_usable_date";
  kind: "radar" | "optical";
  metric_type: string;
  source: string;
  unit: string;
  orbit_key: string | null;
  latest_date: string;
  latest_value: number;
  latest_valid_percent: number;
  previous_date: string | null;
  previous_value: number | null;
  days_between: number | null;
  change: number | null;
  interpretation: string;
};
export type FieldObservationIntelligence = {
  field_id: string;
  window_years: number;
  comparisons: SensorComparison[];
  suppressed_unidentified_radar_metrics: number;
  notes: string[];
};
export type CropPhenologyIntelligence = {
  crop_cycle_id: string;
  field_id: string;
  crop_name: string;
  variety: string | null;
  profile_key: string;
  profile_version: string;
  stage_code: string | null;
  stage_source: "farmer_confirmed" | "provisional_calendar" | "unknown";
  as_of: string;
  days_after_planting: number | null;
  recommended_indices: string[];
  guidance: string;
  historical_comparisons: {
    crop_cycle_id: string;
    crop: string;
    variety: string | null;
    observed_on: string;
    days_after_planting: number;
    ndvi_median: number | null;
    valid_percent: number;
    alignment: string;
  }[];
  warnings: string[];
};
/** Derived on read from compact NDVI cells; not measured yield. */
export type SeasonalZoneAnalysis = {
  status: "zones_available" | "low_spatial_contrast" | "insufficient_data";
  display: { min: number; max: number; mean: number; mode: string } | null;
  zones: {
    method: string;
    status: "qualified" | "low_spatial_contrast";
    mapped_area_acres: number;
    low_area_acres: number;
    medium_area_acres: number;
    high_area_acres: number;
    low_percent: number;
    medium_percent: number;
    high_percent: number;
    p10_p90_spread: number;
    threshold_low: number | null;
    threshold_high: number | null;
  } | null;
  zone_classes: Array<"low" | "medium" | "high" | null>;
  notes: string[];
};

/* Compact seasonal NDVI means; source images are never returned. */
export type SeasonalZoneGrid = {
  width: number;
  height: number;
  mask: boolean[];
  pixels: Array<number | null>;
  mean_ndvi: number | null;
  spatial_analysis?: SeasonalZoneAnalysis;
  relative_pixels?: Array<number | null>;
  relative_analysis?: SeasonalZoneAnalysis;
  stable_relative_area_percent?: number | null;
  stability_basis?: string;
  weak_area_acres?: number;
  strong_area_acres?: number;
  mapped_area_acres?: number;
  scene_count?: number;
  scene_dates?: string[];
  selected_years?: number[];
  zone_threshold_ndvi?: number;
  years_contributing?: number[];
  notes?: string;
};
export type SeasonalZoneRow = {
  id: string;
  year: number;
  status: "pending" | "running" | "completed" | "failed" | "stale_boundary";
  start_date: string;
  end_date: string;
  season_label: string;
  crop_key: string;
  window_source: "reference_calendar" | "recorded_crop_cycle" | "user_selected_months";
  error: string | null;
  result: SeasonalZoneGrid | null;
};
export type SeasonalZonesResponse = {
  field_id: string;
  crop_cycle_id: string;
  crop: string;
  calendar_key: string;
  reference_window: { start: string; length_days: number; basis: string };
  available_years: number[];
  seasons: SeasonalZoneRow[];
};
