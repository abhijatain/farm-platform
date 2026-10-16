import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { calculateSeasonalZones, combineSeasonalZones, getSeasonalZones, listFieldCropCycles, listSavedHistoricalWindows } from "../lib/api";
import type { HistoryWindow, SavedHistoricalWindow } from "../lib/api";
import type { CropCycle, Field, SeasonalZoneGrid, SeasonalZonesResponse } from "../types/api";
import "./HistoricalZonesPanel.css";

type Props = { field: Field; cropCycle: CropCycle | null };

type MapMode = "contrast" | "zones";
type SavedOption = SavedHistoricalWindow & { all_crops: boolean };
const MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
function savedName(key: string): string {
  const match = /^month-(\d{2})-to-(\d{2})$/.exec(key);
  return match ? `${MONTH_NAMES[Number(match[1])-1]}–${MONTH_NAMES[Number(match[2])-1]}` : "Crop-cycle window";
}

const CONTINUOUS: Array<[number, number, number]> = [
  [159, 31, 65], [226, 69, 50], [243, 157, 46],
  [244, 220, 77], [167, 217, 84], [54, 174, 107],
  [9, 107, 96],
];

function colorRamp(t: number): [number, number, number] {
  const position = Math.max(0, Math.min(1, t)) * (CONTINUOUS.length - 1);
  const index = Math.min(CONTINUOUS.length - 2, Math.floor(position));
  const fraction = position - index;
  const a = CONTINUOUS[index], b = CONTINUOUS[index + 1];
  return [
    Math.round(a[0] + (b[0] - a[0]) * fraction),
    Math.round(a[1] + (b[1] - a[1]) * fraction),
    Math.round(a[2] + (b[2] - a[2]) * fraction),
  ];
}

function SeasonalBoundaryMap({ grid, title, mode, relative = false }: {
  grid: SeasonalZoneGrid;
  title: string;
  mode: MapMode;
  relative?: boolean;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const analysis = relative ? grid.relative_analysis : grid.spatial_analysis;
  const values = relative && grid.relative_pixels ? grid.relative_pixels : grid.pixels;
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    canvas.width = grid.width;
    canvas.height = grid.height;
    const context = canvas.getContext("2d");
    if (!context) return;
    const pixels = context.createImageData(grid.width, grid.height);
    const minimum = analysis?.display?.min ?? -0.04;
    const maximum = analysis?.display?.max ?? 0.04;
    const span = Math.max(0.001, maximum - minimum);
    for (let i = 0; i < grid.width * grid.height; i++) {
      const value = values[i], offset = i * 4;
      if (!grid.mask[i] || value == null) continue;
      let rgb: [number, number, number];
      if (mode === "zones") {
        const zone = analysis?.zone_classes[i];
        rgb = zone === "low" ? [230, 105, 62] :
          zone === "high" ? [40, 153, 97] : [212, 219, 167];
      } else {
        rgb = colorRamp((value - minimum) / span);
      }
      pixels.data[offset] = rgb[0];
      pixels.data[offset + 1] = rgb[1];
      pixels.data[offset + 2] = rgb[2];
      pixels.data[offset + 3] = 255;
    }
    context.putImageData(pixels, 0, 0);
  }, [grid, values, analysis, mode]);
  const classified = analysis?.status === "zones_available";
  return (
    <div className="hz-map">
      <canvas ref={ref} role="img"
        aria-label={title + (mode === "contrast" ? " continuous relative NDVI contrast" : " low/medium/high classified NDVI zones")} />
      <div className="hz-legend">
        {mode === "contrast" ? <>
          <span>Lower relative NDVI</span>
          <div className="hz-gradient-bar" aria-hidden="true" />
          <span>Higher relative NDVI</span>
        </> : <>
          <span><i className="hz-weak" /> Lower</span>
          <span><i className="hz-middle" /> Medium</span>
          <span><i className="hz-strong" /> Higher</span>
        </>}
      </div>
      {analysis && <p className="hz-map-caption">
        {mode === "contrast"
          ? "Enhanced field contrast for viewing only · " +
            (analysis.zones?.p10_p90_spread?.toFixed(3) ?? "—") + " NDVI p10–p90 spread"
          : classified ? "Relative categories meet the minimum variation screen."
            : "Low spatial contrast: no defensible low/high zones at this resolution."}
      </p>}
    </div>
  );
}

