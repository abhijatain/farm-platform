import {
  Plus,
  Search,
  SlidersHorizontal,
} from "lucide-react";

import {
  useMemo,
  useState,
} from "react";

import type {
  CropCycle,
  Farm,
  Field,
  Season,
} from "../types/api";


type Props = {
  farms: Farm[];

  selectedFarmId:
    string | null;

  seasons: Season[];

  selectedSeasonId:
    string | null;

  fields: Field[];

  cropCycles:
    CropCycle[];

  selectedFieldId:
    string | null;

  onFarmChange:
    (farmId: string) => void;

  onSeasonChange:
    (seasonId: string) => void;

  onSelectField:
    (fieldId: string) => void;

  onAddFarm:
    () => void;

  onAddSeason:
    () => void;

  onAddField:
    () => void;
};


function getFieldCropCycle(
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


export default function FieldsSidebar({
  farms,
  selectedFarmId,
  seasons,
  selectedSeasonId,
  fields,
  cropCycles,
  selectedFieldId,
  onFarmChange,
  onSeasonChange,
  onSelectField,
  onAddFarm,
  onAddSeason,
  onAddField,
}: Props) {
  const [
    query,
    setQuery,
  ] = useState("");


  const filtered =
    fields.filter(
      (field) =>
        field.name
          .toLowerCase()
          .includes(
            query.toLowerCase(),
          ),
    );


  const totalHa =
    useMemo(
      () =>
        fields.reduce(
          (
            total,
            field,
          ) =>
            total +
            field.area_hectares,

          0,
        ),

      [fields],
    );


  return (
    <aside className="fields-sidebar">

      <header className="sidebar-header">

        <div className="sidebar-top-row">

          <select
            className="farm-picker"

            value={
              selectedFarmId ?? ""
            }

            onChange={(event) =>
              onFarmChange(
                event.target.value,
              )
            }
          >

            {farms.length === 0 && (
              <option value="">
                No farms
              </option>
            )}


            {farms.map(
              (farm) => (
                <option
                  key={farm.id}
                  value={farm.id}
                >
                  {farm.name}
                </option>
              ),
            )}

          </select>


          <button
            className="text-button compact"

            onClick={onAddFarm}
          >
            + Farm
          </button>

        </div>


        <div className="season-row">

          <span className="season-label">
            Season
          </span>


          <select
            className="season-picker"

            value={
              selectedSeasonId ?? ""
            }

            disabled={
              seasons.length === 0
            }

            onChange={(event) => {
              const value =
                event.target.value;

              if (value) {
                onSeasonChange(
                  value,
                );
              }
            }}
          >

            {seasons.length === 0 && (
              <option value="">
                No season
              </option>
            )}


            {seasons.map(
              (season) => (
                <option
                  key={season.id}
                  value={season.id}
                >
                  {season.name}
                </option>
              ),
            )}

          </select>


          <button
            className="season-add-button"

            onClick={onAddSeason}

            disabled={!selectedFarmId}

            title="Create season"
          >
            <Plus size={16} />
            New
          </button>

        </div>

      </header>


      <div className="sidebar-search">

        <Search size={17} />

        <input
          placeholder="Search fields"

          value={query}

          onChange={(event) =>
            setQuery(
              event.target.value,
            )
          }
        />

        <SlidersHorizontal
          size={17}
        />

      </div>


      <div className="fields-heading">

        <div>

          <strong>
            Fields
          </strong>

          <span>
            {totalHa.toFixed(2)}
            {" ha"}
          </span>

        </div>


        <button
          className="small-icon-button"

          onClick={onAddField}

          title="Add field"
        >
          <Plus size={19} />
        </button>

      </div>


      <div className="field-list">

        {filtered.map(
          (field) => {
            const cropCycle =
              getFieldCropCycle(
                field.id,
                cropCycles,
              );


            return (
              <button
                key={field.id}

                className={
                  field.id ===
                  selectedFieldId
                    ? "field-card selected"
                    : "field-card"
                }

                onClick={() =>
                  onSelectField(
                    field.id,
                  )
                }
              >

                <div className="field-thumbnail">

                  <div className="mini-boundary" />

                </div>


                <div className="field-details">

                  <strong>
                    {field.name}
                  </strong>


                  <span>
                    {field.area_hectares.toFixed(2)}
                    {" ha · "}
                    {field.area_acres.toFixed(2)}
                    {" acres"}
                  </span>


                  {selectedSeasonId ? (
                    cropCycle ? (

                      <span className="field-crop">

                        {cropCycle.crop_name}

                        {cropCycle.variety
                          ? ` · ${cropCycle.variety}`
                          : ""}

                      </span>

                    ) : (

                      <span className="field-crop empty">

                        No crop in this season

                      </span>

                    )
                  ) : (

                    <span className="field-crop empty">

                      Select a season

                    </span>

                  )}

                </div>

              </button>
            );
          },
        )}


        {filtered.length === 0 && (
          <div className="empty-sidebar">

            No fields yet.

          </div>
        )}

      </div>


      <button
        className="add-field-button"

        onClick={onAddField}
      >
        <Plus size={20} />

        Add field
      </button>

    </aside>
  );
}
