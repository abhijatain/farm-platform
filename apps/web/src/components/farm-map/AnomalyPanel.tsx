import type { SatelliteAnomalyFeature } from "../../types/api";

type Props = {
  anomalyCount: number;
  loading: boolean;
  error: string | null;
  selectedAnomaly: SatelliteAnomalyFeature | null;
  onZoomToAnomaly: (feature: SatelliteAnomalyFeature) => void;
};

export function AnomalyPanel({
  anomalyCount,
  loading,
  error,
  selectedAnomaly,
  onZoomToAnomaly,
}: Props) {
  return (
    <div className="anomaly-section">
      <div className="anomaly-section-header">
        <span>Potential stress zones</span>
        <strong>{anomalyCount}</strong>
      </div>

      {loading && <p className="anomaly-hint">Analysing detected zones…</p>}

      {error && <p className="ndvi-map-message error">{error}</p>}

      {!loading && !error && anomalyCount === 0 && (
        <p className="anomaly-empty">
          No significant low-NDVI zones were detected for this observation.
        </p>
      )}

      {!loading && anomalyCount > 0 && (
        <p className="anomaly-hint">
          Colored outlines mark areas performing below this field&apos;s normal
          NDVI baseline. Click a zone on the map for details.
        </p>
      )}

      {selectedAnomaly && (
        <div
          className={`anomaly-detail severity-${selectedAnomaly.properties.severity}`}
        >
          <div className="anomaly-detail-title">
            <div>
              <span>Zone {selectedAnomaly.properties.zone_index}</span>
              <strong>Potential stress</strong>
            </div>

            <span
              className={`anomaly-severity severity-${selectedAnomaly.properties.severity}`}
            >
              {selectedAnomaly.properties.severity}
            </span>
          </div>

          <div className="anomaly-stats">
            <div>
              <span>Area</span>
              <strong>{selectedAnomaly.properties.area_acres.toFixed(2)} ac</strong>
            </div>

            <div>
              <span>Zone NDVI</span>
              <strong>
                {selectedAnomaly.properties.zone_mean_value.toFixed(2)}
              </strong>
            </div>

            <div>
              <span>Field median</span>
              <strong>
                {selectedAnomaly.properties.field_median_value.toFixed(2)}
              </strong>
            </div>

            <div>
              <span>Difference</span>
              <strong>
                {selectedAnomaly.properties.percent_difference != null
                  ? `${selectedAnomaly.properties.percent_difference.toFixed(0)}%`
                  : "—"}
              </strong>
            </div>

            <div>
              <span>Pixels</span>
              <strong>{selectedAnomaly.properties.pixel_count}</strong>
            </div>

            <div>
              <span>Lowest NDVI</span>
              <strong>
                {selectedAnomaly.properties.zone_min_value.toFixed(2)}
              </strong>
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
