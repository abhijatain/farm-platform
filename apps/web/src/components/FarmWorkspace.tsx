import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  CalendarDays,
  LayoutGrid,
  Layers3,
  LogOut,
  Map as MapIcon,
  MapPin,
  Plus,
  Search,
  Satellite,
  Sprout,
} from "lucide-react";

import {
  useAuth,
} from "../providers/AuthProvider";

import FarmOverviewMap
  from "./FarmOverviewMap";

import FieldBoundaryPreview
  from "./FieldBoundaryPreview";

import CreateFarmDialog
  from "./CreateFarmDialog";

import CreateFieldDialog
  from "./CreateFieldDialog";

import CreateSeasonDialog
  from "./CreateSeasonDialog";

import FieldDetailsPanel
  from "./FieldDetailsPanel";

import {
  createFarm,
  createField,
  createSeason,
  getFarmSatelliteOverview,
  listFarms,
  listFields,
  listSeasons,
  listSeasonCropCycles,
} from "../lib/api";

import {
  METRIC_CONFIG,
  METRIC_GROUPS,
  buildMetricPreviewUrl,
  formatMetricValue,
} from "./farm-map/satellite";

import type {
  CropCycle,
  Farm,
  FarmSatelliteOverviewItem,
  Field,
  PolygonGeometry,
  SatelliteMetricType,
  Season,
} from "../types/api";

import type {
  MapMode,
} from "../types/map";


type HomeView =
  | "fields"
  | "map";


const TILER_URL =
  import.meta.env
    .VITE_TILER_URL;


if (!TILER_URL) {
  throw new Error(
    "VITE_TILER_URL is missing.",
  );
}


function chooseDefaultSeason(
  seasons: Season[],
) {
  if (
    seasons.length === 0
  ) {
    return null;
  }

  const active =
    seasons.find(
      (
        season,
      ) =>
        season.status
        === "active",
    );

  if (active) {
    return active;
  }

  return (
    [...seasons]
      .sort(
        (
          a,
          b,
        ) =>
          new Date(
            b.started_on,
          ).getTime()
          -
          new Date(
            a.started_on,
          ).getTime(),
      )[
        0
      ]
    ?? null
  );
}


function chooseFieldCropCycle(
  fieldId: string,
  cropCycles: CropCycle[],
) {
  return (
    cropCycles
      .filter(
        (
          cycle,
        ) =>
          cycle.field_id
          === fieldId,
      )
      .sort(
        (
          a,
          b,
        ) => {
          if (
            a.status === "active"
            && b.status
              !== "active"
          ) {
            return -1;
          }

          if (
            b.status === "active"
            && a.status
              !== "active"
          ) {
            return 1;
          }

          return (
            new Date(
              b.started_on,
            ).getTime()
            -
            new Date(
              a.started_on,
            ).getTime()
          );
        },
      )[
        0
      ]
    ?? null
  );
}


