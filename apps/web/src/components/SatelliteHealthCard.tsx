import { useMemo } from "react";

import type { SatelliteObservation } from "../types/api";

type Props = {
  observations: SatelliteObservation[];

  loading: boolean;
};

function formatDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
  });
}

function formatLongDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function isReliable(observation: SatelliteObservation) {
  if (observation.ndvi_mean == null) {
    return false;
  }

  const cloudOkay =
    observation.cloud_cover_percent == null ||
    observation.cloud_cover_percent <= 20;

  const pixelsOkay =
    observation.valid_pixel_percent == null ||
    observation.valid_pixel_percent >= 80;

  return cloudOkay && pixelsOkay;
}

export default function SatelliteHealthCard({ observations, loading }: Props) {
  const reliable = useMemo(
    () =>
      observations
        .filter(isReliable)
        .sort((first, second) =>
          first.observed_on.localeCompare(second.observed_on),
        ),
    [observations],
  );

  if (loading) {
    return (
      <section className="satellite-card">
        <span className="section-label">SATELLITE HEALTH</span>

        <p className="dialog-muted">Loading satellite observations…</p>
      </section>
    );
  }

  if (observations.length === 0) {
    return (
      <section className="satellite-card">
        <span className="section-label">SATELLITE HEALTH</span>

        <h3>No satellite data</h3>

        <p className="dialog-muted">
          Satellite observations have not been collected for this field yet.
        </p>
      </section>
    );
  }

  if (reliable.length === 0) {
    return (
      <section className="satellite-card">
        <span className="section-label">SATELLITE HEALTH</span>

        <h3>No reliable observation</h3>

        <p className="dialog-muted">
          Satellite scenes exist, but they are currently too cloudy or contain
          too few valid pixels.
        </p>
      </section>
    );
  }

  const latest = reliable[reliable.length - 1];

  const previous = reliable.length >= 2 ? reliable[reliable.length - 2] : null;

  const change =
    latest.ndvi_mean != null && previous?.ndvi_mean != null
      ? latest.ndvi_mean - previous.ndvi_mean
      : null;

  return (
    <section className="satellite-card">
      <div className="satellite-heading">
        <div>
          <span className="section-label">SATELLITE HEALTH</span>

          <h3>Vegetation condition</h3>
        </div>

        <span className="satellite-source">Sentinel-2</span>
      </div>

      <div className="satellite-main-stat">
        <div>
          <span>Latest reliable NDVI</span>

          <strong>{latest.ndvi_mean?.toFixed(2)}</strong>
        </div>

        {change != null && (
          <div
            className={
              change >= 0 ? "ndvi-change positive" : "ndvi-change negative"
            }
          >
            <span>{change >= 0 ? "↑" : "↓"}</span>

            <strong>
              {change >= 0 ? "+" : ""}
              {change.toFixed(2)}
            </strong>
          </div>
        )}
      </div>

      <NdviChart observations={reliable} />

      <div className="satellite-observation-info">
        <div>
          <span>Observation</span>

          <strong>{formatLongDate(latest.observed_on)}</strong>
        </div>

        <div>
          <span>Cloud cover</span>

          <strong>
            {latest.cloud_cover_percent != null
              ? `${latest.cloud_cover_percent.toFixed(1)}%`
              : "—"}
          </strong>
        </div>

        <div>
          <span>Valid pixels</span>

          <strong>
            {latest.valid_pixel_percent != null
              ? `${latest.valid_pixel_percent.toFixed(0)}%`
              : "—"}
          </strong>
        </div>

        <div>
          <span>NDWI</span>

          <strong>
            {latest.ndwi_mean != null ? latest.ndwi_mean.toFixed(2) : "—"}
          </strong>
        </div>
      </div>

      <div className="satellite-history">
        <span className="satellite-history-title">Recent observations</span>

        {[...reliable]
          .reverse()
          .slice(0, 5)
          .map((observation) => (
            <div key={observation.id} className="satellite-history-row">
              <span>{formatDate(observation.observed_on)}</span>

              <strong>NDVI {observation.ndvi_mean?.toFixed(2)}</strong>

              <small>
                {observation.cloud_cover_percent != null
                  ? `${observation.cloud_cover_percent.toFixed(0)}% cloud`
                  : ""}
              </small>
            </div>
          ))}
      </div>

      {observations.length > reliable.length && (
        <p className="satellite-quality-note">
          {observations.length - reliable.length} observation
          {observations.length - reliable.length === 1 ? "" : "s"} ignored
          because of cloud cover or insufficient valid pixels.
        </p>
      )}
    </section>
  );
}

function NdviChart({ observations }: { observations: SatelliteObservation[] }) {
  const chartObservations = observations.slice(-8);

  if (chartObservations.length === 0) {
    return null;
  }

  const width = 320;
  const height = 130;

  const paddingLeft = 10;
  const paddingRight = 10;

  const paddingTop = 12;
  const paddingBottom = 28;

  const chartWidth = width - paddingLeft - paddingRight;

  const chartHeight = height - paddingTop - paddingBottom;

  const values = chartObservations.map(
    (observation) => observation.ndvi_mean ?? 0,
  );

  /*
   * NDVI fundamentally ranges
   * from -1 to 1.
   *
   * For crop visualization we
   * display 0 - 1 because that is
   * the useful vegetation range
   * for this first version.
   */
  function yForValue(value: number) {
    const clamped = Math.max(0, Math.min(1, value));

    return paddingTop + (1 - clamped) * chartHeight;
  }

  function xForIndex(index: number) {
    if (chartObservations.length === 1) {
      return paddingLeft + chartWidth / 2;
    }

    return paddingLeft + (index / (chartObservations.length - 1)) * chartWidth;
  }

  const points = values
    .map((value, index) => `${xForIndex(index)},${yForValue(value)}`)
    .join(" ");

  return (
    <div className="ndvi-chart">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="NDVI trend"
      >
        <line
          className="ndvi-grid-line"
          x1={paddingLeft}
          x2={width - paddingRight}
          y1={yForValue(0.8)}
          y2={yForValue(0.8)}
        />

        <line
          className="ndvi-grid-line"
          x1={paddingLeft}
          x2={width - paddingRight}
          y1={yForValue(0.4)}
          y2={yForValue(0.4)}
        />

        {chartObservations.length > 1 && (
          <polyline className="ndvi-line" points={points} fill="none" />
        )}

        {chartObservations.map((observation, index) => {
          const x = xForIndex(index);

          const y = yForValue(observation.ndvi_mean ?? 0);

          return (
            <g key={observation.id}>
              <circle className="ndvi-point" cx={x} cy={y} r="4" />

              <text
                className="ndvi-date"
                x={x}
                y={height - 8}
                textAnchor="middle"
              >
                {formatDate(observation.observed_on)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
