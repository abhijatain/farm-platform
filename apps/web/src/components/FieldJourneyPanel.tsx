import { useEffect, useMemo, useState } from "react";
import FieldJourneyExplorer from "./FieldJourneyExplorer";
import type { CropCycle, CropGrowth, Field, Season, TimelineItem, SatelliteObservation } from "../types/api";
import { getCropGrowthStages, updateCropCyclePlan } from "../lib/api";
import { localDateInputValue } from "../lib/dates";
import "./FieldJourneyPanel.css";

type Props = {
  field: Field;
  season: Season | null;
  cycle: CropCycle | null;
  cycles: CropCycle[];
  timeline: TimelineItem[];
  loading: boolean;
  satelliteObservations: SatelliteObservation[];
  satelliteLoading: boolean;
  satelliteError: string | null;
  onSelectCycle: (id: string) => void;
  onStart: () => void;
  onActivity: () => void;
  onHarvest: () => void;
  onGrowth: () => void;
  onTrends: () => void;
  onHistory: () => void;
  onSaved: () => Promise<void>;
};

function daysBetween(a: string, b: string): number {
  return Math.round((Date.parse(b.slice(0,10) + "T00:00:00Z") -
    Date.parse(a.slice(0,10) + "T00:00:00Z")) / 86400000);
}
function pretty(value: string | null | undefined) {
  if (!value) return "Not recorded";
  const timestamp = value.includes("T");
  return new Date(timestamp ? value : value.slice(0,10) + "T00:00:00Z").toLocaleDateString("en-IN",{
    day:"numeric",month:"short",year:"numeric", ...(timestamp ? {} : {timeZone:"UTC"}),
  });
}
function activityName(code: string) {
  const names: Record<string,string> = {
    tillage:"Tractor / tillage", land_preparation:"Field preparation",
    sowing:"Sowing", planting:"Planting", transplanting:"Transplanting",
    irrigation:"Irrigation", fertilizer:"Fertilizer", herbicide:"Herbicide",
    pesticide:"Pesticide", fungicide:"Fungicide", weeding:"Weeding",
    harvest:"Harvest",
  };
  return names[code] ?? code.replace(/_/g," ").replace(/^./, c => c.toUpperCase());
}

