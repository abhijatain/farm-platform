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


const TILER_URL =
  import.meta.env
    .VITE_TILER_URL;


if (!TILER_URL) {
  throw new Error(
    "VITE_TILER_URL is missing.",
  );
}


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


function buildChangeSummaryUrl(
  change: FieldSatelliteChange,
) {
  if (
    !change.before
    || !change.after
  ) {
    return null;
  }

  const params =
    new URLSearchParams({
      before:
        change.before
          .raster_uri,
      after:
        change.after
          .raster_uri,
      threshold:
        String(
          change
            .pixel_change_threshold,
        ),
    });

  return (
    `${TILER_URL}/change/summary?`
    + params.toString()
  );
}


function buildChangePreviewUrl(
  change: FieldSatelliteChange,
) {
  if (
    !change.before
    || !change.after
  ) {
    return null;
  }

  const params =
    new URLSearchParams({
      before:
        change.before
          .raster_uri,
      after:
        change.after
          .raster_uri,
      max_abs:
        String(
          change
            .pixel_change_display_max,
        ),
    });

  return (
    `${TILER_URL}/change/preview.png?`
    + params.toString()
  );
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
              buildChangeSummaryUrl(
                result,
              );

            if (!summaryUrl) {
              return;
            }

            try {
              const response =
                await fetch(
                  summaryUrl,
                  {
                    signal:
                      controller.signal,
                  },
                );

              if (
                !response.ok
              ) {
                throw new Error(
                  "Unable to calculate pixel change."
                );
              }

              const summary = (
                await response.json()
              ) as SatellitePixelChangeSummary;

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
          ? buildChangePreviewUrl(
              change,
            )
          : null,
      [
        change,
      ],
    );


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

              {previewUrl && (
                <img
                  src={
                    previewUrl
                  }
                  alt="Pixel-by-pixel satellite metric change"
                />
              )}

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
