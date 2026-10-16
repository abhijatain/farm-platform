import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  ArrowRight,
} from "lucide-react";

import {
  getSatelliteChange,
} from "../lib/api";
import { apiRequest } from "../lib/api-client";
import { usePrivateRaster } from "../lib/privateRaster";

import {
  METRIC_OPTIONS,
  formatMetricValue,
} from "./farm-map/satellite";

import type {
  CropCycle,
  FieldSatelliteChange,
  SatelliteChangeMode,
  SatelliteMetricType,
  SatellitePixelChangeSummary,
} from "../types/api";


type Props = {
  fieldId: string;
  cropCycle: CropCycle | null;
};


const MODE_OPTIONS: Array<{
  value: SatelliteChangeMode;
  label: string;
}> = [
  {
    value:
      "previous",
    label:
      "Previous usable observation",
  },
  {
    value:
      "days_7",
    label:
      "Around 7 days earlier",
  },
  {
    value:
      "days_14",
    label:
      "Around 14 days earlier",
  },
  {
    value:
      "days_30",
    label:
      "Around 30 days earlier",
  },
  {
    value:
      "crop_start",
    label:
      "Crop start",
  },
  {
    value:
      "custom",
    label:
      "Custom date",
  },
];


function formatDate(
  value: string,
) {
  return new Date(
    `${value}T00:00:00`,
  ).toLocaleDateString(
    "en-IN",
    {
      day:
        "2-digit",
      month:
        "short",
      year:
        "numeric",
    },
  );
}


function signedValue(
  value:
    number
    | null
    | undefined,
  digits = 3,
) {
  if (
    value == null
    || !Number.isFinite(
      value
    )
  ) {
    return "—";
  }

  return (
    (value > 0
      ? "+"
      : "")
    + value.toFixed(
      digits,
    )
  );
}


function sourceLabel(
  source: string,
) {
  switch (
    source
  ) {
    case "sentinel-1-rtc":
      return "Sentinel-1 radar";

    case "landsat-c2-l2":
      return "Landsat thermal";

    case "sentinel-2":
    default:
      return "Sentinel-2";
  }
}


function isRadarMetric(
  metricType:
    SatelliteMetricType,
) {
  return metricType.startsWith(
    "sar_",
  );
}


function radarGeometryLabel(
  observation:
    FieldSatelliteChange[
      "before"
    ],
) {
  if (
    !observation
    || !observation
      .source
      .startsWith(
        "sentinel-1",
      )
  ) {
    return null;
  }

  const parts = [];

  if (
    observation
      .orbit_state
  ) {
    parts.push(
      observation
        .orbit_state
        .charAt(
          0,
        )
        .toUpperCase()
      + observation
        .orbit_state
        .slice(
          1,
        )
        .toLowerCase(),
    );
  }

  if (
    observation
      .relative_orbit
    != null
  ) {
    parts.push(
      `relative orbit ${observation.relative_orbit}`,
    );
  }

  if (
    observation
      .platform
  ) {
    parts.push(
      observation
        .platform,
    );
  }

  return (
    parts.join(
      " · ",
    )
    || null
  );
}


function changeParams(fieldId: string, change: FieldSatelliteChange, metricType: SatelliteMetricType) {
  if (!change.before || !change.after) return null;
  const prefix = `/fields/${encodeURIComponent(fieldId)}`;
  const params = new URLSearchParams({
    before_id: change.before.observation_id,
    after_id: change.after.observation_id,
    metric_type: metricType,
  });
  return { prefix, params };
}
function buildChangeSummaryUrl(fieldId: string, change: FieldSatelliteChange, metricType: SatelliteMetricType) {
  const parts = changeParams(fieldId, change, metricType);
  if (!parts) return null;
  parts.params.set("threshold", String(change.pixel_change_threshold));
  return `${parts.prefix}/satellite-change-pixels?${parts.params.toString()}`;
}
function buildChangePreviewUrl(fieldId: string, change: FieldSatelliteChange, metricType: SatelliteMetricType) {
  const parts = changeParams(fieldId, change, metricType);
  if (!parts) return null;
  parts.params.set("max_abs", String(change.pixel_change_display_max));
  return `${parts.prefix}/satellite-change-preview?${parts.params.toString()}`;
}

