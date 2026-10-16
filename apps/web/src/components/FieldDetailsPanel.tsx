import { useEffect, useMemo, useState } from "react";

import { Plus, X } from "lucide-react";

import ActivityMediaSection from "./ActivityMediaSection";
import FieldReport from "./FieldReport";
import FieldRasterImage from "./FieldRasterImage";
import FieldIntelligencePanel from "./FieldIntelligencePanel";
import HistoricalZonesPanel from "./HistoricalZonesPanel";
import SatelliteChangePanel from "./SatelliteChangePanel";
import SatelliteTrendCharts from "./SatelliteTrendCharts";
import {
  createActivity,
  createCropCycle,
  getActivitySatelliteContext,
  getFieldTimeline,
  getSatelliteIngestionStatus,
  getSatelliteTimeline,
  harvestCropCycle,
  listSatelliteObservations,
} from "../lib/api";

import { METRIC_CONFIG, getMetricConfig } from "./farm-map/satellite";

import type {
  ActivitySatelliteContext,
  ActivitySatelliteObservationMatch,
  CropCycle,
  Farm,
  Field,
  FieldSatelliteTimeline,
  SatelliteIngestionJob,
  SatelliteMetric,
  SatelliteMetricType,
  SatelliteObservation,
  Season,
  TimelineItem,
} from "../types/api";

import {
  localDateInputValue,
} from "../lib/dates";

import "./FieldWorkspace.css";

type Props = {
  farm: Farm;
  field: Field;
  season: Season | null;
  cropCycle: CropCycle | null;
  onClose: () => void;
  onDataChanged: () => Promise<void>;
};

type FieldWorkspaceTab = "satellite" | "activities" | "yield" | "report" | "historical";

type FarmerMetric = {
  metricType: SatelliteMetricType;
  label: string;
  subtitle: string;
};

const FARMER_METRICS: FarmerMetric[] = [
  {
    metricType: "ndvi",
    label: "Greenery",
    subtitle: "NDVI · crop greenness and canopy condition",
  },
  {
    metricType: "ndmi",
    label: "Moisture",
    subtitle: "NDMI · canopy moisture-sensitive satellite signal",
  },
  {
    metricType: "ndre",
    label: "Chlorophyll",
    subtitle: "NDRE · red-edge chlorophyll-sensitive crop signal",
  },
  {
    metricType: "bsi",
    label: "Soil exposure",
    subtitle: "BSI · exposed soil and surface signal",
  },
  {
    metricType: "sar_rvi",
    label: "All-weather radar",
    subtitle:
      "Sentinel-1 RVI · cloud-independent radar signal; lower/higher is not automatically bad/good",
  },
  {
    metricType: "lst_c",
    label: "Surface temperature",
    subtitle: "Landsat LST · thermal crop-surface temperature in °C",
  },
];

function currentDateTime() {
  const now = new Date();

  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);

  return local.toISOString().slice(0, 16);
}

function formatDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatActivityDate(value: string) {
  return new Date(value).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatActivityName(value: string) {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatMetricValue(value: number | null | undefined, digits = 3) {
  return value == null || !Number.isFinite(value) ? "—" : value.toFixed(digits);
}

function formatObservationSource(value: string) {
  switch (value) {
    case "sentinel-1-rtc":
      return "Sentinel-1 radar";

    case "landsat-c2-l2":
      return "Landsat thermal";

    case "sentinel-2":
    default:
      return "Sentinel-2 optical";
  }
}

function formatRadarGeometry(
  observation: SatelliteObservation,
) {
  if (
    observation.source
    !== "sentinel-1-rtc"
  ) {
    return null;
  }

  const metadata =
    observation.metadata_json
    ?? {};

  const orbitState =
    typeof metadata.orbit_state
      === "string"
      ? metadata.orbit_state
      : null;

  const relativeOrbit =
    typeof metadata.relative_orbit
      === "number"
      || typeof metadata.relative_orbit
        === "string"
      ? String(
          metadata.relative_orbit,
        )
      : null;

  const platform =
    typeof metadata.platform
      === "string"
      ? metadata.platform
      : null;

  const parts = [];

  if (orbitState) {
    parts.push(
      orbitState.charAt(
        0,
      ).toUpperCase()
      + orbitState
        .slice(
          1,
        )
        .toLowerCase(),
    );
  }

  if (relativeOrbit) {
    parts.push(
      `orbit ${relativeOrbit}`,
    );
  }

  if (platform) {
    parts.push(
      platform,
    );
  }

  return (
    parts.join(
      " · ",
    )
    || null
  );
}

function formatSignedMetricValue(value: number | null | undefined, digits = 3) {
  if (value == null || !Number.isFinite(value)) {
    return "—";
  }

  const prefix = value > 0 ? "+" : "";

  return `${prefix}${value.toFixed(digits)}`;
}

function getObservationMetric(
  observation: SatelliteObservation,
  metricType: SatelliteMetricType,
) {
  return (
    observation.metrics.find((metric) => metric.metric_type === metricType) ??
    null
  );
}

function preferredMetricForActivity(activityType: string): SatelliteMetricType {
  switch (activityType.trim().toLowerCase()) {
    case "irrigation":
      return "ndmi";

    case "fertilizer":
      return "ndre";

    case "tillage":
      return "bsi";

    case "sowing":
    case "transplanting":
    case "weeding":
      return "ndvi";

    case "fungicide":
    case "pesticide":
    case "herbicide":
      return "ndvi";

    default:
      return "ndvi";
  }
}

function getActivityDetailSummary(item: TimelineItem) {
  const details = item.details ?? {};

  if (item.activity_type === "irrigation") {
    const source = typeof details.source === "string" ? details.source : null;

    const duration =
      typeof details.duration_minutes === "number"
        ? details.duration_minutes
        : null;

    return [source, duration != null ? `${duration} min` : null]
      .filter(Boolean)
      .join(" · ");
  }

  const product = typeof details.product === "string" ? details.product : null;

  const quantity =
    typeof details.quantity === "number" ? details.quantity : null;

  const unit = typeof details.unit === "string" ? details.unit : null;

  return [
    product,
    quantity != null ? `${quantity}${unit ? ` ${unit}` : ""}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

export default function FieldDetailsPanel({
  farm,
  field,
  season,
  cropCycle,
  onClose,
  onDataChanged,
}: Props) {
  const [activeTab, setActiveTab] = useState<FieldWorkspaceTab>("satellite");

  const [timeline, setTimeline] = useState<TimelineItem[]>([]);

  const [loading, setLoading] = useState(true);

  const [timelineError, setTimelineError] =
    useState<string | null>(null);

  const [cropForm, setCropForm] = useState(false);

  const [activityForm, setActivityForm] = useState(false);

  const [harvestForm, setHarvestForm] = useState(false);

  const [satelliteObservations, setSatelliteObservations] = useState<
    SatelliteObservation[]
  >([]);

  const [satelliteLoading, setSatelliteLoading] = useState(true);

  const [satelliteError, setSatelliteError] =
    useState<string | null>(null);

  const [satelliteIngestion, setSatelliteIngestion] =
    useState<SatelliteIngestionJob | null>(null);

  const [satelliteTimeline, setSatelliteTimeline] =
    useState<FieldSatelliteTimeline | null>(null);

  const [selectedActivityId, setSelectedActivityId] = useState<string | null>(
    null,
  );

  const [activityMetricType, setActivityMetricType] =
    useState<SatelliteMetricType>("ndvi");

  const [activityContext, setActivityContext] =
    useState<ActivitySatelliteContext | null>(null);

  const [activityContextLoading, setActivityContextLoading] = useState(false);

  const [activityContextError, setActivityContextError] = useState<
    string | null
  >(null);

  async function loadSatelliteObservations(
    silent = false,
  ) {
    try {
      if (!silent) {
        setSatelliteLoading(true);
      }

      setSatelliteError(null);

      const [
        observations,
        ingestion,
      ] = await Promise.all([
        listSatelliteObservations(
          field.id,
        ),
        getSatelliteIngestionStatus(
          field.id,
        ),
      ]);

      setSatelliteObservations(
        observations,
      );

      setSatelliteIngestion(
        ingestion,
      );

      try {
        const unifiedTimeline =
          await getSatelliteTimeline(
            field.id,
            "ndvi",
            {
              windowDays: 14,
              minimumValidPercent: 80,
              eventLimit: 60,
            },
          );

        setSatelliteTimeline(
          unifiedTimeline,
        );

      } catch (
        timelineRequestError
      ) {
        setSatelliteTimeline(
          null,
        );

        console.error(
          "Unable to load unified satellite timeline:",
          timelineRequestError,
        );
      }

    } catch (requestError) {
      if (!silent) {
        setSatelliteObservations([]);
      }

      setSatelliteError(
        requestError instanceof Error
          ? requestError.message
          : "Unable to load satellite observations.",
      );

    } finally {
      if (!silent) {
        setSatelliteLoading(false);
      }
    }
  }

  async function loadTimeline() {
    try {
      setLoading(true);
      setTimelineError(null);

      const result = await getFieldTimeline(field.id);

      setTimeline(result);
    } catch (requestError) {
      setTimeline([]);

      setTimelineError(
        requestError instanceof Error
          ? requestError.message
          : "Unable to load field activities.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setActiveTab("satellite");
    setSelectedActivityId(null);
    setSatelliteIngestion(null);
    setSatelliteTimeline(null);

    void loadTimeline();
    void loadSatelliteObservations();
  }, [field.id]);

  useEffect(() => {
    if (
      !satelliteIngestion
      || ![
        "pending",
        "running",
      ].includes(
        satelliteIngestion.status,
      )
    ) {
      return;
    }

    const interval = window.setInterval(
      () => {
        void loadSatelliteObservations(
          true,
        );
      },
      15_000,
    );

    return () => {
      window.clearInterval(
        interval,
      );
    };
  }, [
    field.id,
    satelliteIngestion?.status,
  ]);

  const visibleTimeline = useMemo(() => {
    if (!season) {
      return [];
    }

    return timeline
      .filter((item) => item.season_id === season.id)
      .sort(
        (a, b) =>
          new Date(b.occurred_at).getTime() - new Date(a.occurred_at).getTime(),
      );
  }, [timeline, season]);

  useEffect(() => {
    if (visibleTimeline.length === 0) {
      setSelectedActivityId(null);

      return;
    }

    setSelectedActivityId((current) =>
      current && visibleTimeline.some((item) => item.id === current)
        ? current
        : visibleTimeline[0].id,
    );
  }, [visibleTimeline]);

  const selectedActivity = useMemo(
    () =>
      visibleTimeline.find((item) => item.id === selectedActivityId) ?? null,
    [visibleTimeline, selectedActivityId],
  );

  useEffect(() => {
    if (!selectedActivity) {
      return;
    }

    setActivityMetricType(
      preferredMetricForActivity(selectedActivity.activity_type),
    );
  }, [selectedActivity?.id]);

  useEffect(() => {
    if (!selectedActivity || activeTab !== "activities") {
      setActivityContext(null);
      setActivityContextError(null);

      return;
    }

    let cancelled = false;

    setActivityContextLoading(true);
    setActivityContextError(null);

    void getActivitySatelliteContext(
      selectedActivity.id,
      activityMetricType,
      14,
      80,
    )
      .then((result) => {
        if (!cancelled) {
          setActivityContext(result);
        }
      })
      .catch((requestError: unknown) => {
        if (cancelled) {
          return;
        }

        setActivityContext(null);

        setActivityContextError(
          requestError instanceof Error
            ? requestError.message
            : "Unable to load satellite response.",
        );
      })
      .finally(() => {
        if (!cancelled) {
          setActivityContextLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedActivity?.id, activityMetricType, activeTab]);

  async function refreshAll() {
    await onDataChanged();

    await Promise.all([loadTimeline(), loadSatelliteObservations()]);
  }

  const yieldPerAcre =
    cropCycle?.yield_kg != null &&
    cropCycle.harvested_area_acres != null &&
    cropCycle.harvested_area_acres > 0
      ? cropCycle.yield_kg / cropCycle.harvested_area_acres
      : null;

  const estimatedValue =
    cropCycle?.yield_kg != null && cropCycle.selling_price_per_kg != null
      ? cropCycle.yield_kg * cropCycle.selling_price_per_kg
      : null;

  return (
    <section className="field-workspace-panel">
      <header className="field-workspace-header">
        <div>
          <h1>{field.name}</h1>

          <p>
            {field.area_hectares.toFixed(2)}
            {" ha · "}
            {field.area_acres.toFixed(2)}
            {" acres"}

            {cropCycle
              ? ` · ${cropCycle.crop_name}${
                  cropCycle.variety ? ` · ${cropCycle.variety}` : ""
                }`
              : ""}
          </p>
        </div>

        <div className="field-workspace-header-actions">
          {season && !cropCycle && (
            <button
              className="secondary-action"
              onClick={() => setCropForm(true)}
            >
              <Plus size={16} />
              Start crop
            </button>
          )}

          <button
            className="field-workspace-close"
            onClick={onClose}
            aria-label="Close field"
          >
            <X size={22} />
          </button>
        </div>
      </header>

      <nav className="field-workspace-tabs">
        {[
          ["satellite", "Satellite"],
          ["historical", "Historical Zones"],
          ["activities", "Activities"],
          ["yield", "Yield"],
          ["report", "Report"],
        ].map(([value, label]) => (
          <button
            key={value}
            className={
              activeTab === value
                ? "field-workspace-tab active"
                : "field-workspace-tab"
            }
            onClick={() => setActiveTab(value as FieldWorkspaceTab)}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="field-workspace-content">
        {activeTab === "satellite" && (
          <SatelliteTab
            field={field}
            observations={satelliteObservations}
            loading={satelliteLoading}
            error={satelliteError}
            ingestion={satelliteIngestion}
            timeline={satelliteTimeline}
            cropCycle={cropCycle}
          />
        )}

        {activeTab === "historical" && <HistoricalZonesPanel field={field} cropCycle={cropCycle} />}

        {activeTab === "activities" && (
          <ActivitiesTab
            field={field}
            timeline={visibleTimeline}
            loading={loading}
            error={timelineError}
            cropCycle={cropCycle}
            selectedActivity={selectedActivity}
            selectedActivityId={selectedActivityId}
            activityMetricType={activityMetricType}
            activityContext={activityContext}
            activityContextLoading={activityContextLoading}
            activityContextError={activityContextError}
            onAddActivity={() => setActivityForm(true)}
            onSelectActivity={setSelectedActivityId}
            onMetricChange={setActivityMetricType}
          />
        )}

        {activeTab === "yield" && (
          <YieldTab
            cropCycle={cropCycle}
            yieldPerAcre={yieldPerAcre}
            estimatedValue={estimatedValue}
            onRecordHarvest={() => setHarvestForm(true)}
          />
        )}

        {activeTab === "report" && (
          <FieldReport
            farm={farm}
            field={field}
            season={season}
            cropCycle={cropCycle}
            timeline={timeline}
            observations={satelliteObservations}
            timelineLoading={loading}
            timelineError={timelineError}
            satelliteLoading={satelliteLoading}
            satelliteError={satelliteError}
            onRefresh={refreshAll}
          />
        )}
      </div>

      {season && cropForm && (
        <StartCropDialog
          field={field}
          season={season}
          onClose={() => setCropForm(false)}
          onSaved={refreshAll}
        />
      )}

      {cropCycle && cropCycle.status === "active" && activityForm && (
        <ActivityDialog
          field={field}
          cropCycle={cropCycle}
          onClose={() => setActivityForm(false)}
          onSaved={refreshAll}
        />
      )}

      {cropCycle && cropCycle.status === "active" && harvestForm && (
        <HarvestDialog
          field={field}
          cropCycle={cropCycle}
          onClose={() => setHarvestForm(false)}
          onSaved={refreshAll}
        />
      )}
    </section>
  );
}

type SatelliteSection = "overview" | "trends" | "radar" | "growth" | "changes" | "history";

const SATELLITE_SECTIONS: Array<{ id: SatelliteSection; label: string; description: string }> = [
  {
    id: "overview",
    label: "Latest imagery",
    description: "Choose a satellite measurement to see its latest usable field images. Different indices describe different aspects of the crop.",
  },
  {
    id: "trends",
    label: "Trends",
    description: "Compare canopy greenness, moisture-sensitive signals, surface temperature and anomaly acreage over time. Activity dates provide context, not proof of causation.",
  },
  {
    id: "radar",
    label: "Radar",
    description: "Sentinel-1 observations work through clouds. Compare compatible passes and read the crop-stage warnings before interpreting radar changes.",
  },
  {
    id: "growth",
    label: "Crop & weather",
    description: "Record observed crop stages and explore weather around field work. Calendar-based growth estimates must be confirmed in the field.",
  },
  {
    id: "changes",
    label: "Changes",
    description: "Compare satellite readings and spatial differences between dates. A change is an observation, not a confirmed disease or irrigation problem.",
  },
  {
    id: "history",
    label: "Data history",
    description: "See when each satellite observed the field, which dates were unusable and how clouds affected the measurements. This is for understanding data availability.",
  },
];

function SatelliteTab({
  field,
  observations,
  loading,
  error,
  ingestion,
  timeline,
  cropCycle,
}: {
  field: Field;
  observations: SatelliteObservation[];
  loading: boolean;
  error: string | null;
  ingestion: SatelliteIngestionJob | null;
  timeline: FieldSatelliteTimeline | null;
  cropCycle: CropCycle | null;
}) {
  const [section, setSection] = useState<SatelliteSection>("overview");
  const [metricType, setMetricType] = useState<SatelliteMetricType>("ndvi");

  const sorted = useMemo(
    () => [...observations].sort((a, b) => b.observed_on.localeCompare(a.observed_on)),
    [observations],
  );
  const usableObservations = useMemo(
    () => sorted.filter((observation) => observation.metrics.length > 0),
    [sorted],
  );
  const skippedObservations = useMemo(
    () => sorted.filter((observation) => {
      const status = observation.metadata_json?.processing_status;
      return typeof status === "string" && status.startsWith("skipped_");
    }),
    [sorted],
  );
  const selectedMetric = FARMER_METRICS.find((metric) => metric.metricType === metricType)
    ?? FARMER_METRICS[0];
  const currentSection = SATELLITE_SECTIONS.find((entry) => entry.id === section)
    ?? SATELLITE_SECTIONS[0];

  return (
    <div className="workspace-page satellite-first-page">
      <header className="workspace-page-title">
        <div>
          <span>SATELLITE EXPLORER</span>
          <h2>{currentSection.label}</h2>
          <p>{currentSection.description}</p>
        </div>
      </header>

      <nav className="satellite-section-tabs" aria-label="Satellite analysis sections">
        {SATELLITE_SECTIONS.map((entry) => (
          <button
            key={entry.id}
            type="button"
            className={section === entry.id ? "satellite-section-tab active" : "satellite-section-tab"}
            aria-current={section === entry.id ? "page" : undefined}
            onClick={() => setSection(entry.id)}
          >
            {entry.label}
          </button>
        ))}
      </nav>

      {loading && (
        <div className="workspace-empty-card">Loading satellite observations…</div>
      )}
      {!loading && error && (
        <div className="workspace-empty-card">
          <h3>Unable to load satellite data</h3>
          <p>{error}</p>
        </div>
      )}

      {!loading && !error && section === "overview" && (
        <>
          {usableObservations.length === 0
            ? <SatelliteIngestionEmptyState ingestion={ingestion} />
            : <>
              <section className="satellite-metric-selector">
                <div>
                  <h3>What would you like to examine?</h3>
                  <p>One measurement at a time makes it easier to compare images without confusing different satellite scales.</p>
                </div>
                <label>
                  <span>Satellite measurement</span>
                  <select
                    value={metricType}
                    onChange={(event) => setMetricType(event.target.value as SatelliteMetricType)}
                  >
                    {FARMER_METRICS.map((metric) => (
                      <option value={metric.metricType} key={metric.metricType}>
                        {metric.label}
                      </option>
                    ))}
                  </select>
                </label>
                <p className="satellite-metric-help">{selectedMetric.subtitle}</p>
              </section>
              <MetricImageryStrip
                key={selectedMetric.metricType}
                field={field}
                observations={usableObservations}
                metric={selectedMetric}
              />
            </>}
        </>
      )}

      {!loading && !error && section === "trends" && (
        <SatelliteTrendCharts fieldId={field.id} cropCycle={cropCycle} section="trends" />
      )}
      {!loading && !error && section === "radar" && (
        <>
          <FieldIntelligencePanel field={field} cropCycle={cropCycle} section="radar" />
          <SatelliteTrendCharts fieldId={field.id} cropCycle={cropCycle} section="radar" />
        </>
      )}
      {!loading && !error && section === "growth" && (
        <>
          <FieldIntelligencePanel field={field} cropCycle={cropCycle} section="growth" />
          <SatelliteTrendCharts fieldId={field.id} cropCycle={cropCycle} section="growth" />
        </>
      )}
      {!loading && !error && section === "changes" && (
        <SatelliteChangePanel fieldId={field.id} cropCycle={cropCycle} />
      )}
      {!loading && !error && section === "history" && (
        <>
          {timeline && timeline.events.length > 0
            ? <CrossSatelliteTimeline timeline={timeline} />
            : <div className="workspace-empty-card">
                <h3>No acquisition history yet</h3>
                <p>When satellite observations are ingested, their dates and availability will appear here.</p>
              </div>}
          <SatelliteTrendCharts fieldId={field.id} cropCycle={cropCycle} section="quality" />
          {skippedObservations.length > 0 && (
            <section className="metric-imagery-section">
              <div className="metric-imagery-heading">
                <div>
                  <h3>Dates without usable imagery</h3>
                  <p>Clouds and insufficient valid pixels can prevent optical indices from being calculated. Sentinel-1 radar may still be available.</p>
                </div>
              </div>
              <div className="metric-imagery-empty">
                {skippedObservations.slice(0, 8).map((observation) => {
                  const status = observation.metadata_json?.processing_status;
                  const fieldCloud = observation.metadata_json?.field_cloud_cover_percent;
                  const cloudPercent = typeof fieldCloud === "number"
                    ? fieldCloud
                    : observation.cloud_cover_percent;
                  return (
                    <div key={observation.id}>
                      <strong>{formatDate(observation.observed_on)}</strong>
                      {" · "}
                      {formatObservationSource(observation.source)}
                      {" · "}
                      {status === "skipped_scene_cloud_cover" ? "Cloud covered" : "No usable field pixels"}
                      {cloudPercent != null ? ` · ${cloudPercent.toFixed(0)}% cloud/shadow` : ""}
                    </div>
                  );
                })}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function CrossSatelliteTimeline({
  timeline,
}: {
  timeline: FieldSatelliteTimeline;
}) {
  const events =
    timeline.events
      .slice(
        0,
        10,
      )
      .reverse();

  const selection =
    timeline.selection;

  const recommended =
    selection.recommended;

  return (
    <section className="cross-satellite-timeline">
      <div className="cross-satellite-timeline-heading">
        <div>
          <span className="workspace-eyebrow">
            UNIFIED TIMELINE
          </span>

          <h3>
            Optical, radar and thermal
          </h3>

          <p>
            Each acquisition stays separate. Radar is shown as
            all-weather context when optical imagery is unavailable.
          </p>
        </div>

        {recommended && (
          <div
            className={
              selection.recommended_kind === "radar_fallback"
                ? "satellite-recommendation radar"
                : "satellite-recommendation"
            }
          >
            <span>
              {selection.recommended_kind === "radar_fallback"
                ? "All-weather fallback"
                : "Nearest usable NDVI"}
            </span>

            <strong>
              {formatObservationSource(
                recommended.source,
              )}
              {" · "}
              {formatDate(
                recommended.observed_on,
              )}
            </strong>

            <small>
              {METRIC_CONFIG[
                recommended.metric_type
              ].label}
              {" "}
              {formatMetricValue(
                recommended.median,
                recommended.metric_type === "lst_c"
                  ? 1
                  : 3,
              )}
              {recommended.days_from_target === 0
                ? " · same date"
                : ` · ${Math.abs(
                    recommended.days_from_target,
                  )}d ${
                    recommended.days_from_target < 0
                      ? "before"
                      : "after"
                  }`}
            </small>
          </div>
        )}
      </div>

      <div className="cross-satellite-events">
        {events.map((event, index) => {
          const metric =
            event.representative_metric;

          const unavailable =
            event.status !== "usable";

          return (
            <div
              key={event.observation_id}
              className="cross-satellite-event-wrap"
            >
              {index > 0 && (
                <span className="cross-satellite-arrow">
                  →
                </span>
              )}

              <article
                className={[
                  "cross-satellite-event",
                  event.source_kind,
                  unavailable
                    ? "unavailable"
                    : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                <div className="cross-satellite-event-top">
                  <strong>
                    {formatDate(
                      event.observed_on,
                    )}
                  </strong>

                  {event.cloud_independent && (
                    <span>
                      All-weather
                    </span>
                  )}
                </div>

                <p>
                  {formatObservationSource(
                    event.source,
                  )}
                </p>

                {event.status === "cloud_skipped" && (
                  <small>
                    Cloud covered
                    {event.field_cloud_cover_percent != null
                      ? ` · ${event.field_cloud_cover_percent.toFixed(0)}%`
                      : event.cloud_cover_percent != null
                        ? ` · ${event.cloud_cover_percent.toFixed(0)}%`
                        : ""}
                  </small>
                )}

                {event.status === "unusable" && (
                  <small>
                    No usable field pixels
                  </small>
                )}

                {event.status === "skipped" && (
                  <small>
                    Scene unavailable
                  </small>
                )}

                {event.status === "unavailable" && (
                  <small>
                    No processed metric
                  </small>
                )}

                {event.status === "usable" && metric && (
                  <small>
                    {METRIC_CONFIG[
                      metric.metric_type
                    ].label}
                    {" "}
                    {formatMetricValue(
                      metric.median,
                      metric.metric_type === "lst_c"
                        ? 1
                        : 3,
                    )}
                    {metric.valid_pixel_percent != null
                      ? ` · ${metric.valid_pixel_percent.toFixed(0)}% valid`
                      : ""}
                  </small>
                )}
              </article>
            </div>
          );
        })}
      </div>

      {selection.recommendation_reason && (
        <p className="cross-satellite-note">
          {selection.recommendation_reason}
        </p>
      )}
    </section>
  );
}


function SatelliteIngestionEmptyState({
  ingestion,
}: {
  ingestion: SatelliteIngestionJob | null;
}) {
  if (!ingestion) {
    return (
      <div className="workspace-empty-card">
        <h3>Waiting for satellite ingestion</h3>

        <p>
          Automatic ingestion has not queued a job for this field yet.
          The ingestion worker will pick it up during its next scan.
        </p>
      </div>
    );
  }

  if (ingestion.status === "pending") {
    return (
      <div className="workspace-empty-card">
        <h3>Satellite history queued</h3>

        <p>
          Optical, all-weather radar, and thermal imagery from{" "}
          {formatDate(ingestion.start_date)}
          {" to "}
          {formatDate(ingestion.end_date)}
          {" is waiting to be processed. This page checks automatically."}
        </p>
      </div>
    );
  }

  if (ingestion.status === "running") {
    return (
      <div className="workspace-empty-card">
        <h3>Processing satellite imagery…</h3>

        <p>
          Sentinel-2 optical, Sentinel-1 radar, and Landsat thermal scenes
          are being processed for this field. Results appear here
          automatically as each source is stored.
        </p>
      </div>
    );
  }

  if (ingestion.status === "failed") {
    return (
      <div className="workspace-empty-card">
        <h3>Satellite ingestion failed</h3>

        <p>
          Automatic processing reached its retry limit.
          {ingestion.last_error
            ? ` Last error: ${ingestion.last_error}`
            : ""}
        </p>
      </div>
    );
  }

  return (
    <div className="workspace-empty-card">
      <h3>No usable satellite scenes found yet</h3>

      <p>
        The latest automatic scan completed without producing usable imagery.
        This field will continue to be checked for new Sentinel-2 scenes.
      </p>
    </div>
  );
}


function MetricImageryStrip({
  field,
  observations,
  metric,
}: {
  field: Field;
  observations: SatelliteObservation[];
  metric: FarmerMetric;
}) {
  const available = observations
    .filter((observation) => {
      const value = getObservationMetric(observation, metric.metricType);

      return Boolean(value?.raster_uri);
    })
    .filter((observation) => {
      const value = getObservationMetric(observation, metric.metricType);

      return (
        value?.valid_pixel_percent == null || value.valid_pixel_percent >= 80
      );
    })
    .slice(0, 3);

  return (
    <section className="metric-imagery-section">
      <div className="metric-imagery-heading">
        <div>
          <h3>{metric.label}</h3>

          <p>{metric.subtitle}</p>
        </div>

        <span>{METRIC_CONFIG[metric.metricType].label}</span>
      </div>

      {metric.metricType === "sar_rvi" && (
        <div className="radar-imagery-scale-note">
          <span>Lower Radar RVI</span>

          <div
            style={{
              background:
                METRIC_CONFIG.sar_rvi.gradient,
            }}
          />

          <span>Higher Radar RVI</span>

          <small>
            Spatial radar signal only · not a bad/good health scale
          </small>
        </div>
      )}

      {available.length === 0 ? (
        <div className="metric-imagery-empty">
          No reliable {METRIC_CONFIG[metric.metricType].label} imagery is
          available yet.
        </div>
      ) : (
        <div className="metric-imagery-grid">
          {available.map((observation) => {
            const value = getObservationMetric(observation, metric.metricType);

            if (!value) {
              return null;
            }

            return (
              <MetricPreviewCard
                key={observation.id}
                field={field}
                observation={observation}
                metric={value}
              />
            );
          })}
        </div>
      )}
    </section>
  );
}

function MetricPreviewCard({
  field,
  observation,
  metric,
}: {
  field: Field;
  observation: SatelliteObservation;
  metric: SatelliteMetric;
}) {
  const points = fieldPolygonPoints(field, 420, 230, 16);

  return (
    <article className="metric-preview-card">
      <div className="metric-preview-image">
        <FieldRasterImage
            fieldId={field.id}
            observationId={observation.id}
            metricType={metric.metric_type}
            points={points}
            alt={`${metric.metric_type} ${observation.observed_on}`}
          />
      </div>

      <div className="metric-preview-meta">
        <div>
          <strong>{formatDate(observation.observed_on)}</strong>

          <span>
            {formatObservationSource(observation.source)}
            {" · "}
            {metric.valid_pixel_percent != null
              ? `${metric.valid_pixel_percent.toFixed(0)}% valid`
              : "Coverage —"}
          </span>

          {formatRadarGeometry(
            observation,
          ) && (
            <span className="metric-preview-radar-geometry">
              {formatRadarGeometry(
                observation,
              )}
            </span>
          )}
        </div>

        <div className="metric-preview-value">
          <span>Median</span>

          <strong>{formatMetricValue(metric.median)}</strong>
        </div>
      </div>
    </article>
  );
}

function ActivitiesTab({
  field,
  timeline,
  loading,
  error,
  cropCycle,
  selectedActivity,
  selectedActivityId,
  activityMetricType,
  activityContext,
  activityContextLoading,
  activityContextError,
  onAddActivity,
  onSelectActivity,
  onMetricChange,
}: {
  field: Field;
  timeline: TimelineItem[];
  loading: boolean;
  error: string | null;
  cropCycle: CropCycle | null;
  selectedActivity: TimelineItem | null;
  selectedActivityId: string | null;
  activityMetricType: SatelliteMetricType;
  activityContext: ActivitySatelliteContext | null;
  activityContextLoading: boolean;
  activityContextError: string | null;
  onAddActivity: () => void;
  onSelectActivity: (id: string) => void;
  onMetricChange: (metric: SatelliteMetricType) => void;
}) {
  return (
    <div className="workspace-page activities-page">
      <div className="workspace-page-title activities-title-row">
        <div>
          <span>FARM ACTIONS</span>

          <h2>Activities</h2>

          <p>
            Record field work, photos and notes. Compare the available satellite measurements before and after an activity without a distracting chart.
          </p>
        </div>

        {cropCycle?.status === "active" && (
          <button className="primary-action" onClick={onAddActivity}>
            <Plus size={17} />
            Add activity
          </button>
        )}
      </div>

      {loading && (
        <div className="workspace-empty-card">Loading activities…</div>
      )}

      {!loading && error && (
        <div className="workspace-empty-card">
          <h3>Unable to load activities</h3>
          <p>{error}</p>
        </div>
      )}

      {!loading && !error && timeline.length === 0 && (
        <div className="workspace-empty-card">
          <h3>No activity recorded</h3>

          <p>
            Add irrigation, fertilizer, spraying, tillage or another farm action
            to start building the field history.
          </p>
        </div>
      )}

      {!loading && !error && selectedActivity && (
        <>
          <section className="latest-activity-card">
            <div className="latest-activity-top">
              <div>
                <span className="workspace-eyebrow">SELECTED ACTIVITY</span>

                <h3>{formatActivityName(selectedActivity.activity_type)}</h3>

                <p>
                  {formatActivityDate(selectedActivity.occurred_at)}

                  {getActivityDetailSummary(selectedActivity)
                    ? ` · ${getActivityDetailSummary(selectedActivity)}`
                    : ""}
                </p>

                {selectedActivity.notes && (
                  <p className="latest-activity-notes">
                    {selectedActivity.notes}
                  </p>
                )}
              </div>

              <label className="activity-primary-metric">
                <span>Response metric</span>

                <select
                  value={activityMetricType}
                  onChange={(event) =>
                    onMetricChange(event.target.value as SatelliteMetricType)
                  }
                >
                  {(Object.keys(METRIC_CONFIG) as SatelliteMetricType[]).map(
                    (metricType) => (
                      <option key={metricType} value={metricType}>
                        {METRIC_CONFIG[metricType].label}
                      </option>
                    ),
                  )}
                </select>
              </label>
            </div>

            <ActivityResponsePanel
              field={field}
              activity={selectedActivity}
              metricType={activityMetricType}
              context={activityContext}
              loading={activityContextLoading}
              error={activityContextError}
            />
          </section>

          <section className="past-activities-section">
            <div className="past-activities-heading">
              <div>
                <span className="workspace-eyebrow">FIELD HISTORY</span>

                <h3>Past activities</h3>
              </div>

              <span>Scroll horizontally →</span>
            </div>

            <div className="past-activities-scroll">
              {timeline.map((item) => (
                <button
                  key={item.id}
                  className={
                    item.id === selectedActivityId
                      ? "past-activity-card selected"
                      : "past-activity-card"
                  }
                  onClick={() => onSelectActivity(item.id)}
                >
                  <span>{formatDate(item.occurred_at.slice(0, 10))}</span>

                  <strong>{formatActivityName(item.activity_type)}</strong>

                  <p>
                    {getActivityDetailSummary(item) ||
                      item.notes ||
                      "Recorded farm activity"}
                  </p>

                  <small>View response →</small>
                </button>
              ))}
            </div>
          </section>
          <ActivityMediaSection
            fieldId={field.id}
            activity={selectedActivity}
          />
        </>
      )}
    </div>
  );
}

function ActivityResponsePanel({
  field,
  activity,
  metricType,
  context,
  loading,
  error,
}: {
  field: Field;
  activity: TimelineItem;
  metricType: SatelliteMetricType;
  context: ActivitySatelliteContext | null;
  loading: boolean;
  error: string | null;
}) {
  const config = getMetricConfig(metricType);

  if (loading) {
    return (
      <div className="activity-response-message">
        Finding usable satellite observations before and after this activity…
      </div>
    );
  }

  if (error) {
    return <div className="activity-response-message error">{error}</div>;
  }

  if (!context) {
    return (
      <div className="activity-response-message">
        No satellite response is available.
      </div>
    );
  }

  const before = context.before;

  const after = context.after;

  const comparison = context.comparison;

  if (!before || !after) {
    return (
      <div className="activity-response-message">
        A usable before and after observation was not found within the 14-day
        window.
      </div>
    );
  }

  return (
    <div className="activity-response-layout">
      <div className="activity-response-chart-card">
        <div className="activity-response-chart-header">
          <div>
            <span>{config.label}</span>

            <h4>Satellite before & after</h4>
          </div>

          <p>{config.description}</p>
        </div>

        <div className="activity-response-stats">
          <div>
            <span>Before</span>

            <strong>{formatMetricValue(before.median)}</strong>

            <small>{formatDate(before.observed_on)}</small>
          </div>

          <div>
            <span>After</span>

            <strong>{formatMetricValue(after.median)}</strong>

            <small>{formatDate(after.observed_on)}</small>
          </div>

          <div>
            <span>Change</span>

            <strong>{formatSignedMetricValue(comparison.median_change)}</strong>

            <small>median</small>
          </div>

          <div>
            <span>Anomaly area</span>

            <strong>
              {before.anomaly_area_acres.toFixed(2)}
              {" → "}
              {after.anomaly_area_acres.toFixed(2)}
              {" ac"}
            </strong>

            <small>relative to field</small>
          </div>
        </div>

        <ActivitySpatialComparisonCards
          field={field}
          metricType={metricType}
          before={before}
          after={after}
        />

        <p className="activity-response-disclaimer">
          These are observed satellite changes around the recorded activity.
          They do not prove that the activity caused the change.
        </p>
      </div>

      <div className="activity-response-summary">
        <span className="workspace-eyebrow">OBSERVED CHANGE</span>

        <h4>{formatActivityName(activity.activity_type)}</h4>

        <p>
          {config.label} changed from{" "}
          <strong>{formatMetricValue(before.median)}</strong> before the
          activity to <strong>{formatMetricValue(after.median)}</strong> after
          it.
        </p>

        {context.spatial_comparison.status === "complete" && (
          <div className="activity-spatial-summary">
            <div>
              <span>Resolved anomaly area</span>

              <strong>
                {context.spatial_comparison.resolved_area_acres?.toFixed(2) ??
                  "—"}
                {" ac"}
              </strong>
            </div>

            <div>
              <span>Persistent</span>

              <strong>
                {context.spatial_comparison.persistent_area_acres?.toFixed(2) ??
                  "—"}
                {" ac"}
              </strong>
            </div>

            <div>
              <span>New</span>

              <strong>
                {context.spatial_comparison.new_area_acres?.toFixed(2) ?? "—"}
                {" ac"}
              </strong>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ActivitySpatialComparisonCards({
  field,
  metricType,
  before,
  after,
}: {
  field: Field;
  metricType: SatelliteMetricType;
  before: ActivitySatelliteObservationMatch;
  after: ActivitySatelliteObservationMatch;
}) {
  return (
    <section className="activity-spatial-section">
      <div className="activity-spatial-section-heading">
        <div>
          <span className="workspace-eyebrow">FIELD VIEW</span>

          <h4>Before / after imagery</h4>
        </div>

        <p>Same field boundary and same metric on both dates.</p>
      </div>

      <div className="activity-spatial-pair">
        <ActivitySpatialCard
          title="Before"
          field={field}
          metricType={metricType}
          observation={before}
        />

        <ActivitySpatialCard
          title="After"
          field={field}
          metricType={metricType}
          observation={after}
        />
      </div>
    </section>
  );
}

function ActivitySpatialCard({
  title,
  field,
  metricType,
  observation,
}: {
  title: "Before" | "After";
  field: Field;
  metricType: SatelliteMetricType;
  observation: ActivitySatelliteObservationMatch;
}) {
  const points = fieldPolygonPoints(field, 420, 230, 16);

  const config = getMetricConfig(metricType);

  return (
    <article className="activity-spatial-card">
      <div className="activity-spatial-card-header">
        <div>
          <span>{title}</span>

          <strong>{formatDate(observation.observed_on)}</strong>
        </div>

        <small>{config.label}</small>
      </div>

      <div className="activity-spatial-card-image">
        <FieldRasterImage
            fieldId={field.id}
            observationId={observation.observation_id}
            metricType={metricType}
            points={points}
            alt={`${title} ${config.label} ${observation.observed_on}`}
          />
      </div>

      <div className="activity-spatial-card-meta">
        <div>
          <span>Median</span>

          <strong>{formatMetricValue(observation.median)}</strong>
        </div>

        <div>
          <span>Valid</span>

          <strong>{observation.valid_pixel_percent.toFixed(0)}%</strong>
        </div>

        <div>
          <span>Anomaly</span>

          <strong>
            {observation.anomaly_area_acres.toFixed(2)}
            {" ac"}
          </strong>
        </div>
      </div>
    </article>
  );
}

function YieldTab({
  cropCycle,
  yieldPerAcre,
  estimatedValue,
  onRecordHarvest,
}: {
  cropCycle: CropCycle | null;
  yieldPerAcre: number | null;
  estimatedValue: number | null;
  onRecordHarvest: () => void;
}) {
  return (
    <div className="workspace-page">
      <div className="workspace-page-title">
        <div>
          <span>CROP OUTCOME</span>

          <h2>Yield</h2>

          <p>Harvest and production outcome for the selected crop cycle.</p>
        </div>

        {cropCycle?.status === "active" && (
          <button
            className="harvest-button workspace-harvest-button"
            onClick={onRecordHarvest}
          >
            Record harvest
          </button>
        )}
      </div>

      {!cropCycle && (
        <div className="workspace-empty-card">
          No crop exists for this season.
        </div>
      )}

      {cropCycle?.status === "active" && (
        <div className="yield-active-card">
          <span className="workspace-eyebrow">ACTIVE CROP</span>

          <h3>
            {cropCycle.crop_name}

            {cropCycle.variety ? ` · ${cropCycle.variety}` : ""}
          </h3>

          <p>Harvest has not been recorded yet.</p>

          <div className="yield-active-meta">
            <div>
              <span>Started</span>
              <strong>{cropCycle.started_on}</strong>
            </div>

            <div>
              <span>Expected harvest</span>
              <strong>{cropCycle.expected_harvest_on ?? "—"}</strong>
            </div>
          </div>
        </div>
      )}

      {cropCycle?.status === "completed" && (
        <div className="yield-dashboard">
          <div>
            <span>Total yield</span>

            <strong>
              {cropCycle.yield_kg != null
                ? `${cropCycle.yield_kg.toLocaleString("en-IN")} kg`
                : "—"}
            </strong>
          </div>

          <div>
            <span>Yield / acre</span>

            <strong>
              {yieldPerAcre != null ? `${yieldPerAcre.toFixed(0)} kg/ac` : "—"}
            </strong>
          </div>

          <div>
            <span>Harvested area</span>

            <strong>
              {cropCycle.harvested_area_acres != null
                ? `${cropCycle.harvested_area_acres.toFixed(2)} ac`
                : "—"}
            </strong>
          </div>

          <div>
            <span>Moisture</span>

            <strong>
              {cropCycle.moisture_percent != null
                ? `${cropCycle.moisture_percent}%`
                : "—"}
            </strong>
          </div>

          <div>
            <span>Quality</span>

            <strong>{cropCycle.quality_grade ?? "—"}</strong>
          </div>

          <div>
            <span>Estimated value</span>

            <strong>
              {estimatedValue != null
                ? `₹${estimatedValue.toLocaleString("en-IN", {
                    maximumFractionDigits: 0,
                  })}`
                : "—"}
            </strong>
          </div>
        </div>
      )}
    </div>
  );
}

function fieldPolygonPoints(
  field: Field,
  width: number,
  height: number,
  padding: number,
) {
  const ring = field.boundary.coordinates[0];

  if (!ring?.length) {
    return "";
  }

  const lngs = ring.map(([lng]) => lng);

  const lats = ring.map(([, lat]) => lat);

  const minLng = Math.min(...lngs);

  const maxLng = Math.max(...lngs);

  const minLat = Math.min(...lats);

  const maxLat = Math.max(...lats);

  const lngRange = Math.max(maxLng - minLng, 0.000001);

  const latRange = Math.max(maxLat - minLat, 0.000001);

  const innerWidth = width - padding * 2;

  const innerHeight = height - padding * 2;

  const scale = Math.min(innerWidth / lngRange, innerHeight / latRange);

  const renderedWidth = lngRange * scale;

  const renderedHeight = latRange * scale;

  const offsetX = (width - renderedWidth) / 2;

  const offsetY = (height - renderedHeight) / 2;

  return ring
    .map(([lng, lat]) => {
      const x = offsetX + (lng - minLng) * scale;

      const y = offsetY + (maxLat - lat) * scale;

      return `${x},${y}`;
    })
    .join(" ");
}

function StartCropDialog({
  field,
  season,
  onClose,
  onSaved,
}: {
  field: Field;
  season: Season;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [cropName, setCropName] = useState("");

  const [variety, setVariety] = useState("");

  const [startedOn, setStartedOn] = useState(localDateInputValue());

  const [plantedOn, setPlantedOn] = useState("");

  const [saving, setSaving] = useState(false);

  const [error, setError] = useState<string | null>(null);

  async function save() {
    if (!cropName.trim()) {
      setError("Crop name is required.");

      return;
    }

    try {
      setSaving(true);
      setError(null);

      await createCropCycle(season.id, {
        field_id: field.id,
        crop_name: cropName.trim(),
        variety: variety.trim() || null,
        started_on: startedOn,
        planted_on: plantedOn || null,
        expected_harvest_on: null,
        notes: null,
      });

      await onSaved();

      onClose();
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Unable to start crop.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="dialog-card">
        <h2>Start crop</h2>

        <p className="dialog-muted">
          {field.name}
          {" · "}
          {season.name}
        </p>

        <label>Crop</label>

        <input
          className="form-input"
          value={cropName}
          onChange={(event) => setCropName(event.target.value)}
          placeholder="Paddy"
        />

        <label>Variety</label>

        <input
          className="form-input"
          value={variety}
          onChange={(event) => setVariety(event.target.value)}
          placeholder="PR-126"
        />

        <label>Crop cycle started</label>

        <input
          className="form-input"
          type="date"
          value={startedOn}
          onChange={(event) => setStartedOn(event.target.value)}
        />

        <label>Sowing / transplanting date</label>

        <input
          className="form-input"
          type="date"
          value={plantedOn}
          onChange={(event) => setPlantedOn(event.target.value)}
        />

        {error && <div className="login-error">{error}</div>}

        <div className="dialog-actions">
          <button className="secondary-action" onClick={onClose}>
            Cancel
          </button>

          <button className="primary-action" onClick={save} disabled={saving}>
            {saving ? "Saving..." : "Start crop"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ActivityDialog({
  field,
  cropCycle,
  onClose,
  onSaved,
}: {
  field: Field;
  cropCycle: CropCycle;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [activityType, setActivityType] = useState("irrigation");

  const [occurredAt, setOccurredAt] = useState(currentDateTime());

  const [notes, setNotes] = useState("");

  const [product, setProduct] = useState("");

  const [quantity, setQuantity] = useState("");

  const [unit, setUnit] = useState("");

  const [duration, setDuration] = useState("");

  const [source, setSource] = useState("");

  const [saving, setSaving] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const inputActivity = [
    "fertilizer",
    "herbicide",
    "pesticide",
    "fungicide",
  ].includes(activityType);

  async function save() {
    const details: Record<string, unknown> = {};

    if (activityType === "irrigation") {
      if (duration) {
        details.duration_minutes = Number(duration);
      }

      if (source.trim()) {
        details.source = source.trim();
      }
    }

    if (inputActivity) {
      if (product.trim()) {
        details.product = product.trim();
      }

      if (quantity) {
        details.quantity = Number(quantity);
      }

      if (unit.trim()) {
        details.unit = unit.trim();
      }
    }

    try {
      setSaving(true);
      setError(null);

      await createActivity(field.id, {
        crop_cycle_id: cropCycle.id,
        activity_type: activityType,
        occurred_at: new Date(occurredAt).toISOString(),
        notes: notes.trim() || null,
        details,
      });

      await onSaved();

      onClose();
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Unable to save activity.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="dialog-card">
        <h2>Add activity</h2>

        <p className="dialog-muted">
          {cropCycle.crop_name}

          {cropCycle.variety ? ` · ${cropCycle.variety}` : ""}
        </p>

        <label>Activity</label>

        <select
          className="form-input"
          value={activityType}
          onChange={(event) => setActivityType(event.target.value)}
        >
          <option value="irrigation">Irrigation</option>

          <option value="sowing">Sowing</option>

          <option value="transplanting">Transplanting</option>

          <option value="fertilizer">Fertilizer</option>

          <option value="herbicide">Herbicide</option>

          <option value="pesticide">Pesticide</option>

          <option value="fungicide">Fungicide</option>

          <option value="tillage">Tillage</option>

          <option value="weeding">Weeding</option>

          <option value="observation">Observation</option>

          <option value="incident">Incident</option>

          <option value="other">Other</option>
        </select>

        <label>Date & time</label>

        <input
          className="form-input"
          type="datetime-local"
          value={occurredAt}
          onChange={(event) => setOccurredAt(event.target.value)}
        />

        {activityType === "irrigation" && (
          <>
            <label>Duration in minutes</label>

            <input
              className="form-input"
              type="number"
              value={duration}
              onChange={(event) => setDuration(event.target.value)}
            />

            <label>Water source</label>

            <input
              className="form-input"
              value={source}
              onChange={(event) => setSource(event.target.value)}
              placeholder="Tube well"
            />
          </>
        )}

        {inputActivity && (
          <>
            <label>Product</label>

            <input
              className="form-input"
              value={product}
              onChange={(event) => setProduct(event.target.value)}
              placeholder="Urea"
            />

            <label>Quantity / dose</label>

            <input
              className="form-input"
              type="number"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
            />

            <label>Unit</label>

            <input
              className="form-input"
              value={unit}
              onChange={(event) => setUnit(event.target.value)}
              placeholder="kg_per_acre"
            />
          </>
        )}

        <label>Notes</label>

        <textarea
          className="form-input"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
        />

        {error && <div className="login-error">{error}</div>}

        <div className="dialog-actions">
          <button className="secondary-action" onClick={onClose}>
            Cancel
          </button>

          <button className="primary-action" onClick={save} disabled={saving}>
            {saving ? "Saving..." : "Save activity"}
          </button>
        </div>
      </div>
    </div>
  );
}

function HarvestDialog({
  field,
  cropCycle,
  onClose,
  onSaved,
}: {
  field: Field;
  cropCycle: CropCycle;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [harvestedAt, setHarvestedAt] = useState(currentDateTime());

  const [yieldKg, setYieldKg] = useState("");

  const [harvestedArea, setHarvestedArea] = useState(
    field.area_acres.toFixed(2),
  );

  const [moisture, setMoisture] = useState("");

  const [quality, setQuality] = useState("");

  const [sellingPrice, setSellingPrice] = useState("");

  const [notes, setNotes] = useState("");

  const [saving, setSaving] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const yieldNumber = Number(yieldKg);

  const areaNumber = Number(harvestedArea);

  const liveYieldPerAcre =
    yieldNumber > 0 && areaNumber > 0 ? yieldNumber / areaNumber : null;

  const liveEstimatedValue =
    yieldNumber > 0 && Number(sellingPrice) > 0
      ? yieldNumber * Number(sellingPrice)
      : null;

  async function save() {
    if (!Number.isFinite(yieldNumber) || yieldNumber <= 0) {
      setError("Enter the total harvested yield.");

      return;
    }

    if (!Number.isFinite(areaNumber) || areaNumber <= 0) {
      setError("Harvested area must be greater than zero.");

      return;
    }

    if (moisture && (Number(moisture) < 0 || Number(moisture) > 100)) {
      setError("Moisture must be between 0 and 100.");

      return;
    }

    try {
      setSaving(true);
      setError(null);

      await harvestCropCycle(cropCycle.id, {
        harvested_at: new Date(harvestedAt).toISOString(),
        yield_kg: yieldNumber,
        harvested_area_acres: areaNumber,
        moisture_percent: moisture ? Number(moisture) : null,
        quality_grade: quality.trim() || null,
        selling_price_per_kg: sellingPrice ? Number(sellingPrice) : null,
        notes: notes.trim() || null,
      });

      await onSaved();

      onClose();
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Unable to record harvest.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="dialog-card harvest-dialog">
        <h2>Record harvest</h2>

        <p className="dialog-muted">
          {field.name}
          {" · "}
          {cropCycle.crop_name}

          {cropCycle.variety ? ` · ${cropCycle.variety}` : ""}
        </p>

        <label>Harvest date & time</label>

        <input
          className="form-input"
          type="datetime-local"
          value={harvestedAt}
          onChange={(event) => setHarvestedAt(event.target.value)}
        />

        <div className="harvest-form-grid">
          <div>
            <label>Total yield</label>

            <div className="input-with-unit">
              <input
                className="form-input"
                type="number"
                min="0"
                step="0.01"
                value={yieldKg}
                onChange={(event) => setYieldKg(event.target.value)}
                placeholder="3200"
              />

              <span>kg</span>
            </div>
          </div>

          <div>
            <label>Harvested area</label>

            <div className="input-with-unit">
              <input
                className="form-input"
                type="number"
                min="0"
                step="0.01"
                value={harvestedArea}
                onChange={(event) => setHarvestedArea(event.target.value)}
              />

              <span>acres</span>
            </div>
          </div>
        </div>

        {liveYieldPerAcre != null && (
          <div className="yield-preview">
            <span>Yield per acre</span>

            <strong>
              {liveYieldPerAcre.toFixed(0)}
              {" kg/ac"}
            </strong>
          </div>
        )}

        <label>Grain / produce moisture</label>

        <div className="input-with-unit">
          <input
            className="form-input"
            type="number"
            min="0"
            max="100"
            step="0.1"
            value={moisture}
            onChange={(event) => setMoisture(event.target.value)}
            placeholder="18"
          />

          <span>%</span>
        </div>

        <label>Quality / grade</label>

        <input
          className="form-input"
          value={quality}
          onChange={(event) => setQuality(event.target.value)}
          placeholder="Grade A / FAQ / Premium"
        />

        <label>Selling price</label>

        <div className="input-with-unit">
          <input
            className="form-input"
            type="number"
            min="0"
            step="0.01"
            value={sellingPrice}
            onChange={(event) => setSellingPrice(event.target.value)}
            placeholder="24"
          />

          <span>₹/kg</span>
        </div>

        {liveEstimatedValue != null && (
          <div className="harvest-value-preview">
            <span>Estimated crop value</span>

            <strong>
              ₹
              {liveEstimatedValue.toLocaleString("en-IN", {
                maximumFractionDigits: 0,
              })}
            </strong>
          </div>
        )}

        <label>Harvest notes</label>

        <textarea
          className="form-input"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          placeholder="Crop quality, lodging, losses, disease damage, etc."
        />

        {error && <div className="login-error">{error}</div>}

        <div className="harvest-warning">
          Recording harvest will complete this crop cycle.
        </div>

        <div className="dialog-actions">
          <button
            className="secondary-action"
            disabled={saving}
            onClick={onClose}
          >
            Cancel
          </button>

          <button
            className="harvest-confirm-button"
            disabled={saving}
            onClick={save}
          >
            {saving ? "Recording..." : "Complete harvest"}
          </button>
        </div>
      </div>
    </div>
  );
}
