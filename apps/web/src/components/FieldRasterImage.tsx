import { useMemo } from "react";
import { usePrivateRaster } from "../lib/privateRaster";

type Props = {
  fieldId: string;
  observationId: string;
  metricType: string;
  points: string;
  alt: string;
};

/** HTML img + CSS polygon clipping avoid iOS Safari's SVG external-image
 * fetch/clipPath differences, while keeping the real field boundary overlay.
 */
export default function FieldRasterImage({
  fieldId, observationId, metricType, points, alt,
}: Props) {
  const path = `/fields/${encodeURIComponent(fieldId)}/satellite-observations/${encodeURIComponent(observationId)}/metric-preview/${encodeURIComponent(metricType)}`;
  const { url, loading, error } = usePrivateRaster(path);
  const clip = useMemo(() => {
    const polygon = points.trim().split(/\s+/)
      .map((point) => point.split(",").map(Number))
      .filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y))
      .map(([x, y]) => `${(x / 420) * 100}% ${(y / 230) * 100}%`);
    return polygon.length > 2 ? `polygon(${polygon.join(", ")})` : undefined;
  }, [points]);
  return (
    <div className="field-raster-image" role="img" aria-label={alt}>
      {url && <img src={url} alt="" style={{ clipPath: clip }} />}
      {(loading || error) && !url && (
        <span className="field-raster-status" role="status">
          {loading ? "Loading private satellite image…" : error}
        </span>
      )}
      <svg viewBox="0 0 420 230" aria-hidden="true">
        <polygon className="metric-preview-boundary" points={points} />
      </svg>
    </div>
  );
}
