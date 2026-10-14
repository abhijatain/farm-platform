import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  Layers3,
  Satellite,
} from "lucide-react";

import NavRail
  from "./NavRail";

import FieldsSidebar
  from "./FieldsSidebar";

import FarmMap
  from "./FarmMap";

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
  listFarms,
  listFields,
  listSeasons,
  listSeasonCropCycles,
} from "../lib/api";

import type {
  CropCycle,
  Farm,
  Field,
  PolygonGeometry,
  Season,
} from "../types/api";

import type {
  MapMode,
} from "../types/map";


function chooseDefaultSeason(
  seasons: Season[],
) {
  if (seasons.length === 0) {
    return null;
  }


  const active =
    seasons.find(
      (season) =>
        season.status ===
        "active",
    );


  if (active) {
    return active;
  }


  const sorted =
    [...seasons].sort(
      (a, b) =>
        new Date(
          b.started_on,
        ).getTime()
        -
        new Date(
          a.started_on,
        ).getTime(),
    );


  return sorted[0] ?? null;
}


function chooseFieldCropCycle(
  fieldId: string,
  cropCycles: CropCycle[],
) {
  const matching =
    cropCycles
      .filter(
        (cycle) =>
          cycle.field_id === fieldId,
      )
      .sort((a, b) => {
        if (
          a.status === "active" &&
          b.status !== "active"
        ) {
          return -1;
        }

        if (
          b.status === "active" &&
          a.status !== "active"
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
      });


  return matching[0] ?? null;
}


export default function FarmWorkspace() {
  const [
    farms,
    setFarms,
  ] = useState<Farm[]>([]);


  const [
    selectedFarmId,
    setSelectedFarmId,
  ] = useState<string | null>(
    null,
  );


  const [
    fields,
    setFields,
  ] = useState<Field[]>([]);


  const [
    seasons,
    setSeasons,
  ] = useState<Season[]>([]);


  const [
    selectedSeasonId,
    setSelectedSeasonId,
  ] = useState<string | null>(
    null,
  );


  const [
    seasonCropCycles,
    setSeasonCropCycles,
  ] = useState<CropCycle[]>([]);


  const [
    selectedFieldId,
    setSelectedFieldId,
  ] = useState<string | null>(
    null,
  );


  const [
    mapMode,
    setMapMode,
  ] = useState<MapMode>(
    "hybrid",
  );


  const [
    drawing,
    setDrawing,
  ] = useState(false);


  const [
    createFarmOpen,
    setCreateFarmOpen,
  ] = useState(false);


  const [
    createSeasonOpen,
    setCreateSeasonOpen,
  ] = useState(false);


  const [
    pendingBoundary,
    setPendingBoundary,
  ] = useState<
    PolygonGeometry | null
  >(null);


  const [
    error,
    setError,
  ] = useState<string | null>(
    null,
  );


  const selectedFarmIdRef =
    useRef<string | null>(
      selectedFarmId,
    );

  const farmContextRequestRef =
    useRef(0);

  const seasonCropCyclesRequestRef =
    useRef(0);

  selectedFarmIdRef.current =
    selectedFarmId;


  async function loadFarms() {
    try {
      setError(null);

      const result =
        await listFarms();

      setFarms(result);


      if (
        result.length === 0
      ) {
        setSelectedFarmId(
          null,
        );

        return;
      }


      setSelectedFarmId(
        (current) => {
          if (
            current &&
            result.some(
              (farm) =>
                farm.id === current,
            )
          ) {
            return current;
          }

          return result[0].id;
        },
      );

    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to load farms.",
      );
    }
  }


  async function loadFarmContext(
    farmId: string,
  ) {
    const requestId =
      ++farmContextRequestRef.current;

    try {
      setError(null);


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
        requestId !==
          farmContextRequestRef.current
        ||
        selectedFarmIdRef.current !==
          farmId
      ) {
        return;
      }


      setFields(
        nextFields,
      );

      setSeasons(
        nextSeasons,
      );


      /*
       * Switching farms should close
       * the old selected field.
       */
      setSelectedFieldId(
        null,
      );


      /*
       * Pick active season if available,
       * otherwise newest season.
       */
      const defaultSeason =
        chooseDefaultSeason(
          nextSeasons,
        );


      setSelectedSeasonId(
        defaultSeason?.id
        ?? null,
      );

    } catch (error) {
      if (
        requestId !==
          farmContextRequestRef.current
        ||
        selectedFarmIdRef.current !==
          farmId
      ) {
        return;
      }

      setError(
        error instanceof Error
          ? error.message
          : "Unable to load farm.",
      );
    }
  }


  async function refreshFields() {
    if (!selectedFarmId) {
      return;
    }


    const result =
      await listFields(
        selectedFarmId,
      );


    setFields(result);
  }


  async function refreshSeasons(
    preferredSeasonId?:
      string,
  ) {
    if (!selectedFarmId) {
      return;
    }


    const result =
      await listSeasons(
        selectedFarmId,
      );


    setSeasons(result);


    if (
      preferredSeasonId &&
      result.some(
        (season) =>
          season.id ===
          preferredSeasonId,
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
      ++seasonCropCyclesRequestRef.current;

    const id =
      seasonId
      ?? selectedSeasonId;


    if (!id) {
      setSeasonCropCycles([]);

      return;
    }


    try {
      const result =
        await listSeasonCropCycles(
          id,
        );


      if (
        requestId !==
        seasonCropCyclesRequestRef.current
      ) {
        return;
      }


      setSeasonCropCycles(
        result,
      );

    } catch (error) {
      if (
        requestId !==
        seasonCropCyclesRequestRef.current
      ) {
        return;
      }

      setError(
        error instanceof Error
          ? error.message
          : "Unable to load crop cycles.",
      );
    }
  }


  /*
   * Initial load.
   */
  useEffect(() => {
    void loadFarms();
  }, []);


  /*
   * Farm changed.
   */
  useEffect(() => {
    if (!selectedFarmId) {
      farmContextRequestRef.current += 1;
      seasonCropCyclesRequestRef.current += 1;

      setFields([]);
      setSeasons([]);
      setSeasonCropCycles([]);
      setSelectedSeasonId(
        null,
      );

      return;
    }


    setDrawing(false);
    setPendingBoundary(null);

    void loadFarmContext(
      selectedFarmId,
    );

  }, [
    selectedFarmId,
  ]);


  /*
   * Season changed.
   *
   * This is what causes crop names
   * beside each field to change.
   */
  useEffect(() => {
    seasonCropCyclesRequestRef.current += 1;

    setSeasonCropCycles([]);


    if (
      selectedSeasonId
    ) {
      void refreshSeasonCropCycles(
        selectedSeasonId,
      );
    }

  }, [
    selectedSeasonId,
  ]);


  const selectedFarm =
    useMemo(
      () =>
        farms.find(
          (farm) =>
            farm.id ===
            selectedFarmId,
        ) ?? null,

      [
        farms,
        selectedFarmId,
      ],
    );


  const selectedSeason =
    useMemo(
      () =>
        seasons.find(
          (season) =>
            season.id ===
            selectedSeasonId,
        ) ?? null,

      [
        seasons,
        selectedSeasonId,
      ],
    );


  const selectedField =
    useMemo(
      () =>
        fields.find(
          (field) =>
            field.id ===
            selectedFieldId,
        ) ?? null,

      [
        fields,
        selectedFieldId,
      ],
    );


  const selectedCropCycle =
    useMemo(
      () => {
        if (!selectedFieldId) {
          return null;
        }


        return chooseFieldCropCycle(
          selectedFieldId,
          seasonCropCycles,
        );
      },

      [
        selectedFieldId,
        seasonCropCycles,
      ],
    );


  async function handleCreateFarm(
    name: string,
    location:
      string | null,
  ) {
    try {
      setError(null);


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

    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to create farm.",
      );

      throw error;
    }
  }


  async function handleCreateSeason(
    name: string,
    seasonType:
      string | null,
    startedOn: string,
  ) {
    if (!selectedFarmId) {
      throw new Error(
        "Select a farm first.",
      );
    }


    try {
      setError(null);


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

    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to create season.",
      );

      throw error;
    }
  }


  async function handleCreateField(
    name: string,
  ) {
    if (
      !selectedFarmId ||
      !pendingBoundary
    ) {
      return;
    }


    try {
      setError(null);


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


      setSelectedFieldId(
        field.id,
      );


      setPendingBoundary(
        null,
      );

      setDrawing(false);

    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to create field.",
      );

      throw error;
    }
  }


  function handleStartDrawing() {
    if (!selectedFarmId) {
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

    setDrawing(
      true,
    );
  }


  function handleCancelDrawing() {
    setDrawing(false);

    setPendingBoundary(
      null,
    );
  }


  return (
    <div className="app-shell">

      <NavRail />


      <FieldsSidebar
        farms={farms}

        selectedFarmId={
          selectedFarmId
        }

        seasons={seasons}

        selectedSeasonId={
          selectedSeasonId
        }

        fields={fields}

        cropCycles={
          seasonCropCycles
        }

        selectedFieldId={
          selectedFieldId
        }

        onFarmChange={(farmId) => {
          setSelectedFarmId(
            farmId,
          );
        }}

        onSeasonChange={(
          seasonId,
        ) => {
          setSelectedSeasonId(
            seasonId,
          );
        }}

        onSelectField={(
          fieldId,
        ) => {
          setDrawing(false);

          setPendingBoundary(
            null,
          );

          setSelectedFieldId(
            fieldId,
          );
        }}

        onAddFarm={() =>
          setCreateFarmOpen(
            true,
          )
        }

        onAddSeason={() =>
          setCreateSeasonOpen(
            true,
          )
        }

        onAddField={
          handleStartDrawing
        }
      />


      <main className="map-workspace">

        <FarmMap
          mapMode={
            mapMode
          }

          fields={fields}

          selectedFieldId={
            selectedFieldId
          }

          drawing={drawing}

          onSelectField={(
            fieldId,
          ) => {
            setDrawing(false);

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
            setDrawing(false);

            setPendingBoundary(
              boundary,
            );
          }}
        />


        <div className="layer-switcher">

          <button
            className={
              mapMode ===
              "streets"
                ? "layer-button active"
                : "layer-button"
            }

            onClick={() =>
              setMapMode(
                "streets",
              )
            }
          >
            <Layers3 size={17} />

            Map
          </button>


          <button
            className={
              mapMode ===
              "hybrid"
                ? "layer-button active"
                : "layer-button"
            }

            onClick={() =>
              setMapMode(
                "hybrid",
              )
            }
          >
            <Satellite size={17} />

            Satellite
          </button>

        </div>


        {drawing && (
          <div className="drawing-message">

            <strong>
              Draw field
            </strong>


            <span>
              Click around the field
              boundary. Click the first
              point again to finish.
            </span>


            <button
              onClick={
                handleCancelDrawing
              }
            >
              Cancel
            </button>

          </div>
        )}


        {selectedFarm &&
          selectedField && (

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

            onDataChanged={async () => {
              await refreshSeasonCropCycles();
            }}

            onClose={() =>
              setSelectedFieldId(
                null,
              )
            }
          />

        )}

      </main>


      {createFarmOpen && (
        <CreateFarmDialog
          onClose={() =>
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
          onClose={() =>
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

          onClose={() => {
            setPendingBoundary(
              null,
            );

            setDrawing(false);
          }}

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
            onClick={() =>
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
