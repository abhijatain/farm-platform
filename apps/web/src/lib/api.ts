import { apiRequest } from "./api-client";

import type {
  Activity,
  CropCycle,
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
