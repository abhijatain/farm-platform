import { apiRequest } from "./api-client";

import type {
  FieldWeather,
  Activity,
  CropCycle,
  CropGrowth,
  CropRadarScreening,
  FieldSpatialHistory,
  SeasonalZonesResponse,
  SeasonalZoneGrid,
  FieldObservationIntelligence,
  CropPhenologyIntelligence,
  CropStageObservation,
  CurrentUser,
  Farm,
  Field,
  PolygonGeometry,
  Season,
  TimelineItem,
  SatelliteObservation,
  SatelliteIngestionJob,
  SatelliteAnomalyFeatureCollection,
  SatelliteMetricType,
  ActivitySatelliteContext,
  FieldSatelliteTimeline,
  FieldSatelliteChange,
  SatelliteChangeMode,
  FieldSatelliteTrends,
} from "../types/api";

/* AUTH */

export function getMe() {
  return apiRequest<CurrentUser>("/auth/me");
}

/* FARMS */

export function listFarms() {
  return apiRequest<Farm[]>("/farms");
}

export function createFarm(data: {
  name: string;
  location_name: string | null;
}) {
  return apiRequest<Farm>("/farms", {
    method: "POST",

    body: JSON.stringify(data),
  });
}

/* FIELDS */

export function listFields(farmId: string) {
  return apiRequest<Field[]>(`/farms/${farmId}/fields`);
}

export function createField(
  farmId: string,

  data: {
    name: string;

    boundary: PolygonGeometry;
  },
) {
  return apiRequest<Field>(
    `/farms/${farmId}/fields`,

    {
      method: "POST",

      body: JSON.stringify(data),
    },
  );
}

/* SEASONS */

export function listSeasons(farmId: string) {
  return apiRequest<Season[]>(`/farms/${farmId}/seasons`);
}

export function createSeason(
  farmId: string,

  data: {
    name: string;

    season_type: string | null;

    started_on: string;

    ended_on: string | null;
  },
) {
  return apiRequest<Season>(
    `/farms/${farmId}/seasons`,

    {
      method: "POST",

      body: JSON.stringify(data),
    },
  );
}

/* CROP CYCLES */

export function listFieldCropCycles(fieldId: string) {
  return apiRequest<CropCycle[]>(`/fields/${fieldId}/crop-cycles`);
}
export function listSeasonCropCycles(seasonId: string) {
  return apiRequest<CropCycle[]>(`/seasons/${seasonId}/crop-cycles`);
}

export function createCropCycle(
  seasonId: string,

  data: {
    field_id: string;

    crop_name: string;

    variety: string | null;

    started_on: string;

    planted_on: string | null;

    expected_harvest_on: string | null;

    notes: string | null;
  },
) {
  return apiRequest<CropCycle>(
    `/seasons/${seasonId}/crop-cycles`,

    {
      method: "POST",

      body: JSON.stringify(data),
    },
  );
}

export function updateCropCyclePlan(
  cropCycleId: string,
  data: { planted_on?: string | null; expected_harvest_on?: string | null },
) {
  return apiRequest<CropCycle>(
    `/crop-cycles/${encodeURIComponent(cropCycleId)}/plan`,
    { method: "PATCH", body: JSON.stringify(data) },
  );
}

export type HarvestResult = {
  crop_cycle_id: string;

  status: string;

  harvested_on: string;

  yield_kg: number;

  harvested_area_acres: number;

  yield_kg_per_acre: number;

  moisture_percent: number | null;

  quality_grade: string | null;

  selling_price_per_kg: number | null;

  estimated_value: number | null;
};

export function harvestCropCycle(
  cropCycleId: string,

  data: {
    harvested_at: string;

    yield_kg: number;

    harvested_area_acres: number;

    moisture_percent: number | null;

    quality_grade: string | null;

    selling_price_per_kg: number | null;

    notes: string | null;
  },
) {
  return apiRequest<HarvestResult>(`/crop-cycles/${cropCycleId}/harvest`, {
    method: "POST",

    body: JSON.stringify(data),
  });
}

/* ACTIVITIES */

export function createActivity(
  fieldId: string,

  data: {
    crop_cycle_id: string | null;

    activity_type: string;

    occurred_at: string;

    notes: string | null;

    details: Record<string, unknown>;
  },
) {
  return apiRequest<Activity>(
    `/fields/${fieldId}/activities`,

    {
      method: "POST",

      body: JSON.stringify(data),
    },
  );
}

