import { useEffect, useState } from "react";

import { X } from "lucide-react";

import { getActivitySatelliteContext } from "../lib/api";

import type {
  ActivitySatelliteContext,
  SatelliteMetricType,
  TimelineItem,
} from "../types/api";

import { METRIC_OPTIONS, getMetricConfig } from "./farm-map/satellite";

type Props = {
  activity: TimelineItem;
  onClose: () => void;
};

function formatObservationDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatMetricValue(value: number | null, digits = 3) {
  return value == null || !Number.isFinite(value) ? "—" : value.toFixed(digits);
}

function formatSignedMetricValue(value: number | null, digits = 3) {
  if (value == null || !Number.isFinite(value)) {
    return "—";
  }

  const prefix = value > 0 ? "+" : "";

  return `${prefix}${value.toFixed(digits)}`;
}

function formatSignedPercent(value: number | null) {
  if (value == null || !Number.isFinite(value)) {
    return "—";
  }

  const prefix = value > 0 ? "+" : "";

  return `${prefix}${value.toFixed(1)}%`;
}

function formatArea(value: number | null) {
  return value == null || !Number.isFinite(value)
    ? "—"
    : `${value.toFixed(2)} ac`;
}

function formatSignedArea(value: number | null) {
  if (value == null || !Number.isFinite(value)) {
    return "—";
  }

  const prefix = value > 0 ? "+" : "";

  return `${prefix}${value.toFixed(2)} ac`;
}

