import { useEffect, useMemo, useState } from "react";

import { getCropRadarScreening } from "../lib/api";
import type { CropRadarScreening, RadarOrbitScreen, RadarScreenMetric } from "../types/api";

type Props = {
  cropCycleId: string;
  stagesFingerprint: string;
  selectedOrbitKey: string;
};

function displayDate(value: string) {
  return new Date(value.slice(0, 10) + "T00:00:00Z").toLocaleDateString("en-IN", {
    day: "2-digit", month: "short", year: "numeric",
  });
}

function valueDisplay(value: number | null, digits = 2) {
  return value == null ? "—" : value.toFixed(digits);
}

const LABELS: Record<string, string> = {
  sar_vh_db: "VH · vegetation structure-sensitive",
  sar_vv_db: "VV · surface/moisture-sensitive",
  sar_rvi: "Radar RVI · relative structure",
};

function MetricTable({ metrics }: { metrics: RadarScreenMetric[] }) {
  return (
    <div className="radar-screen-table-scroll">
      <table className="radar-screen-table">
        <thead>
          <tr>
            <th>Radar signal</th>
            <th>Latest</th>
            <th>Stage reference</th>
            <th>Difference</th>
            <th>Screening range</th>
            <th>Earlier passes</th>
            <th>Result</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((metric) => (
            <tr key={metric.metric_type}>
              <td>{LABELS[metric.metric_type] ?? metric.metric_type}</td>
              <td>{valueDisplay(metric.latest_value, 3)} {metric.unit === "dB" ? "dB" : ""}</td>
              <td>{valueDisplay(metric.reference_median, 3)}</td>
              <td>
                {metric.difference != null && metric.difference >= 0 ? "+" : ""}
                {valueDisplay(metric.difference, 3)}
              </td>
              <td>
                {metric.screening_threshold == null
                  ? "—"
                  : "±" + valueDisplay(metric.screening_threshold, 3)}
              </td>
              <td>{metric.baseline_passes}/{metric.required_baseline_passes} min.</td>
              <td>
                {metric.status === "unusual_variation" ? "Unusual variation — inspect" :
                  metric.status === "within_reference_range" ? "Within screening range" :
                  metric.status === "unverified_stage" ? "Stage not confirmed" :
                  metric.status === "unsupported_crop" ? "Crop not calibrated" :
                  "More comparable passes needed"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OrbitReport({ report }: { report: RadarOrbitScreen }) {
  return (
    <div className="radar-screen-orbit-report">
      <div className="radar-screen-orbit-facts">
        <div>
          <span>Acquisition</span>
          <strong>{displayDate(report.observed_on)}</strong>
        </div>
        <div>
          <span>Crop growth stage at acquisition</span>
          <strong>{report.stage_label ?? "Unknown"}</strong>
          <small>
            {report.stage_source === "farmer_confirmed" ? "Farmer-confirmed" :
              report.stage_source === "provisional" ? "Unverified calendar estimate" :
              "No growth-stage evidence"}
          </small>
        </div>
        <div>
          <span>Preceding 3-day rainfall</span>
          <strong>
            {report.weather.precipitation_3_day_mm == null
              ? "Unavailable"
              : valueDisplay(report.weather.precipitation_3_day_mm, 1) + " mm"}
          </strong>
          <small>Modeled, {report.weather.days_available}/3 days covered</small>
        </div>
        <div>
          <span>Screening result</span>
          <strong className={report.status === "review_variation" ? "radar-screen-review" : ""}>
            {report.status === "review_variation" ? "Variation to inspect" :
              report.status === "within_reference_range" ? "No unusual variation found" :
              "Insufficient evidence"}
          </strong>
          <small>Not a crop-health diagnosis</small>
        </div>
      </div>

      {report.metrics.length > 0
        ? <MetricTable metrics={report.metrics} />
        : <p className="radar-screen-empty">No valid VV/VH/RVI metric for the latest pass.</p>}

      <div className="radar-screen-context">
        {report.optical.length > 0 && (
          <p>
            Nearby optical signals: {report.optical.map((x) =>
              x.metric_type.toUpperCase() + " " + x.value.toFixed(3) + " (" +
              displayDate(x.observed_on) + ", " + x.days_from_radar + "d before radar)"
            ).join(" · ")}
          </p>
        )}
        {report.nearby_activities.length > 0 && (
          <p>Recent farm activities: {report.nearby_activities.join(", ").replace(/_/g, " ")}</p>
        )}
        {report.explanations.map((note) => <p key={note}>{note}</p>)}
      </div>
    </div>
  );
}

export default function RadarScreeningPanel({ cropCycleId, stagesFingerprint, selectedOrbitKey }: Props) {
  const [result, setResult] = useState<CropRadarScreening | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setResult(null);
    void getCropRadarScreening(cropCycleId)
      .then((value) => {
        if (cancelled) return;
        setResult(value);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unable to load radar screening.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [cropCycleId, stagesFingerprint, refresh]);

  const active = useMemo(
    () => result?.orbits.find((orbit) => orbit.radar_orbit_key === selectedOrbitKey) ??
      (!selectedOrbitKey ? result?.orbits[0] ?? null : null),
    [result, selectedOrbitKey],
  );

  return (
    <article className="radar-screen-panel">
      <div className="radar-screen-heading">
        <div>
          <span className="workspace-eyebrow">RADAR CHANGE SCREENING</span>
          <h4>Crop- and stage-aware variation checks</h4>
          <p>
            Compares current field-median signals with earlier passes from the
            same orbit and confirmed growth stage. This is an exploratory
            review aid, not an automatic crop-health alert.
          </p>
        </div>
        <button type="button" onClick={() => setRefresh((x) => x + 1)} disabled={loading}>
          Refresh screening
        </button>
      </div>

      {loading && <p className="radar-screen-message">Checking radar observations and growth-stage dates…</p>}
      {!loading && error && <p className="radar-screen-message error">{error}</p>}
      {!loading && !error && result && (
        <>
          {result.orbits.length === 0 ? (
            <p className="radar-screen-message">
              No usable, fully identified Sentinel-1 orbit passes are available in the crop cycle.
            </p>
          ) : (
            <>
              <p className="radar-screen-message">
                Radar geometry selected above: {selectedOrbitKey || "Loading selection…"}
              </p>
              {!active && (
                <p className="radar-screen-message">
                  The selected orbit has no valid screening geometry. Choose a complete
                  orbit in the radar chart selector above.
                </p>
              )}
              {active && <OrbitReport report={active} />}
            </>
          )}
          {result.warnings.map((warning) => <p key={warning} className="radar-screen-warning">{warning}</p>)}
          <p className="radar-screen-disclaimer">{result.statement} Thresholds are provisional
            engineering screening guardrails, not validated crop-specific agronomic limits.
            An absence of flagged variation does not prove crop health.</p>
        </>
      )}
    </article>
  );
}
