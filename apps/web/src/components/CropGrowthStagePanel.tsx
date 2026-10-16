import { useEffect, useState } from "react";

import { deleteCropGrowthStage, recordCropGrowthStage } from "../lib/api";
import type { CropCycle, CropGrowth } from "../types/api";


type Props = {
  cropCycle: CropCycle;
  growth: CropGrowth | null;
  loading: boolean;
  error: string | null;
  onChanged: () => Promise<void>;
};

function displayDate(value: string) {
  return new Date(value.slice(0, 10) + "T00:00:00Z").toLocaleDateString(
    "en-IN", { day: "2-digit", month: "short", year: "numeric" },
  );
}

export default function CropGrowthStagePanel({
  cropCycle, growth, loading, error, onChanged,
}: Props) {
  const [stageCode, setStageCode] = useState("");
  const [observedOn, setObservedOn] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    setStageCode("");
    setObservedOn("");
    setNotes("");
    setSaveError(null);
  }, [cropCycle.id]);

  const stages = growth?.stages ?? [];
  const selectedStage = stageCode || stages[0]?.code || "";
  const existing = growth?.observations.find((stage) => stage.stage_code === selectedStage);

  async function saveStage() {
    if (!growth || !selectedStage || !observedOn || busy) return;
    setBusy(true);
    setSaveError(null);
    try {
      await recordCropGrowthStage(cropCycle.id, {
        stage_code: selectedStage,
        observed_on: observedOn,
        notes: notes.trim() || null,
      });
      await onChanged();
      setObservedOn("");
      setNotes("");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Could not save stage.");
    } finally {
      setBusy(false);
    }
  }

  async function removeStage(code: string) {
    if (busy) return;
    setBusy(true);
    setSaveError(null);
    try {
      await deleteCropGrowthStage(cropCycle.id, code);
      await onChanged();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Could not remove stage.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="crop-growth-panel">
      <div className="crop-growth-heading">
        <div>
          <span className="workspace-eyebrow">CROP DEVELOPMENT</span>
          <h4>Growth stages · {cropCycle.crop_name}</h4>
          <p>
            Record what you actually see in the field. Approximate calendar phases are
            planning context only and do not confirm development or health.
          </p>
        </div>
        <span className="crop-growth-version">
          {growth ? "Template " + growth.profile_version : "Stage diary"}
        </span>
      </div>

      {loading && <p className="crop-growth-message">Loading crop development…</p>}
      {!loading && error && (
        <p className="crop-growth-message error">
          Crop development could not be loaded: {error}
        </p>
      )}

      {!loading && !error && growth && (
        <>
          <div className="crop-growth-summary">
            <div>
              <span>Days since planting</span>
              <strong>{growth.days_after_planting ?? "—"}</strong>
              <small>{growth.planting_date ? "From " + displayDate(growth.planting_date) : "Planting date not recorded"}</small>
            </div>
            <div>
              <span>{cropCycle.harvested_on ? "Last recorded stage before harvest" : "Farmer-confirmed stage"}</span>
              <strong>
                {stages.find((stage) => stage.code === growth.latest_recorded_stage)?.label ?? "Not recorded"}
              </strong>
              <small>{growth.observations.length} confirmed transitions</small>
            </div>
            <div>
              <span>{cropCycle.harvested_on ? "Final crop status" : "Approximate calendar stage"}</span>
              <strong>
                {cropCycle.harvested_on ? "Harvested" :
                  stages.find((stage) => stage.code === growth.provisional_stage)?.label ?? "Unknown"}
              </strong>
              <small>{cropCycle.harvested_on
                ? "Harvest recorded " + displayDate(cropCycle.harvested_on)
                : "Unverified template estimate"}</small>
            </div>
            <div>
              <span>Accumulated growing degree days</span>
              <strong>
                {growth.accumulated_gdd_c_days == null
                  ? "Unavailable"
                  : growth.accumulated_gdd_c_days.toFixed(0) + " °C·days"}
              </strong>
              <small>
                {growth.degree_day_base_c == null
                  ? "Crop-specific base not set"
                  : "Base " + growth.degree_day_base_c + " °C · " +
                    growth.gdd_days_available + "/" + growth.gdd_days_expected + " days"}
              </small>
            </div>
          </div>

          <div className="crop-growth-stage-track" role="list" aria-label="Crop growth stages">
            {stages.map((stage) => {
              const observation = growth.observations.find((item) => item.stage_code === stage.code);
              const estimated = growth.provisional_stage === stage.code;
              const current = !cropCycle.harvested_on && growth.latest_recorded_stage === stage.code;
              return (
                <div
                  key={stage.code}
                  role="listitem"
                  className={
                    "crop-growth-milestone" +
                    (observation ? " confirmed" : estimated ? " provisional" : "") +
                    (current ? " current" : "")
                  }
                >
                  <span className="crop-growth-dot" />
                  <strong>{stage.label}</strong>
                  {stage.bbch_reference && <small>BBCH reference {stage.bbch_reference} · not verified</small>}
                  <small>
                    {observation
                      ? displayDate(observation.observed_on) + " · Recorded"
                      : stage.approx_days_after_planting == null
                        ? "Not dated"
                        : "~Day " + stage.approx_days_after_planting + " · Guide only"}
                  </small>
                </div>
              );
            })}
          </div>

          <div className="crop-growth-record">
            <div>
              <h5>Record or correct a stage</h5>
              <p>Use the date you first observed it. You can revise or remove a record later.</p>
            </div>
            <div className="crop-growth-form">
              <label>
                <span>Stage</span>
                <select
                  value={selectedStage}
                  onChange={(event) => {
                    const nextCode = event.currentTarget.value;
                    const prior = growth.observations.find((item) => item.stage_code === nextCode);
                    setStageCode(nextCode);
                    setObservedOn(prior?.observed_on ?? "");
                    setNotes(prior?.notes ?? "");
                  }}
                >
                  {stages.map((stage) => (
                    <option key={stage.code} value={stage.code}>{stage.label}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Date observed</span>
                <input
                  type="date"
                  value={observedOn}
                  min={cropCycle.planted_on || cropCycle.started_on}
                  max={growth.as_of}
                  onChange={(event) => setObservedOn(event.currentTarget.value)}
                />
              </label>
              <label className="crop-growth-notes">
                <span>Notes (optional)</span>
                <input
                  value={notes}
                  maxLength={2000}
                  placeholder="Field observations"
                  onChange={(event) => setNotes(event.currentTarget.value)}
                />
              </label>
              <button type="button" disabled={busy || !observedOn} onClick={() => void saveStage()}>
                {busy ? "Saving…" : existing ? "Update stage" : "Record stage"}
              </button>
            </div>
            {saveError && <p className="crop-growth-message error">{saveError}</p>}
          </div>

          {growth.observations.length > 0 && (
            <div className="crop-growth-confirmed-list">
              <h5>Confirmed field observations</h5>
              {growth.observations.map((observation) => (
                <div key={observation.id}>
                  <span>{displayDate(observation.observed_on)} · {stages.find((stage) => stage.code === observation.stage_code)?.label ?? observation.stage_code}</span>
                  {observation.notes && <small>{observation.notes}</small>}
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      setStageCode(observation.stage_code);
                      setObservedOn(observation.observed_on);
                      setNotes(observation.notes ?? "");
                    }}
                  >
                    Edit
                  </button>
                  <button type="button" disabled={busy} onClick={() => void removeStage(observation.stage_code)}>
                    Remove
                  </button>
                </div>
              ))}
            </div>
          )}
          <p className="crop-growth-disclaimer">
            GDD uses modeled/reanalysis air temperature where every day is covered.
            A calendar estimate is never labeled as a verified field observation.
            Crop-stage-aware radar anomaly classification is not enabled.
          </p>
          {growth.warnings.map((warning) => <p className="crop-growth-warning" key={warning}>{warning}</p>)}
        </>
      )}
    </section>
  );
}