export default function FieldJourneyPanel({
  field,season,cycle,cycles,timeline,loading,
  satelliteObservations,satelliteLoading,satelliteError,onSelectCycle,
  onStart,onActivity,onHarvest,onGrowth,onTrends,onHistory,onSaved,
}: Props) {
  const [growth, setGrowth] = useState<CropGrowth | null>(null);
  const [growthError, setGrowthError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [plantedOn, setPlantedOn] = useState("");
  const [expectedOn, setExpectedOn] = useState("");
  const [busy, setBusy] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const today = localDateInputValue();

  useEffect(() => {
    let alive = true;
    setGrowth(null);
    setGrowthError(null);
    setEditing(false);
    setPlantedOn(cycle?.planted_on ?? "");
    setExpectedOn(cycle?.expected_harvest_on ?? "");
    if (!cycle) return;
    void getCropGrowthStages(cycle.id).then(data => {
      if (alive) setGrowth(data);
    }).catch((error: unknown) => {
      if (alive) setGrowthError(error instanceof Error ? error.message : "Crop-stage data unavailable.");
    });
    return () => { alive = false; };
  }, [cycle?.id,cycle?.planted_on,cycle?.expected_harvest_on]);

  const cycleActivities = useMemo(() =>
    timeline.filter(entry => entry.crop_cycle_id === cycle?.id)
      .sort((a,b) => a.occurred_at.localeCompare(b.occurred_at)),
    [timeline,cycle?.id]);
  const firstPreparation = cycleActivities.find(a =>
    ["tillage","land_preparation","ploughing","leveling","field_preparation"].includes(a.activity_type)
    && (!cycle?.planted_on || a.occurred_at.slice(0,10) <= cycle.planted_on));
  const prepDate = firstPreparation?.occurred_at.slice(0,10) ?? cycle?.started_on;
  const prepDays = cycle?.planted_on && prepDate ? Math.max(0,daysBetween(prepDate,cycle.planted_on)) : null;
  const asOf = cycle?.harvested_on ?? today;
  const age = cycle?.planted_on && asOf >= cycle.planted_on
    ? Math.max(0, daysBetween(cycle.planted_on,asOf)) : null;
  const toHarvest = cycle?.expected_harvest_on && cycle.status === "active"
    ? daysBetween(today,cycle.expected_harvest_on) : null;
  const currentStage = growth?.latest_recorded_stage ?? growth?.provisional_stage ?? null;
  const stage = growth?.stages.find(item=>item.code === currentStage);
  const isConfirmed = Boolean(growth?.latest_recorded_stage);
  const milestones = [
    {name:"Prepare",complete:cycleActivities.some(a=>["tillage","land_preparation","ploughing","leveling"].includes(a.activity_type)),
      description:"Tractor work, leveling and soil preparation"},
    {name:"Plant",complete:cycle?.planted_on != null,description:"Record sowing or transplanting date"},
    {name:"Grow",complete:cycle?.planted_on != null,
      description:"Daily field work, crop stages and satellite trends"},
    {name:"Harvest",complete:cycle?.harvested_on != null,description:"Record actual yield to close this cycle"},
  ];
  async function savePlan() {
    if (!cycle || busy) return;
    setEditError(null);
    if (plantedOn && plantedOn < cycle.started_on) {
      setEditError("Planting cannot be before the cycle's preparation/start date.");
      return;
    }
    if (expectedOn && expectedOn < (plantedOn || cycle.started_on)) {
      setEditError("Expected harvest must follow planting or preparation.");
      return;
    }
    try {
      setBusy(true);
      await updateCropCyclePlan(cycle.id,{
        planted_on: plantedOn || null,expected_harvest_on:expectedOn || null,
      });
      await onSaved();
      setEditing(false);
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Unable to update crop plan.");
    } finally { setBusy(false); }
  }
  return <div className="workspace-page journey-page">
    <header className="journey-intro">
      <div>
        <span className="workspace-eyebrow">YOUR FIELD, FROM START TO HARVEST</span>
        <h2>{cycle ? `${cycle.crop_name} · ${field.name}` : `Begin with ${field.name}`}</h2>
        <p>{cycle ? "Every crop has its own preparation, planting, activities, growth measurements and eventual harvest." :
          "First create a farm and season, then choose a crop for this field. You can start preparing before it is planted."}</p>
      </div>
      {season && <button className="primary-action" type="button" onClick={onStart}>+ Start another crop</button>}
    </header>
    {cycles.length > 0 && <label className="journey-cycle-picker">
      <span>Crop cycle</span>
      <select value={cycle?.id ?? ""} onChange={e=>onSelectCycle(e.target.value)}>
        {cycles.map(item=><option value={item.id} key={item.id}>
          {item.crop_name}{item.variety ? " · " + item.variety : ""} · {pretty(item.started_on)}
          {item.status === "completed" ? " · harvested" : " · active"}
        </option>)}
      </select>
    </label>}
    {!cycle ? <div className="journey-empty">
      <h3>{season ? "Choose your next crop" : "Create a season to get started"}</h3>
      <p>{season ? "Your first record can be field preparation by tractor. Planting and its date can be added later." :
        "Create a farm season from the field list first. Each crop cycle belongs to that farm season."}</p>
      {season && <button type="button" className="primary-action" onClick={onStart}>Start crop plan</button>}
    </div> : <>
      <FieldJourneyExplorer
        field={field} cycle={cycle} observations={satelliteObservations}
        activities={cycleActivities} loading={satelliteLoading}
        error={satelliteError}
      />
      <div className="journey-progress" aria-label="Crop cycle progress">
        {milestones.map((step,index)=><div className={"journey-step "+(step.complete?"done":"")} key={step.name}>
          <span className="journey-step-number">{step.complete?"✓":index+1}</span>
          <strong>{step.name}</strong><small>{step.description}</small>
        </div>)}
      </div>
      <div className="journey-facts">
        <article><span>Field preparation</span><strong>{prepDays==null?"In progress":prepDays+" days"}</strong>
          <small>{firstPreparation ? "From first recorded tractor/preparation work" : "From crop-cycle start"}
            {cycle.planted_on ? " to planting" : " · ends when planted"}</small></article>
        <article><span>{cycle.harvested_on ? "Age at harvest" : "Crop age"}</span><strong>{age==null?"Not planted":age+" days"}</strong>
          <small>{cycle.planted_on ? "Planted " + pretty(cycle.planted_on) : "Record sowing/transplanting to start the clock"}</small></article>
        <article><span>{cycle.harvested_on ? "Harvested" : "Expected harvest"}</span>
          <strong>{cycle.harvested_on ? pretty(cycle.harvested_on) :
            toHarvest==null ? "Not planned" : toHarvest >= 0 ? toHarvest+" days left" : Math.abs(toHarvest)+" days overdue"}</strong>
          <small>{cycle.harvested_on ? "Cycle completed" :
            cycle.expected_harvest_on ? "Target: " + pretty(cycle.expected_harvest_on) + " · estimate only" : "Set a target harvest date, not an automatic prediction"}</small></article>
        <article><span>{cycle.harvested_on ? "Final crop status" : "Current crop stage"}</span><strong>
          {cycle.harvested_on ? "Harvested" : !cycle.planted_on ? "Preparing" :
            growthError ? "Unavailable" : stage?.label ?? "Not confirmed"}</strong>
          <small>{cycle.harvested_on ? "Harvested " + pretty(cycle.harvested_on) + ". Earlier stage records are kept in the diary." :
            !cycle.planted_on ? "Crop not planted yet" :
            isConfirmed ? "Confirmed by your field record" : stage ? "Approximate calendar stage · verify in field" :
            growthError ?? "Record what you observe"}</small></article>
      </div>
      <div className="journey-actions">
        <button className="primary-action" type="button" onClick={onActivity}>
          {cycle.status === "completed" ? "+ Record previous / post-harvest work" :
            cycle.planted_on ? "+ Record field activity" : "+ Record preparation / planting"}
        </button>
        {cycle.status === "active" && <>
          <button className="secondary-action" type="button" onClick={()=>setEditing(v=>!v)}>
            Edit planting & harvest plan</button>
          {cycle.planted_on && <button className="secondary-action" type="button" onClick={onHarvest}>Record harvest</button>}
        </>}
        <button className="secondary-action" type="button" onClick={onGrowth}>View/confirm crop stages</button>
        <button className="secondary-action" type="button" onClick={onTrends}>See crop-cycle graphs</button>
        <button className="secondary-action" type="button" onClick={onHistory}>Compare past seasons</button>
      </div>
      {editing && <section className="journey-plan-edit">
        <h3>Update the crop plan</h3>
        <p>These dates describe this one crop cycle. Expected harvest is a plan, not a guaranteed prediction.</p>
        <div className="journey-plan-fields">
          <label>Actual planting date<input className="form-input" type="date" min={cycle.started_on}
            value={plantedOn} onChange={e=>setPlantedOn(e.target.value)} /></label>
          <label>Expected harvest<input className="form-input" type="date" min={plantedOn||cycle.started_on}
            value={expectedOn} onChange={e=>setExpectedOn(e.target.value)} /></label>
        </div>
        {editError && <p role="alert" className="login-error">{editError}</p>}
        <button className="primary-action" type="button" disabled={busy} onClick={()=>void savePlan()}>
          {busy?"Saving…":"Save dates"}</button>
      </section>}
      <section className="journey-diary">
        <header><div><span className="workspace-eyebrow">FIELD DIARY</span><h3>Your story so far</h3>
          <p>Chronological operations for this crop, including pre-planting preparation.</p></div></header>
        {loading ? <p>Loading activities…</p> : cycleActivities.length ? <ol>
          {cycleActivities.map(entry=><li key={entry.id}>
            <time dateTime={entry.occurred_at}>{pretty(entry.occurred_at)}</time>
            <div><strong>{activityName(entry.activity_type)}</strong>
              {entry.notes && <p>{entry.notes}</p>}</div></li>)}
        </ol> : <div className="journey-no-activities">
          <p>No field operations recorded for this cycle yet. Start with tractor preparation, sowing or another real activity.</p>
        </div>}
      </section>
    </>}
  </div>;
}