export function getActivitySatelliteContext(
  activityId: string,
  metricType: SatelliteMetricType = "ndvi",
  windowDays = 14,
  minimumValidPercent = 80,
) {
  const params = new URLSearchParams({
    metric_type: metricType,
    window_days: String(windowDays),
    minimum_valid_percent: String(minimumValidPercent),
  });

  return apiRequest<ActivitySatelliteContext>(
    `/activities/${activityId}/satellite-context?${params.toString()}`,
  );
}

/* TIMELINE */

export function getFieldTimeline(fieldId: string) {
  return apiRequest<TimelineItem[]>(`/fields/${fieldId}/timeline`);
}

export function listSatelliteObservations(fieldId: string) {
  return apiRequest<SatelliteObservation[]>(
    `/fields/${fieldId}/satellite-observations`,
  );
}

export function getSatelliteTimeline(
  fieldId: string,
  preferredMetricType: SatelliteMetricType = "ndvi",
  options?: {
    targetDate?: string | null;
    windowDays?: number;
    minimumValidPercent?: number;
    eventLimit?: number;
  },
) {
  const params = new URLSearchParams({
    preferred_metric_type:
      preferredMetricType,
    window_days: String(
      options?.windowDays
      ?? 14,
    ),
    minimum_valid_percent: String(
      options?.minimumValidPercent
      ?? 80,
    ),
    event_limit: String(
      options?.eventLimit
      ?? 60,
    ),
  });

  if (options?.targetDate) {
    params.set(
      "target_date",
      options.targetDate,
    );
  }

  return apiRequest<FieldSatelliteTimeline>(
    `/fields/${fieldId}/satellite-timeline?${params.toString()}`,
  );
}


export function getSatelliteTrends(
  fieldId: string,
  options?: {
    cropCycleId?: string | null;
    startDate?: string | null;
    endDate?: string | null;
  },
) {
  const params = new URLSearchParams();

  if (options?.cropCycleId) {
    params.set(
      "crop_cycle_id",
      options.cropCycleId,
    );
  }

  if (options?.startDate) {
    params.set(
      "start_date",
      options.startDate,
    );
  }

  if (options?.endDate) {
    params.set(
      "end_date",
      options.endDate,
    );
  }

  const query =
    params.toString();

  return apiRequest<FieldSatelliteTrends>(
    `/fields/${fieldId}/satellite-trends${query ? `?${query}` : ""}`,
  );
}


export function getSatelliteChange(
  fieldId: string,
  metricType: SatelliteMetricType,
  mode: SatelliteChangeMode,
  options?: {
    toDate?: string | null;
    fromDate?: string | null;
    cropCycleId?: string | null;
    minimumValidPercent?: number;
    dateToleranceDays?: number;
    pixelChangeThreshold?: number | null;
  },
) {
  const params = new URLSearchParams({
    metric_type: metricType,
    mode,
    minimum_valid_percent: String(
      options?.minimumValidPercent
      ?? 80,
    ),
    date_tolerance_days: String(
      options?.dateToleranceDays
      ?? 7,
    ),
  });

  if (options?.toDate) {
    params.set(
      "to_date",
      options.toDate,
    );
  }

  if (options?.fromDate) {
    params.set(
      "from_date",
      options.fromDate,
    );
  }

  if (options?.cropCycleId) {
    params.set(
      "crop_cycle_id",
      options.cropCycleId,
    );
  }

  if (
    options?.pixelChangeThreshold
    != null
  ) {
    params.set(
      "pixel_change_threshold",
      String(
        options.pixelChangeThreshold,
      ),
    );
  }

  return apiRequest<FieldSatelliteChange>(
    `/fields/${fieldId}/satellite-change?${params.toString()}`,
  );
}


export function getSatelliteIngestionStatus(fieldId: string) {
  return apiRequest<SatelliteIngestionJob | null>(
    `/fields/${fieldId}/satellite-ingestion`,
  );
}

export function listSatelliteAnomalies(
  observationId: string,
  metricType: SatelliteMetricType = "ndvi",
) {
  const params = new URLSearchParams({
    metric_type: metricType,
  });

  return apiRequest<SatelliteAnomalyFeatureCollection>(
    `/satellite-observations/${observationId}/anomalies?${params.toString()}`,
  );
}


