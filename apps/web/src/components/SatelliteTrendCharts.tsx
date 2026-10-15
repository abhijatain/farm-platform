import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getSatelliteTrends,
} from "../lib/api";

import {
  METRIC_CONFIG,
} from "./farm-map/satellite";

import type {
  CropCycle,
  FieldSatelliteTrends,
  SatelliteMetricType,
  SatelliteTrendActivity,
  SatelliteTrendPoint,
} from "../types/api";


type Props = {
  fieldId: string;
  cropCycle: CropCycle | null;
};


type ChartPoint = {
  date: string;
  value: number;
  source: string;
};


type ChartSeries = {
  key: string;
  label: string;
  className: string;
  points: ChartPoint[];
};


type TrendChartProps = {
  title: string;
  subtitle: string;

  series: ChartSeries[];
  activities: SatelliteTrendActivity[];

  startDate: string;
  endDate: string;

  valueLabel: string;

  fixedMin?: number;
  fixedMax?: number;

  emptyMessage: string;
};


const OPTICAL_METRICS: SatelliteMetricType[] = [
  "ndvi",
  "ndre",
  "ndmi",
];


const CONTEXT_METRICS: SatelliteMetricType[] = [
  "ndvi",
  "ndre",
  "ndmi",
  "sar_rvi",
  "lst_c",
];


function dateMs(
  value: string,
) {
  return new Date(
    `${value.slice(
      0,
      10,
    )}T00:00:00Z`,
  ).getTime();
}


function formatShortDate(
  value: string,
) {
  return new Date(
    `${value.slice(
      0,
      10,
    )}T00:00:00Z`,
  ).toLocaleDateString(
    "en-IN",
    {
      day:
        "2-digit",
      month:
        "short",
    },
  );
}


