import type {
  SatelliteAnomalyFeature,
  SatelliteAnomalyFeatureCollection,
} from "../../types/api";
import { AnomalyPanel } from "./AnomalyPanel";
import {
  METRIC_CONFIG,
  METRIC_GROUPS,
  formatMetricValue,
  formatObservationDate,
  getMetricConfig,
  getMetricFromObservation,
  getObservationsForMetric,
  type SatelliteMetricType,
  type SatelliteObservationWithMetrics,
} from "./satellite";

type Props = {
  observations: SatelliteObservationWithMetrics[];
  selectedObservationId: string | null;
  selectedMetricType: SatelliteMetricType;
  metricEnabled: boolean;
  metricOpacity: number;
  satelliteLoading: boolean;
  satelliteError: string | null;
  anomalyData: SatelliteAnomalyFeatureCollection;
  anomalyLoading: boolean;
  anomalyError: string | null;
  selectedAnomaly: SatelliteAnomalyFeature | null;
  onSelectObservation: (observationId: string) => void;
  onSelectMetricType: (metricType: SatelliteMetricType) => void;
  onMetricEnabledChange: (enabled: boolean) => void;
  onMetricOpacityChange: (opacity: number) => void;
  onZoomToAnomaly: (feature: SatelliteAnomalyFeature) => void;
};

export function SatelliteAnalysisPanel({
  observations,
  selectedObservationId,
  selectedMetricType,
  metricEnabled,
  metricOpacity,
  satelliteLoading,
  satelliteError,
  anomalyData,
  anomalyLoading,
  anomalyError,
  selectedAnomaly,
  onSelectObservation,
  onSelectMetricType,
  onMetricEnabledChange,
  onMetricOpacityChange,
  onZoomToAnomaly,
}: Props) {
  const metricObservations = getObservationsForMetric(
    observations,
    selectedMetricType,
  );

  const selectedObservation =
    metricObservations.find(
      (observation) => observation.id === selectedObservationId,
    ) ?? null;

  const selectedMetric = selectedObservation
    ? getMetricFromObservation(selectedObservation, selectedMetricType)
    : null;

  const metricConfig = getMetricConfig(selectedMetricType);

  const displayMidpoint =
    (metricConfig.displayMin + metricConfig.displayMax) / 2;

  return (
    <div className="ndvi-map-panel">
      <div className="ndvi-map-panel-header">
        <div>
          <span className="ndvi-map-eyebrow">FIELD ANALYSIS</span>
          <strong>Satellite layer</strong>
        </div>

        {selectedMetric?.output_resolution_m != null && (
          <span className="ndvi-resolution-badge">
            {selectedMetric.output_resolution_m.toFixed(0)}m
          </span>
        )}
      </div>

      <div className="ndvi-layer-switch">
        <button
          type="button"
          className={!metricEnabled ? "active" : ""}
          onClick={() => onMetricEnabledChange(false)}
        >
          Normal
        </button>

        <button
          type="button"
          className={metricEnabled ? "active" : ""}
          disabled={satelliteLoading || !selectedMetric}
          onClick={() => onMetricEnabledChange(true)}
        >
          Satellite
        </button>
      </div>

      {satelliteLoading && (
        <p className="ndvi-map-message">Loading satellite data…</p>
      )}

      {satelliteError && (
        <p className="ndvi-map-message error">{satelliteError}</p>
      )}

      {!satelliteLoading && !satelliteError && observations.length === 0 && (
        <p className="ndvi-map-message">
          No processed satellite observations are available for this field.
        </p>
      )}

      <label className="ndvi-map-field">
        <span>Metric</span>
        <select
          value={selectedMetricType}
          onChange={(event) =>
            onSelectMetricType(event.target.value as SatelliteMetricType)
          }
        >
          {METRIC_GROUPS.map((group) => (
            <optgroup key={group.label} label={group.label}>
              {group.metrics.map((metricType) => (
                <option key={metricType} value={metricType}>
                  {METRIC_CONFIG[metricType].label}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </label>

      <p className="anomaly-hint">{metricConfig.description}</p>

      {!satelliteLoading &&
        !satelliteError &&
        observations.length > 0 &&
        metricObservations.length === 0 && (
          <p className="ndvi-map-message">
            No {metricConfig.label} raster is available for this field.
          </p>
        )}

      {metricObservations.length > 0 && (
        <>
          <label className="ndvi-map-field">
            <span>Observation</span>
            <select
              value={selectedObservationId ?? ""}
              onChange={(event) => onSelectObservation(event.target.value)}
            >
              {metricObservations.map((observation) => {
                const metric = getMetricFromObservation(
                  observation,
                  selectedMetricType,
                );

                return (
                  <option key={observation.id} value={observation.id}>
                    {formatObservationDate(observation.observed_on)}
                    {metric?.valid_pixel_percent != null
                      ? ` · ${metric.valid_pixel_percent.toFixed(0)}% valid`
                      : ""}
                  </option>
                );
              })}
            </select>
          </label>

          {metricEnabled && selectedMetric && (
            <>
              <div className="ndvi-opacity-row">
                <span>Opacity</span>
                <strong>{Math.round(metricOpacity * 100)}%</strong>
              </div>

              <input
                className="ndvi-opacity-slider"
                type="range"
                min="0.2"
                max="1"
                step="0.05"
                value={metricOpacity}
                onChange={(event) =>
                  onMetricOpacityChange(Number(event.target.value))
                }
              />

              <div className="ndvi-map-legend">
                <span>Low</span>
                <div
                  className="ndvi-map-gradient"
                  style={{ background: metricConfig.gradient }}
                />
                <span>High</span>
              </div>

              <div className="ndvi-map-scale">
                <span>{formatMetricValue(metricConfig.displayMin)}</span>
                <span>{formatMetricValue(displayMidpoint)}</span>
                <span>{formatMetricValue(metricConfig.displayMax)}</span>
              </div>

              <p className="anomaly-hint">
                Fixed visualization scale across dates. Colors are for
                comparison, not diagnostic thresholds.
              </p>
            </>
          )}

          {selectedMetric && (
            <div className="ndvi-map-metadata">
              <span>
                Mean <strong>{formatMetricValue(selectedMetric.mean)}</strong>
              </span>
              <span>
                Median{" "}
                <strong>{formatMetricValue(selectedMetric.median)}</strong>
              </span>
              <span>
                Range{" "}
                <strong>
                  {formatMetricValue(selectedMetric.min)} –{" "}
                  {formatMetricValue(selectedMetric.max)}
                </strong>
              </span>
              <span>
                Valid{" "}
                <strong>
                  {selectedMetric.valid_pixel_percent != null
                    ? `${selectedMetric.valid_pixel_percent.toFixed(0)}%`
                    : "—"}
                </strong>
              </span>
              <span>
                Native{" "}
                <strong>
                  {selectedMetric.native_resolution_m != null
                    ? `${selectedMetric.native_resolution_m.toFixed(0)}m`
                    : "—"}
                </strong>
              </span>
              <span>
                Display{" "}
                <strong>
                  {selectedMetric.output_resolution_m != null
                    ? `${selectedMetric.output_resolution_m.toFixed(0)}m`
                    : "—"}
                </strong>
              </span>
            </div>
          )}

          {metricEnabled && selectedMetricType === "ndvi" && (
            <AnomalyPanel
              anomalyCount={anomalyData.features.length}
              loading={anomalyLoading}
              error={anomalyError}
              selectedAnomaly={selectedAnomaly}
              onZoomToAnomaly={onZoomToAnomaly}
            />
          )}
        </>
      )}
    </div>
  );
}
