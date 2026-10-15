import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getSatelliteTrends,
  getFieldWeather,
  getCropGrowthStages,
} from "../lib/api";

import WeatherContextPanel from "./WeatherContextPanel";
import CropGrowthStagePanel from "./CropGrowthStagePanel";
import RadarScreeningPanel from "./RadarScreeningPanel";

import {
  METRIC_CONFIG,
} from "./farm-map/satellite";

import type {
  CropCycle,
  CropGrowth,
  CropStageObservation,
  FieldSatelliteTrends,
  FieldWeather,
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
  tooltip?: string;
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
  stageMarkers?: CropStageObservation[];

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


const RADAR_METRICS: SatelliteMetricType[] = [
  "sar_rvi",
  "sar_vv_db",
  "sar_vh_db",
  "sar_vv_vh_ratio",
];


const ANOMALY_METRICS: SatelliteMetricType[] = [
  "ndvi",
  "ndre",
  "ndmi",
  "lst_c",
];


const CONTEXT_METRICS: SatelliteMetricType[] = [
  "ndvi",
  "ndre",
  "ndmi",
  "sar_rvi",
  "sar_vv_db",
  "sar_vh_db",
  "sar_vv_vh_ratio",
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

    if (
      minimum === maximum
    ) {
      maximum =
        minimum
        + padding;
    }
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
  stageMarkers = [],
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

        {stageMarkers.length > 0 && (
          <span className="satellite-trend-legend-item confirmed-stage">
            <i />
            Farmer-confirmed crop stage
          </span>
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

              {stageMarkers.map((stage) => {
                const x = xForDate(stage.observed_on);
                if (x < margins.left || x > width - margins.right) return null;
                return (
                  <g key={stage.id} className="crop-stage-chart-marker">
                    <line x1={x} x2={x} y1={margins.top} y2={height - margins.bottom} />
                    <circle cx={x} cy={margins.top + 8} r={4}>
                      <title>{stage.stage_code.replace(/_/g, " ")} · {formatLongDate(stage.observed_on)} · Farmer confirmed</title>
                    </circle>
                  </g>
                );
              })}

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
                              {point.tooltip
                                ?? (
                                  item.label
                                  + " · "
                                  + formatLongDate(
                                    point.date,
                                  )
                                  + " · "
                                  + point.value.toFixed(
                                    Math.abs(
                                      point.value,
                                    )
                                      >= 10
                                      ? 1
                                      : 3,
                                  )
                                  + " · "
                                  + sourceLabel(
                                    point.source,
                                  )
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
  minimumCoverage:
    number
    | null = 80,
) {
  return trends.points
    .filter(
      (
        point,
      ) =>
        point.metric_type
        === metricType
        && (
          minimumCoverage
          == null
          || point.valid_pixel_percent
          == null
          || point.valid_pixel_percent
          >= minimumCoverage
        ),
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


function radarGroupKey(
  point: SatelliteTrendPoint,
) {
  return (
    point.radar_orbit_key
    ?? `unknown:${point.observation_id}`
  );
}


function titleCase(
  value: string,
) {
  if (!value) {
    return value;
  }

  return (
    value.charAt(
      0,
    ).toUpperCase()
    + value.slice(
      1,
    ).toLowerCase()
  );
}


function radarOrbitLabel(
  point: SatelliteTrendPoint,
) {
  if (
    point.radar_orbit_key
    == null
  ) {
    return (
      "Unknown geometry · "
      + formatLongDate(
        point.observed_on,
      )
    );
  }

  const parts = [];

  if (point.orbit_state) {
    parts.push(
      titleCase(
        point.orbit_state,
      ),
    );
  }

  if (
    point.relative_orbit
    != null
  ) {
    parts.push(
      `relative orbit ${point.relative_orbit}`,
    );
  }

  return (
    parts.join(
      " · ",
    )
    || "Radar orbit"
  );
}


function radarPointTooltip(
  point: SatelliteTrendPoint,
  metricType:
    SatelliteMetricType,
  value: number,
) {
  const parts = [
    metricLabel(
      metricType,
    ),
    formatLongDate(
      point.observed_on,
    ),
    value.toFixed(
      metricType
        === "sar_vv_db"
        || metricType
        === "sar_vh_db"
        ? 2
        : 3,
    ),
  ];

  if (point.orbit_state) {
    parts.push(
      titleCase(
        point.orbit_state,
      ),
    );
  }

  if (
    point.relative_orbit
    != null
  ) {
    parts.push(
      `relative orbit ${point.relative_orbit}`,
    );
  }

  if (point.platform) {
    parts.push(
      point.platform,
    );
  }

  return parts.join(
    " · ",
  );
}


function RadarTrendPanel({
  trends,
  weather,
  stageMarkers,
}: {
  trends: FieldSatelliteTrends;
  weather: FieldWeather | null;
  stageMarkers: CropStageObservation[];
}) {
  const radarPoints =
    useMemo(
      () =>
        trends.points.filter(
          (
            point,
          ) =>
            point.source
              .startsWith(
                "sentinel-1",
              )
            && RADAR_METRICS.includes(
              point.metric_type,
            )
            && (
              point.valid_pixel_percent
              == null
              || point.valid_pixel_percent
              >= 80
            ),
        ),
      [
        trends,
      ],
    );

  const orbitGroups =
    useMemo(
      () => {
        const groups =
          new Map<
            string,
            {
              key: string;
              label: string;
              observationIds:
                Set<string>;
              representative:
                SatelliteTrendPoint;
            }
          >();

        for (
          const point
          of radarPoints
        ) {
          const key =
            radarGroupKey(
              point,
            );

          const current =
            groups.get(
              key,
            );

          if (current) {
            current
              .observationIds
              .add(
                point.observation_id,
              );

            continue;
          }

          groups.set(
            key,
            {
              key,
              label:
                radarOrbitLabel(
                  point,
                ),
              observationIds:
                new Set(
                  [
                    point
                      .observation_id,
                  ],
                ),
              representative:
                point,
            },
          );
        }

        return [
          ...groups.values(),
        ]
          .sort(
            (
              a,
              b,
            ) =>
              b.observationIds
                .size
              - a.observationIds
                .size,
          );
      },
      [
        radarPoints,
      ],
    );

  const [
    selectedOrbitKey,
    setSelectedOrbitKey,
  ] = useState(
    "",
  );

  useEffect(
    () => {
      if (
        orbitGroups.length
        === 0
      ) {
        setSelectedOrbitKey(
          "",
        );

        return;
      }

      if (
        orbitGroups.some(
          (
            group,
          ) =>
            group.key
            === selectedOrbitKey,
        )
      ) {
        return;
      }

      setSelectedOrbitKey(
        orbitGroups[
          0
        ].key,
      );
    },
    [
      orbitGroups,
      selectedOrbitKey,
    ],
  );

  const selectedGroup =
    orbitGroups.find(
      (
        group,
      ) =>
        group.key
        === selectedOrbitKey,
    )
    ?? orbitGroups[
      0
    ]
    ?? null;

  const selectedPoints =
    useMemo(
      () => {
        if (!selectedGroup) {
          return [];
        }

        return radarPoints.filter(
          (
            point,
          ) =>
            radarGroupKey(
              point,
            )
            === selectedGroup.key,
        );
      },
      [
        radarPoints,
        selectedGroup,
      ],
    );

  function radarSeries(
    metricType:
      SatelliteMetricType,
    className: string,
  ): ChartSeries[] {
    const points =
      selectedPoints
        .filter(
          (
            point,
          ) =>
            point.metric_type
            === metricType
            && point.median
            != null
            && Number.isFinite(
              point.median,
            ),
        )
        .map(
          (
            point,
          ) => ({
            date:
              point.observed_on,
            value:
              Number(
                point.median,
              ),
            source:
              point.source,
            tooltip:
              radarPointTooltip(
                point,
                metricType,
                Number(
                  point.median,
                ),
              ),
          }),
        );

    return [
      {
        key:
          metricType,
        label:
          metricLabel(
            metricType,
          ),
        className,
        points,
      },
    ];
  }

  const passRows =
    useMemo(
      () => {
        const passes =
          new Map<
            string,
            {
              observationId: string;
              observedOn: string;
              orbitState:
                string
                | null;
              relativeOrbit:
                number
                | null;
              platform:
                string
                | null;
              values:
                Partial<
                  Record<
                    SatelliteMetricType,
                    number
                  >
                >;
            }
          >();

        for (
          const point
          of selectedPoints
        ) {
          if (
            point.median
            == null
          ) {
            continue;
          }

          const existing =
            passes.get(
              point.observation_id,
            );

          if (existing) {
            existing.values[
              point.metric_type
            ] = point.median;

            continue;
          }

          passes.set(
            point.observation_id,
            {
              observationId:
                point.observation_id,
              observedOn:
                point.observed_on,
              orbitState:
                point.orbit_state,
              relativeOrbit:
                point.relative_orbit,
              platform:
                point.platform,
              values: {
                [
                  point.metric_type
                ]:
                  point.median,
              },
            },
          );
        }

        return [
          ...passes.values(),
        ]
          .sort(
            (
              a,
              b,
            ) =>
              b.observedOn
                .localeCompare(
                  a.observedOn,
                ),
          );
      },
      [
        selectedPoints,
      ],
    );

  const comparableRvi = selectedPoints
    .filter((point) => point.metric_type === "sar_rvi" && point.median != null)
    .sort((a, b) => a.observed_on.localeCompare(b.observed_on));
  const currentRvi = comparableRvi[comparableRvi.length - 1];
  const previousRvi = comparableRvi[comparableRvi.length - 2];
  const rviDelta = currentRvi?.median != null && previousRvi?.median != null
    ? currentRvi.median - previousRvi.median
    : null;
  const rainNearCurrent = currentRvi && weather
    ? weather.days.filter((day) => (
        day.date <= currentRvi.observed_on &&
        dateMs(day.date) >= dateMs(currentRvi.observed_on) - 2 * 86_400_000 &&
        day.precipitation_mm != null
      ))
    : [];
  const rainThreeDayTotal = rainNearCurrent.length === 3
    ? rainNearCurrent.reduce((total, day) => total + (day.precipitation_mm ?? 0), 0)
    : null;

  if (
    orbitGroups.length
    === 0
  ) {
    return (
      <article className="radar-interpretation-panel">
        <div className="radar-interpretation-heading">
          <div>
            <span className="workspace-eyebrow">
              RADAR INTERPRETATION
            </span>

            <h4>
              Orbit-aware Sentinel-1
            </h4>

            <p>
              No reliable Sentinel-1 radar observations are available in
              this period.
            </p>
          </div>
        </div>
      </article>
    );
  }

  const representative =
    selectedGroup
      ?.representative
    ?? null;

  return (
    <article className="radar-interpretation-panel">
      <div className="radar-interpretation-heading">
        <div>
          <span className="workspace-eyebrow">
            RADAR INTERPRETATION
          </span>

          <h4>
            Orbit-aware Sentinel-1
          </h4>

          <p>
            Radar passes are only connected when their viewing geometry is
            comparable. RVI, VV, VH and VV/VH are signals—not health scores.
          </p>
        </div>

        <label className="radar-orbit-selector">
          <span>
            Comparable orbit
          </span>

          <select
            value={
              selectedGroup
                ?.key
              ?? ""
            }
            onChange={(
              event,
            ) =>
              setSelectedOrbitKey(
                event.currentTarget
                  .value,
              )
            }
          >
            {orbitGroups.map(
              (
                group,
              ) => (
                <option
                  key={
                    group.key
                  }
                  value={
                    group.key
                  }
                >
                  {group.label}
                  {" · "}
                  {
                    group
                      .observationIds
                      .size
                  }
                  {" "}
                  {
                    group
                      .observationIds
                      .size
                    === 1
                      ? "pass"
                      : "passes"
                  }
                </option>
              ),
            )}
          </select>
        </label>
      </div>

      <div className="radar-orbit-summary">
        <div>
          <span>
            Orbit state
          </span>

          <strong>
            {representative
              ?.orbit_state
              ? titleCase(
                  representative
                    .orbit_state,
                )
              : "Unknown"}
          </strong>
        </div>

        <div>
          <span>
            Relative orbit
          </span>

          <strong>
            {representative
              ?.relative_orbit
              ?? "Unknown"}
          </strong>
        </div>

        <div>
          <span>
            Platform
          </span>

          <strong>
            {representative
              ?.platform
              ?? "Unknown"}
          </strong>
        </div>

        <div>
          <span>
            Comparable passes
          </span>

          <strong>
            {selectedGroup
              ?.observationIds
              .size
              ?? 0}
          </strong>
        </div>
      </div>

      {orbitGroups.length > 1 && (
        <p className="radar-orbit-warning">
          {orbitGroups.length - 1}
          {" other viewing "}
          {
            orbitGroups.length
            - 1
            === 1
              ? "geometry is"
              : "geometries are"
          }
          {" kept separate from this line. Switch the orbit selector to inspect them."}
        </p>
      )}

      <div className="radar-change-summary">
        <div>
          <span>Latest comparable RVI change</span>
          <strong>
            {rviDelta == null ? "Not enough passes" : (rviDelta >= 0 ? "+" : "") + rviDelta.toFixed(3)}
          </strong>
          <small>
            {currentRvi && previousRvi
              ? formatShortDate(previousRvi.observed_on) + " → " + formatShortDate(currentRvi.observed_on)
              : "Same-orbit acquisitions required"}
          </small>
        </div>
        <div>
          <span>Rain before latest radar pass</span>
          <strong>{rainThreeDayTotal == null ? "—" : rainThreeDayTotal.toFixed(1) + " mm"}</strong>
          <small>{currentRvi
            ? "3-day modeled total ending " + formatShortDate(currentRvi.observed_on)
            : "Weather data may be unavailable"}</small>
        </div>
        <p>RVI change is a radar signal, not a crop-health verdict. Rain is context, not a proven explanation.</p>
      </div>
      <div className="radar-primary-chart">
        <TrendChart
          title="Radar RVI"
          stageMarkers={stageMarkers}
          subtitle="Relative dual-polarization canopy/structure signal for the selected orbit geometry."
          series={
            radarSeries(
              "sar_rvi",
              "sar-rvi",
            )
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
          fixedMin={
            0
          }
          emptyMessage="No reliable RVI observations exist for this orbit."
        />
      </div>

      <details className="radar-technical-details">
        <summary>Technical radar signals: VV, VH and VV/VH ratio · view acquisition table</summary>
        <div className="radar-metric-chart-grid">
        <TrendChart
          title="VV backscatter"
          subtitle="Co-polarized gamma-nought backscatter. Changes can reflect moisture, roughness and structure."
          series={
            radarSeries(
              "sar_vv_db",
              "sar-vv",
            )
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
          valueLabel="dB"
          emptyMessage="No reliable VV observations exist for this orbit."
        />

        <TrendChart
          title="VH backscatter"
          subtitle="Cross-polarized gamma-nought backscatter, often responsive to vegetation structure."
          series={
            radarSeries(
              "sar_vh_db",
              "sar-vh",
            )
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
          valueLabel="dB"
          emptyMessage="No reliable VH observations exist for this orbit."
        />

        <TrendChart
          title="VV / VH ratio"
          subtitle="Polarization ratio for the same comparable Sentinel-1 passes."
          series={
            radarSeries(
              "sar_vv_vh_ratio",
              "sar-ratio",
            )
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
          valueLabel="Ratio"
          fixedMin={
            0
          }
          emptyMessage="No reliable VV/VH observations exist for this orbit."
        />
      </div>

      {passRows.length > 0 && (
        <div className="radar-pass-table-wrap">
          <table className="radar-pass-table">
            <thead>
              <tr>
                <th>
                  Date
                </th>
                <th>
                  Platform
                </th>
                <th>
                  VV dB
                </th>
                <th>
                  VH dB
                </th>
                <th>
                  VV/VH
                </th>
                <th>
                  RVI
                </th>
              </tr>
            </thead>

            <tbody>
              {passRows
                .slice(
                  0,
                  12,
                )
                .map(
                  (
                    pass,
                  ) => (
                    <tr
                      key={
                        pass
                          .observationId
                      }
                    >
                      <td>
                        {formatLongDate(
                          pass.observedOn,
                        )}
                      </td>
                      <td>
                        {pass.platform
                          ?? "—"}
                      </td>
                      <td>
                        {pass.values
                          .sar_vv_db
                          ?.toFixed(
                            2,
                          )
                          ?? "—"}
                      </td>
                      <td>
                        {pass.values
                          .sar_vh_db
                          ?.toFixed(
                            2,
                          )
                          ?? "—"}
                      </td>
                      <td>
                        {pass.values
                          .sar_vv_vh_ratio
                          ?.toFixed(
                            3,
                          )
                          ?? "—"}
                      </td>
                      <td>
                        {pass.values
                          .sar_rvi
                          ?.toFixed(
                            3,
                          )
                          ?? "—"}
                      </td>
                    </tr>
                  ),
                )}
            </tbody>
          </table>
        </div>
      )}

      </details>

      <p className="radar-interpretation-note">
        Do not interpret higher/lower radar values as automatically
        healthier/unhealthier. Soil moisture, standing water, canopy
        structure, surface roughness and crop-row geometry can all change
        the signal. Crop/stage-aware anomaly rules remain intentionally
        disabled until enough field data is collected.
      </p>
    </article>
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

  const [weather, setWeather] = useState<FieldWeather | null>(null);
  const [weatherLoading, setWeatherLoading] = useState(true);
  const [weatherError, setWeatherError] = useState<string | null>(null);

  const [growth, setGrowth] = useState<CropGrowth | null>(null);
  const [growthLoading, setGrowthLoading] = useState(false);
  const [growthError, setGrowthError] = useState<string | null>(null);

  useEffect(() => {
    if (!cropCycle) {
      setGrowth(null);
      setGrowthLoading(false);
      setGrowthError(null);
      return;
    }
    let cancelled = false;
    setGrowth(null);
    setGrowthLoading(true);
    setGrowthError(null);
    void getCropGrowthStages(cropCycle.id)
      .then((result) => {
        if (!cancelled) setGrowth(result);
      })
      .catch((err: unknown) => {
        if (!cancelled) setGrowthError(
          err instanceof Error ? err.message : "Could not load crop stages.",
        );
      })
      .finally(() => {
        if (!cancelled) setGrowthLoading(false);
      });
    return () => { cancelled = true; };
  }, [cropCycle?.id]);

  async function refreshGrowthStages() {
    if (!cropCycle) return;
    const updated = await getCropGrowthStages(cropCycle.id);
    setGrowth(updated);
  }

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


  useEffect(() => {
    if (!trends) {
      setWeather(null);
      setWeatherLoading(false);
      return;
    }
    let cancelled = false;
    setWeatherLoading(true);
    setWeatherError(null);
    const requestedStart = new Date(
      Math.max(dateMs(trends.start_date), dateMs(trends.end_date) - 365 * 86_400_000),
    ).toISOString().slice(0, 10);
    void getFieldWeather(fieldId, {
      startDate: requestedStart,
      endDate: trends.end_date,
      includeForecast: cropCycle?.status !== "completed",
    })
      .then((result) => {
        if (!cancelled) setWeather(result);
      })
      .catch((requestError: unknown) => {
        if (!cancelled) {
          setWeather(null);
          setWeatherError(
            requestError instanceof Error ? requestError.message : "Weather service unavailable",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setWeatherLoading(false);
      });
    return () => { cancelled = true; };
  }, [fieldId, trends, cropCycle?.status]);

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
                null,
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
          {cropCycle && (
            <CropGrowthStagePanel
              cropCycle={cropCycle}
              growth={growth}
              loading={growthLoading}
              error={growthError}
              onChanged={refreshGrowthStages}
            />
          )}
          <TrendChart
            title="Optical crop signals"
            stageMarkers={growth?.observations ?? []}
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

          <RadarTrendPanel
            trends={trends}
            weather={weather}
            stageMarkers={growth?.observations ?? []}
          />
          {cropCycle && !growthLoading && (
            <RadarScreeningPanel
              cropCycleId={cropCycle.id}
              stagesFingerprint={
                growth?.observations.map((item) => (
                  item.stage_code + ":" + item.observed_on + ":" + item.updated_at
                )).join("|") ?? ""
              }
            />
          )}
          <WeatherContextPanel
            weather={weather}
            loading={weatherLoading}
            error={weatherError}
            activities={trends.activities}
            startDate={trends.start_date}
            endDate={trends.end_date}
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
                  {ANOMALY_METRICS.map(
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