function formatLongDate(
  value: string,
) {
  return new Date(
    `${value.slice(
      0,
      10,
    )}T00:00:00Z`,
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


function formatActivityName(
  value: string,
) {
  return value
    .split(
      "_",
    )
    .filter(
      Boolean,
    )
    .map(
      (
        part,
      ) =>
        part.charAt(
          0,
        ).toUpperCase()
        + part.slice(
          1,
        ),
    )
    .join(
      " ",
    );
}


function sourceLabel(
  source: string,
) {
  switch (
    source
  ) {
    case "sentinel-1-rtc":
      return "Sentinel-1";

    case "landsat-c2-l2":
      return "Landsat";

    case "sentinel-2":
    default:
      return "Sentinel-2";
  }
}


function metricLabel(
  metricType:
    SatelliteMetricType,
) {
  return (
    METRIC_CONFIG[
      metricType
    ]?.label
    ?? metricType.toUpperCase()
  );
}


function linePath(
  points: Array<{
    x: number;
    y: number;
  }>,
) {
  return points
    .map(
      (
        point,
        index,
      ) =>
        `${index === 0 ? "M" : "L"} ${point.x.toFixed(
          2,
        )} ${point.y.toFixed(
          2,
        )}`,
    )
    .join(
      " ",
    );
}


function valueRange(
  series: ChartSeries[],
  fixedMin:
    number
    | undefined,
  fixedMax:
    number
    | undefined,
) {
  const values =
    series.flatMap(
      (
        item,
      ) =>
        item.points.map(
          (
            point,
          ) =>
            point.value,
        ),
    );

  if (
    fixedMin != null
    && fixedMax != null
  ) {
    return [
      fixedMin,
      fixedMax,
    ] as const;
  }

  if (
    values.length === 0
  ) {
    return [
      fixedMin
      ?? 0,
      fixedMax
      ?? 1,
    ] as const;
  }

  let minimum =
    fixedMin
    ?? Math.min(
      ...values,
    );

  let maximum =
    fixedMax
    ?? Math.max(
      ...values,
    );

  if (
    minimum === maximum
  ) {
    const padding =
      Math.max(
        Math.abs(
          minimum,
        )
        * 0.1,
        0.1,
      );

    minimum -= padding;
    maximum += padding;
  }

  const padding =
    (
      maximum
      - minimum
    )
    * 0.08;

  if (
    fixedMin == null
  ) {
    minimum -= padding;
  }

  if (
    fixedMax == null
  ) {
    maximum += padding;
  }

  return [
    minimum,
    maximum,
  ] as const;
}


function TrendChart({
  title,
  subtitle,
  series,
  activities,
  startDate,
  endDate,
  valueLabel,
  fixedMin,
  fixedMax,
  emptyMessage,
}: TrendChartProps) {
  const width =
    940;

  const height =
    280;

  const margins = {
    top:
      22,
    right:
      22,
    bottom:
      42,
    left:
      58,
  };

  const innerWidth =
    width
    - margins.left
    - margins.right;

  const innerHeight =
    height
    - margins.top
    - margins.bottom;

  const start =
    dateMs(
      startDate,
    );

  const rawEnd =
    dateMs(
      endDate,
    );

  const end =
    rawEnd > start
      ? rawEnd
      : start
        + 86_400_000;

  const [
    minValue,
    maxValue,
  ] = valueRange(
    series,
    fixedMin,
    fixedMax,
  );

  const hasPoints =
    series.some(
      (
        item,
      ) =>
        item.points.length
        > 0,
    );

  function xForDate(
    value: string,
  ) {
    const timestamp =
      dateMs(
        value,
      );

    return (
      margins.left
      + (
        timestamp
        - start
      )
      / (
        end
        - start
      )
      * innerWidth
    );
  }

  function yForValue(
    value: number,
  ) {
    return (
      margins.top
      + (
        maxValue
        - value
      )
      / (
        maxValue
        - minValue
      )
      * innerHeight
    );
  }

  const horizontalTicks =
    Array.from(
      {
        length:
          5,
      },
      (
        _,
        index,
      ) => {
        const ratio =
          index
          / 4;

        return {
          value:
            maxValue
            - (
              maxValue
              - minValue
            )
            * ratio,

          y:
            margins.top
            + innerHeight
            * ratio,
        };
      },
    );

  const dateTicks =
    Array.from(
      {
        length:
          5,
      },
      (
        _,
        index,
      ) => {
        const ratio =
          index
          / 4;

        const timestamp =
          start
          + (
            end
            - start
          )
          * ratio;

        return {
          x:
            margins.left
            + innerWidth
            * ratio,

          date:
            new Date(
              timestamp,
            )
            .toISOString()
            .slice(
              0,
              10,
            ),
        };
      },
    );

  return (
    <article className="satellite-trend-chart-card">
      <div className="satellite-trend-chart-heading">
        <div>
          <h4>
            {title}
          </h4>

          <p>
            {subtitle}
          </p>
        </div>

        <span>
          {valueLabel}
        </span>
      </div>

      <div className="satellite-trend-legend">
        {series.map(
          (
            item,
          ) => (
            <span
              key={
                item.key
              }
              className={
                `satellite-trend-legend-item ${item.className}`
              }
            >
              <i />

              {item.label}
            </span>
          ),
        )}

        {activities.length > 0 && (
          <span className="satellite-trend-legend-item activity">
            <i />
            Farm activity
          </span>
        )}
      </div>

      {!hasPoints
        ? (
          <div className="satellite-trend-empty">
            {emptyMessage}
          </div>
        )
        : (
          <div className="satellite-trend-svg-wrap">
            <svg
              className="satellite-trend-svg"
              viewBox={
                `0 0 ${width} ${height}`
              }
              role="img"
              aria-label={
                `${title} time series`
              }
            >
              {horizontalTicks.map(
                (
                  tick,
                  index,
                ) => (
                  <g
                    key={
                      `y-${index}`
                    }
                  >
                    <line
                      className="satellite-trend-grid-line"
                      x1={
                        margins.left
                      }
                      x2={
                        width
                        - margins.right
                      }
                      y1={
                        tick.y
                      }
                      y2={
                        tick.y
                      }
                    />

                    <text
                      className="satellite-trend-axis-label"
                      x={
                        margins.left
                        - 9
                      }
                      y={
                        tick.y
                        + 4
                      }
                      textAnchor="end"
                    >
                      {Math.abs(
                        tick.value,
                      )
                        >= 10
                        ? tick.value.toFixed(
                            1,
                          )
                        : tick.value.toFixed(
                            2,
                          )}
                    </text>
                  </g>
                ),
              )}

              {dateTicks.map(
                (
                  tick,
                ) => (
                  <g
                    key={
                      tick.date
                    }
                  >
                    <line
                      className="satellite-trend-date-line"
                      x1={
                        tick.x
                      }
                      x2={
                        tick.x
                      }
                      y1={
                        margins.top
                      }
                      y2={
                        height
                        - margins.bottom
                      }
                    />

                    <text
                      className="satellite-trend-axis-label"
                      x={
                        tick.x
                      }
                      y={
                        height
                        - 15
                      }
                      textAnchor="middle"
                    >
                      {formatShortDate(
                        tick.date,
                      )}
                    </text>
                  </g>
                ),
              )}

              {activities.map(
                (
                  activity,
                ) => {
                  const activityDate =
                    activity.occurred_at
                      .slice(
                        0,
                        10,
                      );

                  const x =
                    xForDate(
                      activityDate,
                    );

                  if (
                    x
                    < margins.left
                    || x
                    > width
                      - margins.right
                  ) {
                    return null;
                  }

                  return (
                    <g
                      key={
                        activity.id
                      }
                      className="satellite-trend-activity-marker"
                    >
                      <line
                        x1={
                          x
                        }
                        x2={
                          x
                        }
                        y1={
                          margins.top
                        }
                        y2={
                          height
                          - margins.bottom
                        }
                      />

                      <path
                        d={
                          `M ${x - 5} ${margins.top} L ${x + 5} ${margins.top} L ${x} ${margins.top + 8} Z`
                        }
                      >
                        <title>
                          {formatActivityName(
                            activity.activity_type,
                          )}
                          {" · "}
                          {formatLongDate(
                            activityDate,
                          )}
                          {activity.notes
                            ? ` · ${activity.notes}`
                            : ""}
                        </title>
                      </path>
                    </g>
                  );
                },
              )}

              {series.map(
                (
                  item,
                ) => {
                  const plotted =
                    item.points
                      .filter(
                        (
                          point,
                        ) =>
                          Number.isFinite(
                            point.value,
                          ),
                      )
                      .map(
                        (
                          point,
                        ) => ({
                          ...point,

                          x:
                            xForDate(
                              point.date,
                            ),

                          y:
                            yForValue(
                              point.value,
                            ),
                        }),
                      );

                  return (
                    <g
                      key={
                        item.key
                      }
                      className={
                        `satellite-trend-series ${item.className}`
                      }
                    >
                      {plotted.length > 1 && (
                        <path
                          className="satellite-trend-series-line"
                          d={
                            linePath(
                              plotted,
                            )
                          }
                        />
                      )}

                      {plotted.map(
                        (
                          point,
                          index,
                        ) => (
                          <circle
                            key={
                              `${point.date}-${index}`
                            }
                            className="satellite-trend-point"
                            cx={
                              point.x
                            }
                            cy={
                              point.y
                            }
                            r="4"
                          >
                            <title>
                              {item.label}
                              {" · "}
                              {formatLongDate(
                                point.date,
                              )}
                              {" · "}
                              {point.value.toFixed(
                                Math.abs(
                                  point.value,
                                )
                                  >= 10
                                  ? 1
                                  : 3,
                              )}
                              {" · "}
                              {sourceLabel(
                                point.source,
                              )}
                            </title>
                          </circle>
                        ),
                      )}
                    </g>
                  );
                },
              )}

              <line
                className="satellite-trend-axis"
                x1={
                  margins.left
                }
                x2={
                  margins.left
                }
                y1={
                  margins.top
                }
                y2={
                  height
                  - margins.bottom
                }
              />

              <line
                className="satellite-trend-axis"
                x1={
                  margins.left
                }
                x2={
                  width
                  - margins.right
                }
                y1={
                  height
                  - margins.bottom
                }
                y2={
                  height
                  - margins.bottom
                }
              />
            </svg>
          </div>
        )}
    </article>
  );
}


function pointsForMetric(
  trends: FieldSatelliteTrends,
  metricType:
    SatelliteMetricType,
  selector:
    (
      point:
        SatelliteTrendPoint,
    ) =>
      number
      | null,
) {
  return trends.points
    .filter(
      (
        point,
      ) =>
        point.metric_type
        === metricType,
    )
    .map(
      (
        point,
      ) => ({
        date:
          point.observed_on,

        value:
          selector(
            point,
          ),

        source:
          point.source,
      }),
    )
    .filter(
      (
        point,
      ): point is ChartPoint =>
        point.value
        != null
        && Number.isFinite(
          point.value,
        ),
    );
}


export default function SatelliteTrendCharts({
  fieldId,
  cropCycle,
}: Props) {
  const [
    trends,
    setTrends,
  ] = useState<
    FieldSatelliteTrends
    | null
  >(
    null,
  );

  const [
    loading,
    setLoading,
  ] = useState(
    true,
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
    anomalyMetric,
    setAnomalyMetric,
  ] = useState<
    SatelliteMetricType
  >(
    "ndvi",
  );

  const [
    coverageMetric,
    setCoverageMetric,
  ] = useState<
    SatelliteMetricType
  >(
    "ndvi",
  );


  useEffect(
    () => {
      let cancelled =
        false;

      setLoading(
        true,
      );

      setError(
        null,
      );

      void getSatelliteTrends(
        fieldId,
        {
          cropCycleId:
            cropCycle?.id
            ?? null,
        },
      )
        .then(
          (
            result,
          ) => {
            if (
              !cancelled
            ) {
              setTrends(
                result,
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

            setTrends(
              null,
            );

            setError(
              requestError
                instanceof Error
                ? requestError.message
                : "Unable to load satellite trends.",
            );
          },
        )
        .finally(
          () => {
            if (
              !cancelled
            ) {
              setLoading(
                false,
              );
            }
          },
        );

      return () => {
        cancelled =
          true;
      };
    },
    [
      fieldId,
      cropCycle?.id,
    ],
  );


  const opticalSeries =
    useMemo(
      () => {
        if (!trends) {
          return [];
        }

        const classNames = [
          "ndvi",
          "ndre",
          "ndmi",
        ];

        return OPTICAL_METRICS.map(
          (
            metricType,
            index,
          ) => ({
            key:
              metricType,

            label:
              metricLabel(
                metricType,
              ),

            className:
              classNames[
                index
              ],

            points:
              pointsForMetric(
                trends,
                metricType,
                (
                  point,
                ) =>
                  point.median,
              ),
          }),
        );
      },
      [
        trends,
      ],
    );


  const radarSeries =
    useMemo(
      () => {
        if (!trends) {
          return [];
        }

        return [
          {
            key:
              "sar_rvi",

            label:
              "Radar RVI",

            className:
              "sar-rvi",

            points:
              pointsForMetric(
                trends,
                "sar_rvi",
                (
                  point,
                ) =>
                  point.median,
              ),
          },
        ];
      },
      [
        trends,
      ],
    );


  const thermalSeries =
    useMemo(
      () => {
        if (!trends) {
          return [];
        }

        return [
          {
            key:
              "lst_c",

            label:
              "LST °C",

            className:
              "lst",

            points:
              pointsForMetric(
                trends,
                "lst_c",
                (
                  point,
                ) =>
                  point.median,
              ),
          },
        ];
      },
      [
        trends,
      ],
    );


  const anomalySeries =
    useMemo(
      () => {
        if (!trends) {
          return [];
        }

        return [
          {
            key:
              `${anomalyMetric}-anomaly`,

            label:
              `${metricLabel(
                anomalyMetric,
              )} anomaly area`,

            className:
              "anomaly",

            points:
              pointsForMetric(
                trends,
                anomalyMetric,
                (
                  point,
                ) =>
                  point
                    .anomaly_area_acres,
              ),
          },
        ];
      },
      [
        trends,
        anomalyMetric,
      ],
    );


  const coverageSeries =
    useMemo(
      () => {
        if (!trends) {
          return [];
        }

        return [
          {
            key:
              `${coverageMetric}-coverage`,

            label:
              `${metricLabel(
                coverageMetric,
              )} valid coverage`,

            className:
              "coverage",

            points:
              pointsForMetric(
                trends,
                coverageMetric,
                (
                  point,
                ) =>
                  point
                    .valid_pixel_percent,
              ),
          },
        ];
      },
      [
        trends,
        coverageMetric,
      ],
    );


  return (
    <section className="satellite-trends-panel">
      <div className="satellite-trends-heading">
        <div>
          <span className="workspace-eyebrow">
            FIELD TRENDS
          </span>

          <h3>
            Satellite trends and farm activities
          </h3>

          <p>
            Satellite observations use their actual acquisition dates.
            Activity markers show when irrigation, fertilizer, spraying
            and other field work occurred.
          </p>
        </div>

        {trends && (
          <span className="satellite-trends-range">
            {formatLongDate(
              trends.start_date,
            )}
            {" → "}
            {formatLongDate(
              trends.end_date,
            )}
          </span>
        )}
      </div>

      {loading && (
        <div className="satellite-trends-state">
          Loading field trends…
        </div>
      )}

      {!loading
        && error && (
        <div className="satellite-trends-state error">
          {error}
        </div>
      )}

      {!loading
        && !error
        && trends && (
        <div className="satellite-trends-grid">
          <TrendChart
            title="Optical crop signals"
            subtitle="NDVI, NDRE and NDMI on one comparable index scale."
            series={
              opticalSeries
            }
            activities={
              trends.activities
            }
            startDate={
              trends.start_date
            }
            endDate={
              trends.end_date
            }
            valueLabel="Index value"
            emptyMessage="No NDVI, NDRE or NDMI observations are available in this period."
          />

          <TrendChart
            title="All-weather radar"
            subtitle="Sentinel-1 Radar RVI. Kept on its own scale because it is not an optical index."
            series={
              radarSeries
            }
            activities={
              trends.activities
            }
            startDate={
              trends.start_date
            }
            endDate={
              trends.end_date
            }
            valueLabel="RVI"
            emptyMessage="No Radar RVI observations are available in this period."
          />

          <TrendChart
            title="Surface temperature"
            subtitle="Landsat land-surface temperature trend."
            series={
              thermalSeries
            }
            activities={
              trends.activities
            }
            startDate={
              trends.start_date
            }
            endDate={
              trends.end_date
            }
            valueLabel="°C"
            emptyMessage="No Landsat surface-temperature observations are available in this period."
          />

          <article className="satellite-trend-chart-with-control">
            <div className="satellite-trend-inline-control">
              <label>
                <span>
                  Anomaly metric
                </span>

                <select
                  value={
                    anomalyMetric
                  }
                  onChange={(event) => {
                    setAnomalyMetric(
                      event.currentTarget.value as SatelliteMetricType,
                    );
                  }}
                >
                  {CONTEXT_METRICS.map(
                    (
                      metricType,
                    ) => (
                      <option
                        key={
                          metricType
                        }
                        value={
                          metricType
                        }
                      >
                        {metricLabel(
                          metricType,
                        )}
                      </option>
                    ),
                  )}
                </select>
              </label>
            </div>

            <TrendChart
              title="Anomaly area"
              subtitle="Total saved anomaly area for the selected metric on each acquisition."
              series={
                anomalySeries
              }
              activities={
                trends.activities
              }
              startDate={
                trends.start_date
              }
              endDate={
                trends.end_date
              }
              valueLabel="Acres"
              fixedMin={
                0
              }
              emptyMessage="No anomaly history is available for this metric in this period."
            />
          </article>

          <article className="satellite-trend-chart-with-control">
            <div className="satellite-trend-inline-control">
              <label>
                <span>
                  Coverage metric
                </span>

                <select
                  value={
                    coverageMetric
                  }
                  onChange={(event) => {
                    setCoverageMetric(
                      event.currentTarget.value as SatelliteMetricType,
                    );
                  }}
                >
                  {CONTEXT_METRICS.map(
                    (
                      metricType,
                    ) => (
                      <option
                        key={
                          metricType
                        }
                        value={
                          metricType
                        }
                      >
                        {metricLabel(
                          metricType,
                        )}
                      </option>
                    ),
                  )}
                </select>
              </label>
            </div>

            <TrendChart
              title="Valid field coverage"
              subtitle="Percentage of field pixels retained as valid for the selected metric."
              series={
                coverageSeries
              }
              activities={
                trends.activities
              }
              startDate={
                trends.start_date
              }
              endDate={
                trends.end_date
              }
              valueLabel="% valid"
              fixedMin={
                0
              }
              fixedMax={
                100
              }
              emptyMessage="No coverage history is available for this metric in this period."
            />
          </article>
        </div>
      )}
    </section>
  );
}