function formatOverviewDate(
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


function formatSource(
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


export default function FarmWorkspace() {
  const {
    profile,
    logout,
  } = useAuth();

  const [
    farms,
    setFarms,
  ] = useState<
    Farm[]
  >([]);

  const [
    selectedFarmId,
    setSelectedFarmId,
  ] = useState<
    string | null
  >(null);

  const [
    fields,
    setFields,
  ] = useState<
    Field[]
  >([]);

  const [
    seasons,
    setSeasons,
  ] = useState<
    Season[]
  >([]);

  const [
    selectedSeasonId,
    setSelectedSeasonId,
  ] = useState<
    string | null
  >(null);

  const [
    seasonCropCycles,
    setSeasonCropCycles,
  ] = useState<
    CropCycle[]
  >([]);

  const [
    selectedFieldId,
    setSelectedFieldId,
  ] = useState<
    string | null
  >(null);

  const [
    homeView,
    setHomeView,
  ] = useState<
    HomeView
  >(
    "fields",
  );

  const [
    mapMode,
    setMapMode,
  ] = useState<
    MapMode
  >(
    "hybrid",
  );

  const [
    overviewMetricType,
    setOverviewMetricType,
  ] = useState<
    SatelliteMetricType
  >(
    "ndvi",
  );

  const [
    overviewDate,
    setOverviewDate,
  ] = useState<
    string | null
  >(null);

  const [
    overview,
    setOverview,
  ] = useState<
    FarmSatelliteOverviewItem[]
  >([]);

  const [
    overviewLoading,
    setOverviewLoading,
  ] = useState(
    false,
  );

  const [
    overviewError,
    setOverviewError,
  ] = useState<
    string | null
  >(null);

  const [
    drawing,
    setDrawing,
  ] = useState(
    false,
  );

  const [
    createFarmOpen,
    setCreateFarmOpen,
  ] = useState(
    false,
  );

  const [
    createSeasonOpen,
    setCreateSeasonOpen,
  ] = useState(
    false,
  );

  const [
    pendingBoundary,
    setPendingBoundary,
  ] = useState<
    PolygonGeometry | null
  >(null);

  const [
    fieldQuery,
    setFieldQuery,
  ] = useState(
    "",
  );

  const [
    error,
    setError,
  ] = useState<
    string | null
  >(null);

  const selectedFarmIdRef =
    useRef<
      string | null
    >(
      selectedFarmId,
    );

  const farmContextRequestRef =
    useRef(
      0,
    );

  const seasonCropCyclesRequestRef =
    useRef(
      0,
    );

  const overviewRequestRef =
    useRef(
      0,
    );

  selectedFarmIdRef.current =
    selectedFarmId;


  async function loadFarms() {
    try {
      setError(
        null,
      );

      const result =
        await listFarms();

      setFarms(
        result,
      );

      if (
        result.length === 0
      ) {
        setSelectedFarmId(
          null,
        );

        return;
      }

      setSelectedFarmId(
        (
          current,
        ) => {
          if (
            current
            && result.some(
              (
                farm,
              ) =>
                farm.id
                === current,
            )
          ) {
            return current;
          }

          return (
            result[
              0
            ].id
          );
        },
      );

    } catch (
      requestError
    ) {
      setError(
        requestError
          instanceof Error
          ? requestError.message
          : "Unable to load farms.",
      );
    }
  }


  async function loadFarmContext(
    farmId: string,
  ) {
    const requestId =
      ++farmContextRequestRef
        .current;

    try {
      setError(
        null,
      );

      const [
        nextFields,
        nextSeasons,
      ] =
        await Promise.all([
          listFields(
            farmId,
          ),
          listSeasons(
            farmId,
          ),
        ]);

      if (
        requestId
          !== farmContextRequestRef
            .current
        || selectedFarmIdRef
          .current
          !== farmId
      ) {
        return;
      }

      setFields(
        nextFields,
      );

      setSeasons(
        nextSeasons,
      );

      setSelectedFieldId(
        null,
      );

      const defaultSeason =
        chooseDefaultSeason(
          nextSeasons,
        );

      setSelectedSeasonId(
        defaultSeason?.id
        ?? null,
      );

    } catch (
      requestError
    ) {
      if (
        requestId
          !== farmContextRequestRef
            .current
        || selectedFarmIdRef
          .current
          !== farmId
      ) {
        return;
      }

      setError(
        requestError
          instanceof Error
          ? requestError.message
          : "Unable to load farm.",
      );
    }
  }


  async function loadOverview(
    farmId: string,
    metricType:
      SatelliteMetricType,
    date:
      string | null,
  ) {
    const requestId =
      ++overviewRequestRef
        .current;

    try {
      setOverviewLoading(
        true,
      );

      setOverviewError(
        null,
      );

      const result =
        await getFarmSatelliteOverview(
          farmId,
          metricType,
          date,
        );

      if (
        requestId
        !== overviewRequestRef
          .current
      ) {
        return;
      }

      setOverview(
        result,
      );

    } catch (
      requestError
    ) {
      if (
        requestId
        !== overviewRequestRef
          .current
      ) {
        return;
      }

      setOverview(
        [],
      );

      setOverviewError(
        requestError
          instanceof Error
          ? requestError.message
          : "Unable to load satellite overview.",
      );

    } finally {
      if (
        requestId
        === overviewRequestRef
          .current
      ) {
        setOverviewLoading(
          false,
        );
      }
    }
  }


  async function refreshFields() {
    if (
      !selectedFarmId
    ) {
      return;
    }

    const result =
      await listFields(
        selectedFarmId,
      );

    setFields(
      result,
    );
  }


  async function refreshSeasons(
    preferredSeasonId?:
      string,
  ) {
    if (
      !selectedFarmId
    ) {
      return;
    }

    const result =
      await listSeasons(
        selectedFarmId,
      );

    setSeasons(
      result,
    );

    if (
      preferredSeasonId
      && result.some(
        (
          season,
        ) =>
          season.id
          === preferredSeasonId,
      )
    ) {
      setSelectedSeasonId(
        preferredSeasonId,
      );

      return;
    }

    const defaultSeason =
      chooseDefaultSeason(
        result,
      );

    setSelectedSeasonId(
      defaultSeason?.id
      ?? null,
    );
  }


  async function refreshSeasonCropCycles(
    seasonId?:
      string | null,
  ) {
    const requestId =
      ++seasonCropCyclesRequestRef
        .current;

    const id =
      seasonId
      ?? selectedSeasonId;

    if (!id) {
      setSeasonCropCycles(
        [],
      );

      return;
    }

    try {
      const result =
        await listSeasonCropCycles(
          id,
        );

      if (
        requestId
        !== seasonCropCyclesRequestRef
          .current
      ) {
        return;
      }

      setSeasonCropCycles(
        result,
      );

    } catch (
      requestError
    ) {
      if (
        requestId
        !== seasonCropCyclesRequestRef
          .current
      ) {
        return;
      }

      setError(
        requestError
          instanceof Error
          ? requestError.message
          : "Unable to load crop cycles.",
      );
    }
  }


  useEffect(
    () => {
      void loadFarms();
    },
    [],
  );


  useEffect(
    () => {
      if (
        !selectedFarmId
      ) {
        farmContextRequestRef
          .current += 1;

        seasonCropCyclesRequestRef
          .current += 1;

        overviewRequestRef
          .current += 1;

        setFields(
          [],
        );

        setSeasons(
          [],
        );

        setSeasonCropCycles(
          [],
        );

        setOverview(
          [],
        );

        setSelectedSeasonId(
          null,
        );

        return;
      }

      setDrawing(
        false,
      );

      setPendingBoundary(
        null,
      );

      setFieldQuery(
        "",
      );

      setHomeView(
        "fields",
      );

      void loadFarmContext(
        selectedFarmId,
      );
    },
    [
      selectedFarmId,
    ],
  );


  useEffect(
    () => {
      seasonCropCyclesRequestRef
        .current += 1;

      setSeasonCropCycles(
        [],
      );

      if (
        selectedSeasonId
      ) {
        void refreshSeasonCropCycles(
          selectedSeasonId,
        );
      }
    },
    [
      selectedSeasonId,
    ],
  );


  useEffect(
    () => {
      if (
        !selectedFarmId
      ) {
        setOverview(
          [],
        );

        return;
      }

      void loadOverview(
        selectedFarmId,
        overviewMetricType,
        overviewDate,
      );
    },
    [
      selectedFarmId,
      overviewMetricType,
      overviewDate,
    ],
  );


  const selectedFarm =
    useMemo(
      () =>
        farms.find(
          (
            farm,
          ) =>
            farm.id
            === selectedFarmId,
        )
        ?? null,
      [
        farms,
        selectedFarmId,
      ],
    );


  const selectedSeason =
    useMemo(
      () =>
        seasons.find(
          (
            season,
          ) =>
            season.id
            === selectedSeasonId,
        )
        ?? null,
      [
        seasons,
        selectedSeasonId,
      ],
    );


  const selectedField =
    useMemo(
      () =>
        fields.find(
          (
            field,
          ) =>
            field.id
            === selectedFieldId,
        )
        ?? null,
      [
        fields,
        selectedFieldId,
      ],
    );


  const selectedCropCycle =
    useMemo(
      () => {
        if (
          !selectedFieldId
        ) {
          return null;
        }

        return (
          chooseFieldCropCycle(
            selectedFieldId,
            seasonCropCycles,
          )
        );
      },
      [
        selectedFieldId,
        seasonCropCycles,
      ],
    );


  const overviewByField =
    useMemo(
      () =>
        new Map(
          overview.map(
            (
              item,
            ) => [
              item.field_id,
              item,
            ],
          ),
        ),
      [
        overview,
      ],
    );


  const filteredFields =
    useMemo(
      () => {
        const query =
          fieldQuery
            .trim()
            .toLowerCase();

        if (!query) {
          return fields;
        }

        return fields.filter(
          (
            field,
          ) =>
            field.name
              .toLowerCase()
              .includes(
                query,
              ),
        );
      },
      [
        fields,
        fieldQuery,
      ],
    );


  const totalAcres =
    useMemo(
      () =>
        fields.reduce(
          (
            total,
            field,
          ) =>
            total
            + field.area_acres,
          0,
        ),
      [
        fields,
      ],
    );


  async function handleCreateFarm(
    name: string,
    location:
      string | null,
  ) {
    try {
      setError(
        null,
      );

      const farm =
        await createFarm({
          name,
          location_name:
            location,
        });

      const refreshed =
        await listFarms();

      setFarms(
        refreshed,
      );

      setSelectedFarmId(
        farm.id,
      );

    } catch (
      requestError
    ) {
      setError(
        requestError
          instanceof Error
          ? requestError.message
          : "Unable to create farm.",
      );

      throw requestError;
    }
  }


  async function handleCreateSeason(
    name: string,
    seasonType:
      string | null,
    startedOn: string,
  ) {
    if (
      !selectedFarmId
    ) {
      throw new Error(
        "Select a farm first.",
      );
    }

    try {
      setError(
        null,
      );

      const season =
        await createSeason(
          selectedFarmId,
          {
            name,
            season_type:
              seasonType,
            started_on:
              startedOn,
            ended_on:
              null,
          },
        );

      await refreshSeasons(
        season.id,
      );

      setSelectedSeasonId(
        season.id,
      );

    } catch (
      requestError
    ) {
      setError(
        requestError
          instanceof Error
          ? requestError.message
          : "Unable to create season.",
      );

      throw requestError;
    }
  }


  async function handleCreateField(
    name: string,
  ) {
    if (
      !selectedFarmId
      || !pendingBoundary
    ) {
      return;
    }

    try {
      setError(
        null,
      );

      const field =
        await createField(
          selectedFarmId,
          {
            name,
            boundary:
              pendingBoundary,
          },
        );

      await refreshFields();

      setPendingBoundary(
        null,
      );

      setDrawing(
        false,
      );

      setHomeView(
        "fields",
      );

      setSelectedFieldId(
        field.id,
      );

      void loadOverview(
        selectedFarmId,
        overviewMetricType,
        overviewDate,
      );

    } catch (
      requestError
    ) {
      setError(
        requestError
          instanceof Error
          ? requestError.message
          : "Unable to create field.",
      );

      throw requestError;
    }
  }


  function handleStartDrawing() {
    if (
      !selectedFarmId
    ) {
      setCreateFarmOpen(
        true,
      );

      return;
    }

    setPendingBoundary(
      null,
    );

    setSelectedFieldId(
      null,
    );

    setHomeView(
      "map",
    );

    setDrawing(
      true,
    );
  }


  function handleCancelDrawing() {
    setDrawing(
      false,
    );

    setPendingBoundary(
      null,
    );
  }


  function changeHomeView(
    nextView:
      HomeView,
  ) {
    if (
      nextView
      === "fields"
    ) {
      handleCancelDrawing();
    }

    setHomeView(
      nextView,
    );
  }


  return (
    <div className="home-shell">
      <header className="home-topbar">
        <div className="home-brand">
          <div className="home-brand-mark">
            <Sprout
              size={21}
            />
          </div>

          <div>
            <strong>
              Farm Platform
            </strong>

            <span>
              Field intelligence
            </span>
          </div>
        </div>

        <div className="home-context">
          <div className="home-control-group">
            <span>
              Farm
            </span>

            <select
              value={
                selectedFarmId
                ?? ""
              }
              onChange={(
                event,
              ) =>
                setSelectedFarmId(
                  event.target
                    .value
                  || null,
                )
              }
            >
              {farms.length === 0 && (
                <option value="">
                  No farms yet
                </option>
              )}

              {farms.map(
                (
                  farm,
                ) => (
                  <option
                    key={
                      farm.id
                    }
                    value={
                      farm.id
                    }
                  >
                    {farm.name}
                  </option>
                ),
              )}
            </select>
          </div>

          <div className="home-control-group">
            <span>
              Season
            </span>

            <select
              value={
                selectedSeasonId
                ?? ""
              }
              disabled={
                seasons.length
                === 0
              }
              onChange={(
                event,
              ) =>
                setSelectedSeasonId(
                  event.target
                    .value
                  || null,
                )
              }
            >
              {seasons.length === 0 && (
                <option value="">
                  No season
                </option>
              )}

              {seasons.map(
                (
                  season,
                ) => (
                  <option
                    key={
                      season.id
                    }
                    value={
                      season.id
                    }
                  >
                    {season.name}
                  </option>
                ),
              )}
            </select>
          </div>
        </div>

        <div className="home-actions">
          <button
            className="home-action secondary"
            onClick={
              () =>
                setCreateFarmOpen(
                  true,
                )
            }
          >
            <Plus
              size={15}
            />
            Farm
          </button>

          <button
            className="home-action secondary"
            disabled={
              !selectedFarmId
            }
            onClick={
              () =>
                setCreateSeasonOpen(
                  true,
                )
            }
          >
            <CalendarDays
              size={15}
            />
            Season
          </button>

          <button
            className="home-action primary"
            onClick={
              handleStartDrawing
            }
          >
            <MapPin
              size={15}
            />
            Add field
          </button>

          <div className="home-user">
            <div>
              <strong>
                {profile?.name
                  || "Farmer"}
              </strong>

              <span>
                {profile?.phone_e164
                  ?? ""}
              </span>
            </div>

            <button
              className="home-icon-button"
              onClick={
                () =>
                  void logout()
              }
              title="Sign out"
            >
              <LogOut
                size={17}
              />
            </button>
          </div>
        </div>
      </header>

      <main className="home-main">
        <section className="home-dashboard">
          <div className="home-dashboard-header">
            <div className="home-dashboard-title">
              <span>
                FARM OVERVIEW
              </span>

              <h1>
                {selectedFarm?.name
                  ?? "Your farm"}
              </h1>

              <p>
                {fields.length}
                {" "}
                {fields.length === 1
                  ? "field"
                  : "fields"}
                {" · "}
                {totalAcres.toFixed(
                  1,
                )}
                {" acres"}

                {selectedSeason
                  ? ` · ${selectedSeason.name}`
                  : ""}
              </p>
            </div>

            {selectedFarmId && (
              <div className="home-overview-filters">
                <label>
                  <span>
                    Metric
                  </span>

                  <select
                    value={
                      overviewMetricType
                    }
                    onChange={(event) => {
                      setOverviewMetricType(
                        event.currentTarget.value as SatelliteMetricType,
                      );
                    }}
                  >
                    {METRIC_GROUPS.map(
                      (
                        group,
                      ) => (
                        <optgroup
                          key={
                            group.label
                          }
                          label={
                            group.label
                          }
                        >
                          {group.metrics.map(
                            (
                              metric,
                            ) => (
                              <option
                                key={
                                  metric
                                }
                                value={
                                  metric
                                }
                              >
                                {
                                  METRIC_CONFIG[
                                    metric
                                  ].label
                                }
                              </option>
                            ),
                          )}
                        </optgroup>
                      ),
                    )}
                  </select>
                </label>

                <label>
                  <span>
                    Date
                  </span>

                  <div className="home-date-input">
                    <input
                      type="date"
                      value={
                        overviewDate
                        ?? ""
                      }
                      onChange={(
                        event,
                      ) =>
                        setOverviewDate(
                          event.target
                            .value
                          || null,
                        )
                      }
                    />

                    {overviewDate && (
                      <button
                        onClick={
                          () =>
                            setOverviewDate(
                              null,
                            )
                        }
                      >
                        Latest
                      </button>
                    )}
                  </div>
                </label>
              </div>
            )}
          </div>

          {selectedFarmId && (
            <div className="home-view-bar">
              <div className="home-view-tabs">
                <button
                  className={
                    homeView
                    === "fields"
                      ? "active"
                      : ""
                  }
                  onClick={
                    () =>
                      changeHomeView(
                        "fields",
                      )
                  }
                >
                  <LayoutGrid
                    size={16}
                  />
                  Fields
                </button>

                <button
                  className={
                    homeView
                    === "map"
                      ? "active"
                      : ""
                  }
                  onClick={
                    () =>
                      changeHomeView(
                        "map",
                      )
                  }
                >
                  <MapIcon
                    size={16}
                  />
                  Map
                </button>
              </div>

              {homeView
                === "fields" && (
                  <div className="home-grid-search">
                    <Search
                      size={16}
                    />

                    <input
                      value={
                        fieldQuery
                      }
                      onChange={(
                        event,
                      ) =>
                        setFieldQuery(
                          event.target
                            .value,
                        )
                      }
                      placeholder="Search fields"
                    />
                  </div>
                )}

              {homeView
                === "map" && (
                  <div className="home-map-mode">
                    <button
                      className={
                        mapMode
                        === "streets"
                          ? "active"
                          : ""
                      }
                      onClick={
                        () =>
                          setMapMode(
                            "streets",
                          )
                      }
                      title="Map"
                    >
                      <Layers3
                        size={16}
                      />
                    </button>

                    <button
                      className={
                        mapMode
                        === "hybrid"
                          ? "active"
                          : ""
                      }
                      onClick={
                        () =>
                          setMapMode(
                            "hybrid",
                          )
                      }
                      title="Satellite basemap"
                    >
                      <Satellite
                        size={16}
                      />
                    </button>
                  </div>
                )}
            </div>
          )}

          <div className="home-view-content">
            {!selectedFarmId && (
              <div className="home-onboarding home-onboarding-static">
                <div className="home-onboarding-icon">
                  <Sprout
                    size={28}
                  />
                </div>

                <span>
                  START HERE
                </span>

                <h1>
                  Create your first farm
                </h1>

                <p>
                  Add a farm, then draw field boundaries and satellite
                  monitoring will begin automatically.
                </p>

                <button
                  className="home-action primary"
                  onClick={
                    () =>
                      setCreateFarmOpen(
                        true,
                      )
                  }
                >
                  <Plus
                    size={16}
                  />
                  Create farm
                </button>
              </div>
            )}

            {selectedFarmId
              && homeView
                === "fields" && (
                  <div className="home-fields-grid-view">
                    {overviewLoading && (
                      <div className="home-inline-status">
                        Loading {
                          METRIC_CONFIG[
                            overviewMetricType
                          ].label
                        }…
                      </div>
                    )}

                    {!overviewLoading
                      && overviewError && (
                        <div className="home-inline-status error">
                          {overviewError}
                        </div>
                      )}

                    {filteredFields.length > 0
                      ? (
                        <div className="home-fields-grid">
                          {filteredFields.map(
                            (
                              field,
                            ) => {
                              const crop =
                                chooseFieldCropCycle(
                                  field.id,
                                  seasonCropCycles,
                                );

                              const item =
                                overviewByField
                                  .get(
                                    field.id,
                                  );

                              return (
                                <button
                                  key={
                                    field.id
                                  }
                                  className="field-grid-card"
                                  onClick={
                                    () =>
                                      setSelectedFieldId(
                                        field.id,
                                      )
                                  }
                                >
                                  <div className="field-grid-preview">
                                    <FieldBoundaryPreview
                                      boundary={
                                        field.boundary
                                      }
                                      imageUrl={
                                        item
                                          ? buildMetricPreviewUrl(
                                              TILER_URL,
                                              item.metric,
                                              420,
                                            )
                                          : null
                                      }
                                    />

                                    <span className="field-grid-area">
                                      {field.area_acres.toFixed(
                                        2,
                                      )}
                                      {" ac"}
                                    </span>
                                  </div>

                                  <div className="field-grid-card-body">
                                    <div className="field-grid-card-title">
                                      <div>
                                        <h3>
                                          {field.name}
                                        </h3>

                                        <p>
                                          {crop
                                            ? (
                                              <>
                                                {crop.crop_name}
                                                {crop.variety
                                                  ? ` · ${crop.variety}`
                                                  : ""}
                                              </>
                                            )
                                            : "No crop assigned for this season"}
                                        </p>
                                      </div>

                                      <div className="field-grid-card-metric">
                                        <span>
                                          {
                                            METRIC_CONFIG[
                                              overviewMetricType
                                            ].label
                                          }
                                        </span>

                                        <strong>
                                          {item
                                            ? formatMetricValue(
                                                item.metric.median,
                                                overviewMetricType
                                                  === "lst_c"
                                                  ? 1
                                                  : 2,
                                              )
                                            : "—"}
                                        </strong>
                                      </div>
                                    </div>

                                    <div className="field-grid-card-footer">
                                      <span>
                                        {item
                                          ? (
                                            <>
                                              {formatOverviewDate(
                                                item.observed_on,
                                              )}
                                              {" · "}
                                              {formatSource(
                                                item.source,
                                              )}
                                            </>
                                          )
                                          : `No ${METRIC_CONFIG[
                                              overviewMetricType
                                            ].label} data`}
                                      </span>

                                      <span>
                                        Open field
                                      </span>
                                    </div>
                                  </div>
                                </button>
                              );
                            },
                          )}
                        </div>
                      )
                      : (
                        <div className="home-fields-empty">
                          <FieldBoundaryPreview
                            boundary={{
                              type:
                                "Polygon",
                              coordinates: [
                                [
                                  [0, 0],
                                  [1.2, 0.1],
                                  [1.05, 0.8],
                                  [0.25, 1],
                                  [0, 0],
                                ],
                              ],
                            }}
                          />

                          <h2>
                            {fields.length === 0
                              ? "No fields yet"
                              : "No fields found"}
                          </h2>

                          <p>
                            {fields.length === 0
                              ? "Draw your first field boundary to start monitoring it."
                              : "Try a different field name."}
                          </p>

                          {fields.length === 0 && (
                            <button
                              className="home-action primary"
                              onClick={
                                handleStartDrawing
                              }
                            >
                              <MapPin
                                size={15}
                              />
                              Add field
                            </button>
                          )}
                        </div>
                      )}
                  </div>
                )}

            {selectedFarmId
              && homeView
                === "map" && (
                  <div className="home-map-pane">
                    <FarmOverviewMap
                      mapMode={
                        mapMode
                      }
                      fields={
                        fields
                      }
                      overview={
                        overview
                      }
                      selectedMetricType={
                        overviewMetricType
                      }
                      drawing={
                        drawing
                      }
                      onSelectField={(
                        fieldId,
                      ) => {
                        setDrawing(
                          false,
                        );

                        setPendingBoundary(
                          null,
                        );

                        setSelectedFieldId(
                          fieldId,
                        );
                      }}
                      onPolygonFinished={(
                        boundary,
                      ) => {
                        setDrawing(
                          false,
                        );

                        setPendingBoundary(
                          boundary,
                        );
                      }}
                    />

                    <div className="home-map-legend">
                      <div
                        className="home-map-gradient"
                        style={{
                          background:
                            METRIC_CONFIG[
                              overviewMetricType
                            ].gradient,
                        }}
                      />

                      <div>
                        <span>
                          {
                            METRIC_CONFIG[
                              overviewMetricType
                            ].label
                          }
                        </span>

                        <small>
                          {
                            METRIC_CONFIG[
                              overviewMetricType
                            ].displayMin
                          }
                          {" → "}
                          {
                            METRIC_CONFIG[
                              overviewMetricType
                            ].displayMax
                          }
                        </small>
                      </div>
                    </div>

                    {overviewLoading && (
                      <div className="home-map-status">
                        Loading {
                          METRIC_CONFIG[
                            overviewMetricType
                          ].label
                        }…
                      </div>
                    )}

                    {!overviewLoading
                      && overviewError && (
                        <div className="home-map-status error">
                          {overviewError}
                        </div>
                      )}

                    {drawing && (
                      <div className="home-drawing-banner">
                        <div>
                          <strong>
                            Draw the field boundary
                          </strong>

                          <span>
                            Click around the field and close the polygon at
                            the first point.
                          </span>
                        </div>

                        <button
                          onClick={
                            handleCancelDrawing
                          }
                        >
                          Cancel
                        </button>
                      </div>
                    )}
                  </div>
                )}
          </div>
        </section>

        {selectedFarm
          && selectedField && (
            <FieldDetailsPanel
              key={
                `${selectedField.id}-${selectedSeasonId ?? "none"}`
              }
              farm={
                selectedFarm
              }
              field={
                selectedField
              }
              season={
                selectedSeason
              }
              cropCycle={
                selectedCropCycle
              }
              onDataChanged={
                async () => {
                  await refreshSeasonCropCycles();

                  if (
                    selectedFarmId
                  ) {
                    await loadOverview(
                      selectedFarmId,
                      overviewMetricType,
                      overviewDate,
                    );
                  }
                }
              }
              onClose={
                () =>
                  setSelectedFieldId(
                    null,
                  )
              }
            />
          )}
      </main>

      {createFarmOpen && (
        <CreateFarmDialog
          onClose={
            () =>
              setCreateFarmOpen(
                false,
              )
          }
          onCreate={
            handleCreateFarm
          }
        />
      )}

      {createSeasonOpen && (
        <CreateSeasonDialog
          onClose={
            () =>
              setCreateSeasonOpen(
                false,
              )
          }
          onCreate={
            handleCreateSeason
          }
        />
      )}

      {pendingBoundary && (
        <CreateFieldDialog
          boundary={
            pendingBoundary
          }
          onClose={
            () => {
              setPendingBoundary(
                null,
              );

              setDrawing(
                false,
              );
            }
          }
          onCreate={
            handleCreateField
          }
        />
      )}

      {error && (
        <div className="error-toast">
          <span>
            {error}
          </span>

          <button
            onClick={
              () =>
                setError(
                  null,
                )
            }
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}