function formatActivityName(value: string) {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatDaysFromActivity(days: number) {
  if (days === 0) {
    return "same day";
  }

  const count = Math.abs(days);
  const unit = count === 1 ? "day" : "days";

  return days < 0 ? `${count} ${unit} before` : `${count} ${unit} after`;
}

export default function ActivitySatelliteComparison({
  activity,
  onClose,
}: Props) {
  const [metricType, setMetricType] = useState<SatelliteMetricType>("ndvi");

  const [context, setContext] = useState<ActivitySatelliteContext | null>(null);

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    setLoading(true);
    setError(null);
    setContext(null);

    void getActivitySatelliteContext(activity.id, metricType, 14, 80)
      .then((result) => {
        if (!cancelled) {
          setContext(result);
        }
      })
      .catch((requestError: unknown) => {
        if (cancelled) {
          return;
        }

        console.error(
          "Failed to load activity satellite context:",
          requestError,
        );

        setError(
          requestError instanceof Error
            ? requestError.message
            : "Unable to load satellite response.",
        );
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activity.id, metricType]);

  const metricConfig = getMetricConfig(metricType);

  const before = context?.before ?? null;
  const after = context?.after ?? null;

  const comparison = context?.comparison ?? null;

  const spatial = context?.spatial_comparison ?? null;

  return (
    <section className="activity-satellite-card">
      <div className="activity-satellite-header">
        <div>
          <span className="activity-satellite-eyebrow">SATELLITE RESPONSE</span>

          <strong>{formatActivityName(activity.activity_type)}</strong>
        </div>

        <button
          type="button"
          className="activity-satellite-close"
          onClick={onClose}
          aria-label="Close satellite response"
        >
          <X size={16} />
        </button>
      </div>

      <p className="activity-satellite-date">
        Activity recorded{" "}
        {new Date(activity.occurred_at).toLocaleString("en-IN")}
      </p>

      <label className="activity-satellite-metric">
        <span>Metric</span>

        <select
          value={metricType}
          onChange={(event) =>
            setMetricType(event.target.value as SatelliteMetricType)
          }
        >
          {METRIC_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

      <p className="activity-satellite-description">
        {metricConfig.description}
      </p>

      {loading && (
        <p className="activity-satellite-message">
          Finding the nearest usable observations before and after this
          activity…
        </p>
      )}

      {error && <p className="activity-satellite-message error">{error}</p>}

      {!loading && !error && context && (
        <>
          {comparison?.status !== "complete" && (
            <p className="activity-satellite-message">
              {comparison?.status === "missing_before" &&
                "No usable observation was found before this activity within the 14-day window."}

              {comparison?.status === "missing_after" &&
                "No usable observation was found after this activity within the 14-day window."}

              {comparison?.status === "missing_both" &&
                "No usable before or after observations were found within the 14-day window."}
            </p>
          )}

          <div className="activity-satellite-observations">
            <div className="activity-satellite-observation">
              <span>Before</span>

              {before ? (
                <>
                  <strong>{formatObservationDate(before.observed_on)}</strong>

                  <small>
                    {formatDaysFromActivity(before.days_from_activity)}
                    {" · "}
                    {before.valid_pixel_percent.toFixed(0)}
                    {"% valid"}
                  </small>
                </>
              ) : (
                <strong>Not available</strong>
              )}
            </div>

            <div className="activity-satellite-observation">
              <span>After</span>

              {after ? (
                <>
                  <strong>{formatObservationDate(after.observed_on)}</strong>

                  <small>
                    {formatDaysFromActivity(after.days_from_activity)}
                    {" · "}
                    {after.valid_pixel_percent.toFixed(0)}
                    {"% valid"}
                  </small>
                </>
              ) : (
                <strong>Not available</strong>
              )}
            </div>
          </div>

          <div className="activity-satellite-table">
            <div className="activity-satellite-table-row heading">
              <span>{metricConfig.label}</span>
              <span>Before</span>
              <span>After</span>
              <span>Change</span>
            </div>

            <div className="activity-satellite-table-row">
              <span>Median</span>
              <strong>{formatMetricValue(before?.median ?? null)}</strong>
              <strong>{formatMetricValue(after?.median ?? null)}</strong>
              <strong>
                {formatSignedMetricValue(comparison?.median_change ?? null)}
              </strong>
            </div>

            <div className="activity-satellite-table-row">
              <span>Mean</span>
              <strong>{formatMetricValue(before?.mean ?? null)}</strong>
              <strong>{formatMetricValue(after?.mean ?? null)}</strong>
              <strong>
                {formatSignedMetricValue(comparison?.mean_change ?? null)}
              </strong>
            </div>

            <div className="activity-satellite-table-row secondary">
              <span>Median %</span>
              <span>—</span>
              <span>—</span>
              <strong>
                {formatSignedPercent(comparison?.median_percent_change ?? null)}
              </strong>
            </div>
          </div>

          <div className="activity-satellite-anomaly-summary">
            <div className="activity-satellite-section-title">
              Relative anomaly area
            </div>

            <div className="activity-satellite-anomaly-flow">
              <div>
                <span>Before</span>
                <strong>
                  {formatArea(before?.anomaly_area_acres ?? null)}
                </strong>
                <small>
                  {before
                    ? `${before.anomaly_zone_count} zone${
                        before.anomaly_zone_count === 1 ? "" : "s"
                      }`
                    : "—"}
                </small>
              </div>

              <span className="activity-satellite-arrow">→</span>

              <div>
                <span>After</span>
                <strong>{formatArea(after?.anomaly_area_acres ?? null)}</strong>
                <small>
                  {after
                    ? `${after.anomaly_zone_count} zone${
                        after.anomaly_zone_count === 1 ? "" : "s"
                      }`
                    : "—"}
                </small>
              </div>

              <div>
                <span>Change</span>
                <strong>
                  {formatSignedArea(
                    comparison?.anomaly_area_acres_change ?? null,
                  )}
                </strong>
              </div>
            </div>
          </div>

          {spatial?.status === "complete" && (
            <div className="activity-satellite-spatial">
              <div className="activity-satellite-section-title">
                Spatial change
              </div>

              <div className="activity-satellite-spatial-grid">
                <div>
                  <span>Resolved</span>
                  <strong>{formatArea(spatial.resolved_area_acres)}</strong>
                </div>

                <div>
                  <span>Persistent</span>
                  <strong>{formatArea(spatial.persistent_area_acres)}</strong>
                </div>

                <div>
                  <span>New</span>
                  <strong>{formatArea(spatial.new_area_acres)}</strong>
                </div>
              </div>
            </div>
          )}

          <p className="activity-satellite-disclaimer">
            This is an observed before/after satellite change. It does not prove
            that the recorded farm activity caused the change.
          </p>
        </>
      )}
    </section>
  );
}