/** Fetch weather using the field's server-side polygon centroid. */
export function getFieldWeather(
  fieldId: string,
  options?: {
    startDate?: string | null;
    endDate?: string | null;
    includeForecast?: boolean;
  },
) {
  const params = new URLSearchParams();
  if (options?.startDate) params.set("start_date", options.startDate);
  if (options?.endDate) params.set("end_date", options.endDate);
  params.set("include_forecast", String(options?.includeForecast ?? true));
  return apiRequest<FieldWeather>(
    "/fields/" + fieldId + "/weather?" + params.toString(),
  );
}

/* GROWTH STAGES */

export function getCropGrowthStages(cropCycleId: string) {
  return apiRequest<CropGrowth>(
    `/crop-cycles/${cropCycleId}/growth-stages`,
  );
}

export function recordCropGrowthStage(
  cropCycleId: string,
  data: { stage_code: string; observed_on: string; notes: string | null },
) {
  return apiRequest<CropStageObservation>(
    `/crop-cycles/${cropCycleId}/growth-stages`,
    { method: "PUT", body: JSON.stringify(data) },
  );
}

export function deleteCropGrowthStage(cropCycleId: string, stageCode: string) {
  return apiRequest<void>(
    `/crop-cycles/${cropCycleId}/growth-stages/${encodeURIComponent(stageCode)}`,
    { method: "DELETE" },
  );
}


/** Read-only screening of comparable radar passes in a crop cycle. */
export function getCropRadarScreening(cropCycleId: string) {
  return apiRequest<CropRadarScreening>(
    "/crop-cycles/" + encodeURIComponent(cropCycleId) + "/radar-screening",
  );
}

/* Conservative field spatial zones and stage-aware sensor intelligence. */
export function getFieldSpatialHistory(
  fieldId: string, metricType: "ndvi" | "ndmi" | "ndre" = "ndvi", years = 10,
) {
  const params = new URLSearchParams({ metric_type: metricType, years: String(years) });
  return apiRequest<FieldSpatialHistory>(
    `/fields/${encodeURIComponent(fieldId)}/spatial-history?${params}`,
  );
}

export function getFieldObservationIntelligence(fieldId: string, years = 2) {
  return apiRequest<FieldObservationIntelligence>(
    `/fields/${encodeURIComponent(fieldId)}/observation-intelligence?years=${years}`,
  );
}

export function getCropPhenologyIntelligence(cropCycleId: string) {
  return apiRequest<CropPhenologyIntelligence>(
    `/crop-cycles/${encodeURIComponent(cropCycleId)}/phenology-intelligence`,
  );
}

/* Historical season processing is strictly user-triggered. */
export type HistoryWindow = {start_month: number; end_month: number; all_crops?: boolean};
export type SavedHistoricalWindow = {
  calendar_key: string;
  years: number[];
  completed_years: number[];
  is_custom: boolean;
};
function historyWindowParams(window?: HistoryWindow) {
  return window ? { start_month: window.start_month, end_month: window.end_month } : {};
}
export function listSavedHistoricalWindows(fieldId: string, cropCycleId: string, allCrops = false) {
  return apiRequest<SavedHistoricalWindow[]>(
    `/fields/${encodeURIComponent(fieldId)}/seasonal-zone-windows?crop_cycle_id=${encodeURIComponent(cropCycleId)}&all_crops=${allCrops}`,
  );
}
export function getSeasonalZones(fieldId: string, cropCycleId: string, window?: HistoryWindow) {
  const params = new URLSearchParams({
    crop_cycle_id: cropCycleId,
    ...(window ? {
      start_month: String(window.start_month),
      end_month: String(window.end_month),
      all_crops: String(window.all_crops ?? false),
    } : {}),
  });
  return apiRequest<SeasonalZonesResponse>(
    `/fields/${encodeURIComponent(fieldId)}/seasonal-zones?${params}`,
  );
}
export function calculateSeasonalZones(fieldId: string, cropCycleId: string, years: number[], window?: HistoryWindow) {
  return apiRequest<{queued_years:number[];already_available_or_running:number[];worker_required:boolean}>(
    `/fields/${encodeURIComponent(fieldId)}/seasonal-zones/calculate`,
    { method: "POST", body: JSON.stringify({crop_cycle_id: cropCycleId,years,...historyWindowParams(window)}) },
  );
}
export function combineSeasonalZones(fieldId: string, cropCycleId: string, years: number[], window?: HistoryWindow) {
  return apiRequest<SeasonalZoneGrid>(
    `/fields/${encodeURIComponent(fieldId)}/seasonal-zones/combine`,
    { method: "POST", body: JSON.stringify({crop_cycle_id: cropCycleId,years,...historyWindowParams(window)}) },
  );
}