export default function SatelliteChangePanel({
  fieldId,
  cropCycle,
}: Props) {
  const [
    metricType,
    setMetricType,
  ] = useState<
    SatelliteMetricType
  >(
    "ndvi",
  );

  const [
    mode,
    setMode,
  ] = useState<
    SatelliteChangeMode
  >(
    "previous",
  );

  const [
    fromDate,
    setFromDate,
  ] = useState(
    "",
  );

  const [
    toDate,
    setToDate,
  ] = useState(
    "",
  );

  const [
    change,
    setChange,
  ] = useState<
    FieldSatelliteChange
    | null
  >(
    null,
  );

  const [
    pixels,
    setPixels,
  ] = useState<
    SatellitePixelChangeSummary
    | null
  >(
    null,
  );

  const [
    loading,
    setLoading,
  ] = useState(
    false,
  );

  const [
    error,
    setError,
  ] = useState<
    string | null
  >(
    null,
  );

  const [
    pixelError,
    setPixelError,
  ] = useState<
    string | null
  >(
    null,
  );


  useEffect(
    () => {
      if (
        mode === "custom"
        && !fromDate
      ) {
        setChange(
          null,
        );

        setPixels(
          null,
        );

        return;
      }

      let cancelled =
        false;

      const controller =
        new AbortController();

      setLoading(
        true,
      );

      setError(
        null,
      );

      setPixelError(
        null,
      );

      void getSatelliteChange(
        fieldId,
        metricType,
        mode,
        {
          toDate:
            toDate
            || null,
          fromDate:
            mode
            === "custom"
              ? fromDate
              : null,
          cropCycleId:
            cropCycle?.id
            ?? null,
        },
      )
        .then(
          async (
            result,
          ) => {
            if (cancelled) {
              return;
            }

            setChange(
              result,
            );

            setPixels(
              null,
            );

            if (
              result.status
              !== "complete"
            ) {
              return;
            }

            const summaryUrl =
              buildChangeSummaryUrl(fieldId, result, metricType);

            if (!summaryUrl) {
              return;
            }

            try {
              const summary = await apiRequest<SatellitePixelChangeSummary>(
                summaryUrl, { signal: controller.signal },
              );

              if (!cancelled) {
                setPixels(
                  summary,
                );
              }

            } catch (
              requestError
            ) {
              if (
                cancelled
                || controller
                  .signal
                  .aborted
              ) {
                return;
              }

              setPixelError(
                requestError
                  instanceof Error
                  ? requestError.message
                  : "Unable to calculate pixel change.",
              );
            }
          },
        )
        .catch(
          (
            requestError:
              unknown,
          ) => {
            if (cancelled) {
              return;
            }

            setChange(
              null,
            );

            setPixels(
              null,
            );

            setError(
              requestError
                instanceof Error
                ? requestError.message
                : "Unable to load change analysis.",
            );
          },
        )
        .finally(
          () => {
            if (!cancelled) {
              setLoading(
                false,
              );
            }
          },
        );

      return () => {
        cancelled =
          true;

        controller.abort();
      };
    },
    [
      fieldId,
      metricType,
      mode,
      fromDate,
      toDate,
      cropCycle?.id,
    ],
  );


  const previewUrl =
    useMemo(
      () =>
        change
          ? buildChangePreviewUrl(fieldId, change, metricType)
          : null,
      [
        change, fieldId, metricType,
      ],
    );


  const { url: previewBlobUrl, loading: previewLoading, error: previewError } = usePrivateRaster(previewUrl);


  return (
    <section className="satellite-change-panel">
      <div className="satellite-change-heading">
        <div>
          <span className="workspace-eyebrow">
            CHANGE ANALYSIS
          </span>

          <h3>
            Date-to-date change
          </h3>

          <p>
            Compare actual usable acquisitions. Requested day ranges resolve
            to the nearest usable satellite observation.
          </p>
        </div>

        {change?.scalar
          .days_between
          != null && (
          <span className="satellite-change-days">
            {
              change.scalar
                .days_between
            }
            {" days between acquisitions"}
          </span>
        )}
      </div>

      <div className="satellite-change-controls">
        <label>
          <span>
            Metric
          </span>

          <select
            value={
              metricType
            }
            onChange={(event) => {
              setMetricType(
                event.currentTarget.value as SatelliteMetricType,
              );
            }}
          >
            {METRIC_OPTIONS.map(
              (
                metric,
              ) => (
                <option
                  key={
                    metric.value
                  }
                  value={
                    metric.value
                  }
                >
                  {metric.label}
                </option>
              ),
            )}
          </select>
        </label>

        <label>
          <span>
            Compare with
          </span>

          <select
            value={
              mode
            }
            onChange={(event) => {
              setMode(
                event.currentTarget.value as SatelliteChangeMode,
              );
            }}
          >
            {MODE_OPTIONS.map(
              (
                option,
              ) => (
                <option
                  key={
                    option.value
                  }
                  value={
                    option.value
                  }
                  disabled={
                    option.value
                    === "crop_start"
                    && !cropCycle
                  }
                >
                  {option.label}
                </option>
              ),
            )}
          </select>
        </label>

        {mode
          === "custom" && (
          <label>
            <span>
              Baseline date
            </span>

            <input
              type="date"
              value={
                fromDate
              }
              onChange={(
                event,
              ) =>
                setFromDate(
                  event.currentTarget
                    .value,
                )
              }
            />
          </label>
        )}

        <label>
          <span>
            Current date
          </span>

          <input
            type="date"
            value={
              toDate
            }
            onChange={(
              event,
            ) =>
              setToDate(
                event.currentTarget
                  .value,
              )
            }
          />

          {toDate && (
            <button
              type="button"
              onClick={
                () =>
                  setToDate(
                    "",
                  )
              }
            >
              Latest
            </button>
          )}
        </label>
      </div>

      {loading && (
        <div className="satellite-change-state">
          Calculating comparison…
        </div>
      )}

      {!loading
        && error && (
        <div className="satellite-change-state error">
          {error}
        </div>
      )}

      {!loading
        && !error
        && mode === "custom"
        && !fromDate && (
        <div className="satellite-change-state">
          Choose a baseline date for the custom comparison.
        </div>
      )}

      {!loading
        && !error
        && change
        && change.status
          !== "complete" && (
        <div className="satellite-change-state">
          {change.status === "missing_current"
            ? "No usable current observation is available for this metric."
            : "No usable baseline observation is close enough to the requested comparison date."}
        </div>
      )}

      {!loading
        && !error
        && change?.status
          === "complete"
        && change.before
        && change.after && (
        <>
          <div className="satellite-change-pair">
            <div className="satellite-change-observation">
              <span>
                Baseline
              </span>

              <strong>
                {formatDate(
                  change.before
                    .observed_on,
                )}
              </strong>

              <small>
                {sourceLabel(
                  change.before
                    .source,
                )}
              </small>

              {radarGeometryLabel(
                change.before,
              ) && (
                <small className="satellite-change-radar-geometry">
                  {radarGeometryLabel(
                    change.before,
                  )}
                </small>
              )}

              <b>
                {formatMetricValue(
                  change.before
                    .median,
                  metricType
                    === "lst_c"
                    ? 1
                    : 3,
                )}
              </b>
            </div>

            <ArrowRight
              size={20}
            />

            <div className="satellite-change-observation">
              <span>
                Current
              </span>

              <strong>
                {formatDate(
                  change.after
                    .observed_on,
                )}
              </strong>

              <small>
                {sourceLabel(
                  change.after
                    .source,
                )}
              </small>

              {radarGeometryLabel(
                change.after,
              ) && (
                <small className="satellite-change-radar-geometry">
                  {radarGeometryLabel(
                    change.after,
                  )}
                </small>
              )}

              <b>
                {formatMetricValue(
                  change.after
                    .median,
                  metricType
                    === "lst_c"
                    ? 1
                    : 3,
                )}
              </b>
            </div>

            <div className="satellite-change-delta">
              <span>
                Median change
              </span>

              <strong>
                {signedValue(
                  change.scalar
                    .median_change,
                  metricType
                    === "lst_c"
                    ? 1
                    : 3,
                )}
              </strong>

              {change.scalar
                .median_percent_change
                != null && (
                <small>
                  {signedValue(
                    change.scalar
                      .median_percent_change,
                    1,
                  )}
                  {"%"}
                </small>
              )}
            </div>
          </div>

          <div className="satellite-change-spatial">
            <div className="satellite-change-raster-card">
              <div>
                <strong>
                  Pixel-by-pixel change
                </strong>

                <span>
                  Red = numerical decrease · Green = numerical increase
                </span>
              </div>

              {previewBlobUrl ? (
                <img src={previewBlobUrl} alt="Pixel-by-pixel satellite metric change" />
              ) : previewLoading ? (
                <p className="satellite-change-state">Loading private change imagery…</p>
              ) : previewError ? (
                <p className="satellite-change-state" role="status">{previewError}</p>
              ) : null}

              <div className="satellite-change-gradient">
                <span>
                  -
                  {
                    change
                      .pixel_change_display_max
                  }
                </span>

                <div />

                <span>
                  +
                  {
                    change
                      .pixel_change_display_max
                  }
                </span>
              </div>
            </div>

            <div className="satellite-change-stats">
              {pixels
                ? (
                  <>
                    <div>
                      <span>
                        Increased
                      </span>

                      <strong>
                        {pixels
                          .increased_percent
                          .toFixed(
                            1,
                          )}
                        {"%"}
                      </strong>

                      <small>
                        {pixels
                          .increased_area_acres
                          .toFixed(
                            2,
                          )}
                        {" ac"}
                      </small>
                    </div>

                    <div>
                      <span>
                        Decreased
                      </span>

                      <strong>
                        {pixels
                          .decreased_percent
                          .toFixed(
                            1,
                          )}
                        {"%"}
                      </strong>

                      <small>
                        {pixels
                          .decreased_area_acres
                          .toFixed(
                            2,
                          )}
                        {" ac"}
                      </small>
                    </div>

                    <div>
                      <span>
                        Stable
                      </span>

                      <strong>
                        {pixels
                          .stable_percent
                          .toFixed(
                            1,
                          )}
                        {"%"}
                      </strong>

                      <small>
                        {pixels
                          .stable_area_acres
                          .toFixed(
                            2,
                          )}
                        {" ac"}
                      </small>
                    </div>
                  </>
                )
                : (
                  <div className="satellite-change-pixel-loading">
                    {pixelError
                      ?? "Calculating spatial pixel areas…"}
                  </div>
                )}
            </div>
          </div>

          {isRadarMetric(
            metricType,
          )
            ? (
              <div className="satellite-change-radar-note">
                Radar anomaly classification is intentionally not enabled yet.
                The comparison above uses the same Sentinel-1 orbit geometry
                and reports numerical pixel change only.
              </div>
            )
            : (
              <div className="satellite-change-anomalies">
                <div>
                  <span>
                    Persistent anomaly
                  </span>

                  <strong>
                    {change.anomalies
                      .persistent_area_acres
                      != null
                      ? `${change.anomalies.persistent_area_acres.toFixed(2)} ac`
                      : "—"}
                  </strong>
                </div>

                <div>
                  <span>
                    Resolved anomaly
                  </span>

                  <strong>
                    {change.anomalies
                      .resolved_area_acres
                      != null
                      ? `${change.anomalies.resolved_area_acres.toFixed(2)} ac`
                      : "—"}
                  </strong>
                </div>

                <div>
                  <span>
                    New anomaly
                  </span>

                  <strong>
                    {change.anomalies
                      .new_area_acres
                      != null
                      ? `${change.anomalies.new_area_acres.toFixed(2)} ac`
                      : "—"}
                  </strong>
                </div>
              </div>
            )}

          <p className="satellite-change-note">
            Increased/decreased describe numeric raster change only. They are
            not automatically labelled healthy/unhealthy because crop stage,
            weather and metric meaning can change the agronomic interpretation.
          </p>
        </>
      )}
    </section>
  );
}