function ZoneBreakdown({ grid, relative = false }: {
  grid: SeasonalZoneGrid;
  relative?: boolean;
}) {
  const analysis = relative ? grid.relative_analysis : grid.spatial_analysis;
  const zones = analysis?.zones;
  if (!zones || analysis?.status !== "zones_available") {
    return <p className="hz-variation-warning">
      Not enough within-field NDVI variation to classify meaningful zones. The
      heatmap is a contrast-enhanced visualization, not evidence of yield differences.
    </p>;
  }
  const rows = [
    ["Lower NDVI", zones.low_area_acres, zones.low_percent, "low"],
    ["Medium NDVI", zones.medium_area_acres, zones.medium_percent, "medium"],
    ["Higher NDVI", zones.high_area_acres, zones.high_percent, "high"],
  ] as const;
  return (
    <div className="hz-distribution" aria-label="Field-relative NDVI zone distribution">
      {rows.map(([label, acreage, percent, className]) => (
        <div key={label} className={"hz-distribution-row " + className}>
          <span>{label}</span>
          <div className="hz-distribution-track"><i style={{ width: percent + "%" }} /></div>
          <strong>{percent.toFixed(1)}%</strong>
          <small>{acreage.toFixed(3)} ac</small>
        </div>
      ))}
      <p>Field-relative classification, not predicted yield deviation or soil quality.</p>
    </div>
  );
}
function fmt(value: number | null | undefined) {
  return value == null ? "—" : value.toFixed(3);
}
function HistoricalZonesContent({ field, cropCycle }: Props) {
  const [data, setData] = useState<SeasonalZonesResponse | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const [combined, setCombined] = useState<SeasonalZoneGrid | null>(null);
  const [mapMode, setMapMode] = useState<MapMode>("contrast");
  const [screen, setScreen] = useState<"saved" | "new">("saved");
  const [openedSaved, setOpenedSaved] = useState<SavedOption | null>(null);
  const [savedLoading, setSavedLoading] = useState(true);
  const [periodMode, setPeriodMode] = useState<"crop" | "custom">("custom");
  const [startMonth, setStartMonth] = useState(8);
  const [endMonth, setEndMonth] = useState(10);
  const [allCrops, setAllCrops] = useState(true);
  const [savedWindows, setSavedWindows] = useState<SavedOption[]>([]);
  const period = useMemo<HistoryWindow | undefined>(() => periodMode === "custom"
    ? {start_month:startMonth,end_month:endMonth,all_crops:allCrops} : undefined,
    [periodMode,startMonth,endMonth,allCrops]);
  const monthNames = MONTH_NAMES;
  const monthsDiff = (endMonth-startMonth+12)%12+1;
  const validPeriod = periodMode === "crop" || monthsDiff <= 8;
  const periodName = periodMode === "crop" ? "Same-crop growing calendar"
    : `${monthNames[startMonth-1]}–${monthNames[endMonth-1]}${allCrops ? " · any crop" : " · crop calendar reference"}`;
  const historyScopeLabel = periodMode === "custom" && allCrops
    ? "Field history (all crops)" : cropCycle?.crop_name ?? "Crop";

  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  // Reading and combining completed compact composites never starts a new
  // satellite calculation. Only the explicit Calculate button queues work.
  const savedKey = screen === "saved" ? openedSaved?.calendar_key : undefined;
  const refresh = useCallback(async () => {
    if (!cropCycle || (screen === "saved" && !openedSaved)) return;
    const response = await getSeasonalZones(field.id, cropCycle.id, period, savedKey);
    setData(response);
    return response;
  }, [cropCycle?.id, field.id, period, savedKey, screen, openedSaved]);

  useEffect(() => {
    let active = true;
    setSavedLoading(true);
    setSavedWindows([]);
    setOpenedSaved(null);
    if (!cropCycle) { setSavedLoading(false); return; }
    void Promise.all([
      listSavedHistoricalWindows(field.id, cropCycle.id, false),
      listSavedHistoricalWindows(field.id, cropCycle.id, true),
    ]).then(([cropWindows, fieldWindows]) => {
      if (!active) return;
      const items: SavedOption[] = [
        ...cropWindows.map(item => ({...item, all_crops:false})),
        ...fieldWindows.map(item => ({...item, all_crops:true})),
      ];
      setSavedWindows(items.sort((a,b) =>
        Number(b.completed_years.length > 0)-Number(a.completed_years.length > 0) ||
        b.years.length-a.years.length || a.calendar_key.localeCompare(b.calendar_key)));
    }).catch((e: unknown) => {
      if (active) setError(e instanceof Error ? e.message : "Could not load saved analyses.");
    }).finally(() => { if (active) setSavedLoading(false); });
    return () => { active = false; };
  }, [field.id, cropCycle?.id]);

  // When a saved report is opened, load its exact stored key and select every
  // completed year automatically. New reports default to two recent years.
  useEffect(() => {
    let active = true;
    setData(null);
    setSelected([]);
    setCombined(null);
    setInfo(null);
    setLoading(false);
    setError(null);
    if (!cropCycle || !validPeriod || (screen === "saved" && !openedSaved)) return;
    setLoading(true);
    void getSeasonalZones(field.id, cropCycle.id, period, savedKey).then(result => {
      if (!active) return;
      setData(result);
      const completed = result.seasons.filter(item => item.status === "completed").map(item => item.year).slice(0,6);
      setSelected(screen === "saved" ? completed : completed.length ? completed : result.available_years.slice(0,2));
    }).catch((e: unknown) => {
      if (active) setError(e instanceof Error ? e.message : "Unable to load historical seasons.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [field.id, cropCycle?.id, period, validPeriod, screen, openedSaved, savedKey]);

  // Combine the SAVED averages on read; no worker or raw imagery is requested.
  useEffect(() => {
    let active = true;
    setCombined(null);
    if (!cropCycle || !data || !selected.length || busy) return;
    const completed = data.seasons.filter(row => selected.includes(row.year) && row.status === "completed");
    if (completed.length !== selected.length) return;
    void combineSeasonalZones(field.id, cropCycle.id, selected, period, savedKey)
      .then(result => { if (active) setCombined(result); })
      .catch((e: unknown) => {
        if (active) setError(e instanceof Error ? e.message : "Unable to combine saved years.");
      });
    return () => { active = false; };
  }, [field.id, cropCycle?.id, data, selected, period, savedKey, busy]);

  // Status polling is read-only and only relevant to an opened/active period.
  useEffect(() => {
    if (!cropCycle || !data?.seasons.some(row => row.status === "pending" || row.status === "running")) return;
    const interval = window.setInterval(() => {
      void refresh().catch(() => undefined);
    }, 10000);
    return () => window.clearInterval(interval);
  }, [cropCycle?.id, data?.seasons, refresh]);

  function openSaved(item: SavedOption) {
    const match = /^month-(\\d{2})-to-(\\d{2})$/.exec(item.calendar_key);
    if (match) {
      setStartMonth(Number(match[1]));
      setEndMonth(Number(match[2]));
      setPeriodMode("custom");
    } else {
      setPeriodMode("crop");
    }
    setAllCrops(item.all_crops);
    setOpenedSaved(item);
    setScreen("saved");
  }

  const toggle = (year: number) => {
    setCombined(null);
    setSelected((prev) => prev.includes(year) ? prev.filter((y) => y !== year) : [...prev, year].sort());
  };
  const rows = (data?.seasons ?? []).filter((s) => selected.includes(s.year));
  const finished = rows.filter((r) => r.status === "completed");
  const missing = selected.filter((year) => !data?.seasons.some((s) =>
    s.year === year && ["completed", "pending", "running"].includes(s.status)
  ));
  const pending = rows.some((r) => r.status === "pending" || r.status === "running");

  async function calculate() {
    if (!cropCycle || !missing.length || busy) return;
    setBusy(true); setError(null); setInfo(null); setCombined(null);
    try {
      const result = await calculateSeasonalZones(field.id, cropCycle.id, missing, period);
      setInfo(result.queued_years.length
        ? "Calculation queued for " + result.queued_years.join(", ") +
          ". Run the seasonal-zones worker to process them. Only final season averages will be stored."
        : "Selected seasons have already been calculated or queued.");
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to queue calculations."); }
    finally { setBusy(false); }
  }
  if (!cropCycle) return (
    <section className="workspace-page hz-panel">
      <h2>Historical Zones</h2>
      <p>Choose or create a crop cycle with planting and harvest dates before comparing historical seasons.</p>
    </section>
  );
  return (
    <section className="workspace-page hz-panel">
      <header className="hz-heading">
        <div>
          <span className="workspace-eyebrow">HISTORICAL FIELD ANALYSIS</span>
          <h2>Historical Zones</h2>
          <p>Open a saved report or calculate a new time period. Raw satellite images are not kept.</p>
        </div>
        <button type="button" className="hz-new-action" onClick={() => {
          if (screen === "new") {
            setScreen("saved");
          } else {
            setPeriodMode("custom");
            setAllCrops(true);
            setStartMonth(8);
            setEndMonth(10);
            setScreen("new");
          }
        }}>{screen === "new" ? "← Saved reports" : "+ New analysis"}</button>
      </header>
      <section className="hz-section hz-library">
        <h3>Saved analyses</h3>
        <p>Click a report to see its combined map and each year's average immediately.</p>
        {savedLoading && <p>Loading saved analyses…</p>}
        {!savedLoading && savedWindows.length === 0 &&
          <div className="hz-empty-library">
            <p>No historical reports have been calculated yet.</p>
            <button type="button" className="hz-primary" onClick={() => setScreen("new")}>
              Create your first analysis
            </button>
          </div>}
        {savedWindows.length > 0 && <div className="hz-saved-grid">
          {savedWindows.map(item => {
            const isOpen = screen === "saved" && openedSaved?.calendar_key === item.calendar_key &&
              openedSaved.all_crops === item.all_crops;
            return <button key={item.calendar_key + ":" + item.all_crops}
              type="button" className={"hz-saved-card" + (isOpen ? " active" : "")}
              aria-pressed={isOpen} onClick={() => openSaved(item)}>
              <strong>{savedName(item.calendar_key)}</strong>
              <span>{item.all_crops ? "Whole field · any crop" : cropCycle.crop_name + " crop calendar"}</span>
              <small>{item.completed_years.length
                ? item.completed_years.length + " year" + (item.completed_years.length > 1 ? "s" : "") +
                  " ready · " + [...item.completed_years].sort().join(", ")
                : item.years.length + " year(s) queued or incomplete"}</small>
              <span className="hz-open-report">{isOpen ? "Viewing report" : "View report →"}</span>
            </button>;
          })}
        </div>}
      </section>
      {screen === "new" && <section className="hz-section hz-create">
        <h3>Create a new analysis</h3>
        <p>Choose the months and the years. Calculation only starts when you press Calculate.</p>
        <div className="hz-simple-form">
          <label>Time period
            <select value={periodMode} onChange={event => setPeriodMode(event.target.value as "crop" | "custom")}>
              <option value="custom">Choose calendar months</option>
              <option value="crop">Use the crop cycle's growing dates</option>
            </select>
          </label>
          {periodMode === "custom" && <>
            <label>From
              <select value={startMonth} onChange={event => setStartMonth(Number(event.target.value))}>
                {monthNames.map((name,i) => <option key={name} value={i+1}>{name}</option>)}
              </select>
            </label>
            <label>Through
              <select value={endMonth} onChange={event => setEndMonth(Number(event.target.value))}>
                {monthNames.map((name,i) => <option key={name} value={i+1}>{name}</option>)}
              </select>
            </label>
            <label>Compare
              <select value={allCrops ? "field" : "crop"} onChange={event => setAllCrops(event.target.value === "field")}>
                <option value="field">Whole field (any crops)</option>
                <option value="crop">{cropCycle.crop_name} crop calendar</option>
              </select>
            </label>
          </>}
        </div>
        {!validPeriod && <p className="hz-error" role="alert">
          Select at most eight consecutive months; make a second report for a longer period.
        </p>}
        {validPeriod && <p className="hz-explanation">
          {periodName}. {allCrops && periodMode === "custom" ?
            "Different crops may have grown in these months; this compares field vegetation, not the same crop." :
            "Unrecorded historical planting dates are estimates."}
        </p>}
      </section>}
      {screen === "saved" && !openedSaved && !savedLoading && savedWindows.length > 0 &&
        <p className="hz-choose-hint">Select a saved analysis above to open its maps and results.</p>}
      {error && <p className="hz-error" role="alert">{error}</p>}
      {info && <p className="hz-info" role="status">{info}</p>}
      {loading && <p>Loading available seasons…</p>}
      {data && <>
        {screen === "new" && <section className="hz-section">
          <h3>Choose years to calculate</h3>
          <p>Choose up to six years. Already calculated years can be viewed without recalculation.</p>
          <div className="hz-years">
            {data.available_years.map((year) => {
              const row = data.seasons.find((r) => r.year === year);
              return (
                <label key={year} className={"hz-year" + (selected.includes(year) ? " selected" : "")}>
                  <input type="checkbox" checked={selected.includes(year)} onChange={() => toggle(year)} />
                  <strong>{year}</strong>
                  <small>{row?.status ?? "Not calculated"}</small>
                </label>
              );
            })}
          </div>
          <div className="hz-actions">
            <button type="button" className="hz-primary" disabled={busy || missing.length === 0 || !validPeriod}
              onClick={() => void calculate()}>
              {busy ? "Working…" : missing.length ? "Calculate " + missing.length + " missing season" + (missing.length > 1 ? "s" : "") : "Selected seasons calculated"}
            </button>
          </div>
          {pending && <p className="hz-info">Calculations are queued or running. The page checks job status automatically; computation only begins from your Calculate request.</p>}
          {rows.filter((r) => r.status === "failed").map((r) =>
            <p className="hz-error" key={r.year}>{r.year}: {r.error}. Select Calculate to retry.</p>)}
        </section>}
        {(screen === "new" || openedSaved) && <div className="hz-results">
          <div className="hz-results-heading">
            <div>
              <span className="workspace-eyebrow">SAVED SATELLITE AVERAGES</span>
              <h3>{savedName(data.calendar_key)} · {historyScopeLabel}</h3>
              <p>{data.reference_window.basis}</p>
            </div>
            {screen === "saved" && <button type="button" onClick={() =>
              void refresh().catch((err:unknown)=>setError(String(err))
            )}>Refresh results</button>}
          </div>
        <section className="hz-section">
          <div className="hz-view-selector">
            <span>Zone-map display</span>
            <div role="group" aria-label="Zone map display mode">
              <button type="button" className={mapMode === "contrast" ? "active" : ""}
                aria-pressed={mapMode === "contrast"} onClick={() => setMapMode("contrast")}>Continuous NDVI</button>
              <button type="button" className={mapMode === "zones" ? "active" : ""}
                aria-pressed={mapMode === "zones"} onClick={() => setMapMode("zones")}>Low / medium / high</button>
            </div>
          </div>
          <h3>Combined map · {selected.length} saved year{selected.length === 1 ? "" : "s"}</h3>
          {combined ? <>
            <p><strong>{(combined.selected_years ?? []).join(", ")}</strong> · Mean NDVI: {fmt(combined.mean_ndvi)}</p>
            <SeasonalBoundaryMap grid={combined} title="Combined season relative zones" mode={mapMode} relative />
            <ZoneBreakdown grid={combined} relative />
            <p className="hz-explanation">This spatial map averages each year’s deviations from its own seasonal field mean, preventing greener or wetter years from automatically dominating the zone boundaries.</p>
            <p className="hz-stability"><strong>Cross-year spatial consistency:</strong> {combined.stable_relative_area_percent == null ? "Requires at least three comparable years" : combined.stable_relative_area_percent.toFixed(1) + "% of comparable cells"}</p>
            <p className="hz-explanation">{combined.notes}</p>
          </> : <p className="hz-explanation">{
            selected.length === 0 ? "No completed yearly averages available yet." :
              "Loading the combined map from saved yearly averages…"
          }</p>}
        </section>
        <section className="hz-section">
          <h3>Individual yearly maps</h3>
          <p>Each map is saved once as a small, aligned NDVI average. Raw source scenes are not saved.</p>
          <div className="hz-season-grid">
            {data.seasons.filter((r) => r.status === "completed" && r.result).map((r) => (
              <article className="hz-season-card" key={r.id}>
                <h4>{historyScopeLabel} {r.year}</h4>
                <p>{r.start_date} to {r.end_date}</p>
                <p>{r.window_source === "recorded_crop_cycle" ? "Actual saved crop-cycle dates" : r.window_source === "user_selected_months" ? "Calendar months you selected" : "Projected crop calendar · estimated dates"}</p>
                <p>Season mean NDVI: <strong>{fmt(r.result?.mean_ndvi)}</strong> · {r.result?.scene_count} clear dates</p>
                {r.result && <>
                  <SeasonalBoundaryMap grid={r.result} title={r.year + " NDVI season mean zones"} mode={mapMode} />
                  <ZoneBreakdown grid={r.result} />
                  <details className="hz-dates"><summary>Show {r.result.scene_count ?? 0} image acquisition dates used</summary>
                    <p>{(r.result.scene_dates ?? []).join(", ") || "Dates unavailable in this saved composite."}</p>
                  </details>
                </>}
              </article>
            ))}
          </div>
          {!data.seasons.some((r) => r.status === "completed") &&
            <p className="hz-explanation">No completed yearly averages yet. {pending ?
              "The background worker is still processing this report." :
              "Create an analysis and select Calculate to generate one."}</p>}
        </section>
        </div>}
      </>}
      <p className="hz-disclaimer">Zone maps use continuous field-relative NDVI contrast and conservative variation checks, not measured yield, soil tests or evidence of disease. Each selected year contributes equally to the combined map. A field with fewer than three usable scenes is marked failed rather than given a fabricated seasonal average.</p>
    </section>
  );
}


/** Choose which crop and reference growing-season calendar should anchor history. */
export default function HistoricalZonesPanel({ field, cropCycle }: Props) {
  const [options, setOptions] = useState<CropCycle[]>([]);
  const [chosenId, setChosenId] = useState(cropCycle?.id ?? "");
  const [optionError, setOptionError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    setOptions([]);
    setChosenId(cropCycle?.id ?? "");
    setOptionError(null);
    void listFieldCropCycles(field.id).then((rows) => {
      if (!active) return;
      setOptions(rows);
      setChosenId((previous) =>
        rows.some((row) => row.id === previous) ? previous :
        (cropCycle && rows.some((row) => row.id === cropCycle.id) ? cropCycle.id : rows[0]?.id ?? "")
      );
    }).catch((e: unknown) => {
      if (active) setOptionError(e instanceof Error ? e.message : "Unable to load field crop cycles.");
    });
    return () => { active = false; };
  }, [field.id, cropCycle?.id]);
  const current = options.find((cycle) => cycle.id === chosenId)
    ?? (cropCycle && chosenId === cropCycle.id ? cropCycle : null);
  return <>
    {options.length > 0 && <div className="workspace-page hz-reference-select">
      <label>
        <span>Crop and reference growing season</span>
        <select value={chosenId} onChange={(event) => setChosenId(event.target.value)}>
          {options.map((cycle) => <option value={cycle.id} key={cycle.id}>
            {cycle.crop_name} {cycle.variety ? "· " + cycle.variety : ""}
            {" · " + (cycle.planted_on ?? cycle.started_on)}
          </option>)}
        </select>
      </label>
    </div>}
    {optionError && <p className="hz-error" role="alert">{optionError}</p>}
    <HistoricalZonesContent field={field} cropCycle={current} />
  </>;
}
