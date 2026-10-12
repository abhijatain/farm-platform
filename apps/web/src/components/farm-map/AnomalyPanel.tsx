import type { SatelliteAnomalyFeature } from "../../types/api";
import {
  formatMetricValue,
  getMetricAnomalyDescription,
  getMetricConfig,
  type SatelliteMetricType,
} from "./satellite";

type Props = {
  metricType: SatelliteMetricType;
  anomalyCount: number;
  loading: boolean;
  error: string | null;
  selectedAnomaly: SatelliteAnomalyFeature | null;
  onZoomToAnomaly: (feature: SatelliteAnomalyFeature) => void;
};

function formatDirection(anomalyType: string) {
  if (anomalyType === "above_field_baseline") {
    return "Above field baseline";
  }

  if (anomalyType === "below_field_baseline") {
    return "Below field baseline";
  }

  return "Relative field anomaly";
}

export function AnomalyPanel({
  metricType,
  anomalyCount,
  loading,
  error,
  selectedAnomaly,
  onZoomToAnomaly,
}: Props) {
  const metricConfig = getMetricConfig(metricType);
  const anomalyDescription = getMetricAnomalyDescription(metricType);

  const selectedProperties = selectedAnomaly?.properties ?? null;

  const selectedDirection = selectedProperties
    ? formatDirection(selectedProperties.anomaly_type)
    : null;

  const selectedExtremeLabel =
    selectedProperties?.anomaly_type === "above_field_baseline"
      ? "Zone maximum"
      : "Zone minimum";

  const selectedExtremeValue =
    selectedProperties?.anomaly_type === "above_field_baseline"
      ? selectedProperties.zone_max_value
      : selectedProperties?.zone_min_value;

  return (
    <div className="anomaly-section">
      <div className="anomaly-section-header">
        <span>Relative anomaly zones</span>
        <strong>{anomalyCount}</strong>
      </div>

      {loading && <p className="anomaly-hint">Analysing relative zones…</p>}

      {error && <p className="ndvi-map-message error">{error}</p>}

      {!loading && !error && anomalyCount === 0 && (
        <p className="anomaly-empty">
          No significant relative {metricConfig.label} anomaly zones were
          detected for this observation.
        </p>
      )}

      {!loading && !error && anomalyCount > 0 && (
        <p className="anomaly-hint">
          {anomalyDescription} Colored outlines show the detected zones. Click a
          zone on the map for details.
        </p>
      )}

      {selectedAnomaly && selectedProperties && (
        <div
          className={`anomaly-detail severity-${selectedProperties.severity}`}
        >
          <div className="anomaly-detail-title">
            <div>
              <span>Zone {selectedProperties.zone_index}</span>
              <strong>
                {metricConfig.label} · {selectedDirection}
              </strong>
            </div>

            <span
              className={`anomaly-severity severity-${selectedProperties.severity}`}
            >
              {selectedProperties.severity}
            </span>
          </div>

          <div className="anomaly-stats">
            <div>
              <span>Area</span>
              <strong>{selectedProperties.area_acres.toFixed(2)} ac</strong>
            </div>

            <div>
              <span>Zone mean</span>
              <strong>
                {formatMetricValue(selectedProperties.zone_mean_value)}
              </strong>
            </div>

            <div>
              <span>Field median</span>
              <strong>
                {formatMetricValue(selectedProperties.field_median_value)}
              </strong>
            </div>

            <div>
              <span>Difference</span>
              <strong>
                {formatMetricValue(selectedProperties.difference_from_field)}
                {selectedProperties.percent_difference != null
                  ? ` (${selectedProperties.percent_difference > 0 ? "+" : ""}${selectedProperties.percent_difference.toFixed(0)}%)`
                  : ""}
              </strong>
            </div>

            <div>
              <span>{selectedExtremeLabel}</span>
              <strong>{formatMetricValue(selectedExtremeValue ?? null)}</strong>
            </div>

            <div>
              <span>Pixels</span>
              <strong>{selectedProperties.pixel_count}</strong>
            </div>
          </div>

          <button
            type="button"
            className="anomaly-zoom-button"
            onClick={() => onZoomToAnomaly(selectedAnomaly)}
          >
            Zoom to area
          </button>
        </div>
      )}
    </div>
  );
}
