import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { calculateSeasonalZones, combineSeasonalZones, getSeasonalZones, listFieldCropCycles, listSavedHistoricalWindows } from "../lib/api";
import type { HistoryWindow, SavedHistoricalWindow } from "../lib/api";
import type { CropCycle, Field, SeasonalZoneGrid, SeasonalZonesResponse } from "../types/api";
import "./HistoricalZonesPanel.css";

type Props = { field: Field; cropCycle: CropCycle | null };

type MapMode = "contrast" | "zones";

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
  const [periodMode, setPeriodMode] = useState<"crop" | "custom">("crop");
  const [startMonth, setStartMonth] = useState(8);
  const [endMonth, setEndMonth] = useState(10);
  const [allCrops, setAllCrops] = useState(true);
  const [savedWindows, setSavedWindows] = useState<SavedHistoricalWindow[]>([]);
  const period = useMemo<HistoryWindow | undefined>(() => periodMode === "custom"
    ? {start_month:startMonth,end_month:endMonth,all_crops:allCrops} : undefined,
    [periodMode,startMonth,endMonth,allCrops]);
  const monthNames = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
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
  const refresh = useCallback(async () => {
    if (!cropCycle) return;
    const response = await getSeasonalZones(field.id, cropCycle.id, period);
    setData(response);
    return response;
  }, [cropCycle?.id, field.id, period]);

  useEffect(() => {
    let active = true;
    setData(null);
    setSelected([]);
    setCombined(null);
    setLoading(true);
    setError(null);
    if (!cropCycle || !validPeriod) { setLoading(false); return; }
    void getSeasonalZones(field.id, cropCycle.id, period).then((r) => {
      if (active) {
        setData(r);
        setSelected(r.seasons.filter((s) => s.status === "completed").slice(0, 6).map((s) => s.year));
      }
    }).catch((e: unknown) => {
      if (active) setError(e instanceof Error ? e.message : "Unable to load historical seasons.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [field.id, cropCycle?.id, period, validPeriod]);

  useEffect(() => {
    if (!cropCycle) { setSavedWindows([]); return; }
    let active = true;
    void listSavedHistoricalWindows(field.id, cropCycle.id, periodMode === "custom" && allCrops)
      .then(windows => { if (active) setSavedWindows(windows); })
      .catch(() => { if (active) setSavedWindows([]); });
    return () => { active = false; };
  }, [field.id, cropCycle?.id, data?.seasons.length, periodMode, allCrops]);

  // Poll status only; never calculate or queue jobs automatically.
  useEffect(() => {
    if (!cropCycle || !data?.seasons.some((s) => s.status === "pending" || s.status === "running")) return;
    const handle = window.setInterval(() => {
      void refresh().catch(() => undefined);
    }, 10000);
    return () => window.clearInterval(handle);
  }, [cropCycle?.id, data?.seasons, refresh]);

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
  async function combine() {
    if (!cropCycle || busy || !selected.length || finished.length !== selected.length) return;
    setBusy(true); setCombined(null); setError(null); setInfo(null);
    try {
      setCombined(await combineSeasonalZones(field.id, cropCycle.id, selected, period));
      setInfo("Combined from saved seasonal averages only. No satellite source download was needed.");
    } catch (e) { setError(e instanceof Error ? e.message : "Cannot combine these seasons."); }
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
          <span className="workspace-eyebrow">ON-DEMAND HISTORICAL INTELLIGENCE</span>
          <h2>Historical Zones · {historyScopeLabel}</h2>
          <p>Choose a crop-season window, calculate it once per year, then compare matching periods without keeping raw imagery.</p>
        </div>
        <button type="button" onClick={() => void refresh().catch((e) => setError(String(e)))} disabled={loading || busy}>Refresh status</button>
      </header>
      <section className="hz-section hz-period-picker">
        <h3>1. What period do you want to compare?</h3>
        <p>Create separate saved analyses, for example August–October or November–January. Nothing calculates automatically.</p>
        <label className="hz-option-label">
          <input type="radio" checked={periodMode === "crop"} onChange={()=>setPeriodMode("crop")}/>
          Use the crop-cycle growing window
        </label>
        <label className="hz-option-label">
          <input type="radio" checked={periodMode === "custom"} onChange={()=>setPeriodMode("custom")}/>
          Choose calendar months
        </label>
        {periodMode === "custom" && <div className="hz-crop-scope" role="group" aria-label="Compare crop or field">
          <label className="hz-option-label">
            <input type="radio" checked={allCrops} onChange={()=>setAllCrops(true)}/>
            Field history (any crop) — same months across years
          </label>
          <label className="hz-option-label">
            <input type="radio" checked={!allCrops} onChange={()=>setAllCrops(false)}/>
            Use {cropCycle.crop_name} crop calendar as reference — unrecorded historical years remain estimates
          </label>
          {allCrops && <p className="hz-explanation">Vegetation comparisons describe this field, regardless of what was planted. A difference between years may reflect different crops, not lower productivity.</p>}
        </div>}
        {periodMode === "custom" && <div className="hz-month-range">
          <label>From
            <select value={startMonth} onChange={e=>setStartMonth(Number(e.target.value))}>
              {monthNames.map((name,i)=><option key={name} value={i+1}>{name}</option>)}
            </select>
          </label>
          <label>Through
            <select value={endMonth} onChange={e=>setEndMonth(Number(e.target.value))}>
              {monthNames.map((name,i)=><option key={name} value={i+1}>{name}</option>)}
            </select>
          </label>
        </div>}
        {!validPeriod && <p className="hz-error" role="alert">Choose at most eight consecutive months. Divide longer periods into separate reports.</p>}
        <p className="hz-explanation">Period: <strong>{periodName}</strong>. The same months will be compared across earlier calendar years.</p>
        {savedWindows.length > 0 && <div className="hz-saved-windows">
          <span>Saved analyses</span>
          {savedWindows.map(item => {
            const match = /^month-(\d{2})-to-(\d{2})$/.exec(item.calendar_key);
            return <button type="button" key={item.calendar_key}
              onClick={()=>{
                if (match) {
                  setStartMonth(Number(match[1]));
                  setEndMonth(Number(match[2]));
                  setPeriodMode("custom");
                } else setPeriodMode("crop");
              }}>
              {match ? `${monthNames[Number(match[1])-1]}–${monthNames[Number(match[2])-1]}` : "Full crop cycle"}
              {" · "}{item.completed_years.length} years saved
            </button>;
          })}
        </div>}
      </section>
      {data && <p className="hz-explanation">
        Reference growing window: {data.reference_window.start}, {data.reference_window.length_days} days.
        {" "}{data.reference_window.basis}
      </p>}
      {error && <p className="hz-error" role="alert">{error}</p>}
      {info && <p className="hz-info" role="status">{info}</p>}
      {loading && <p>Loading available seasons…</p>}
      {data && <>
        <section className="hz-section">
          <h3>2. Select years · {historyScopeLabel} ({periodName})</h3>
          <p>Select years, calculate any missing ones manually, then view their combined average.</p>
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
            <button type="button" disabled={busy || !selected.length || finished.length !== selected.length}
              onClick={() => void combine()}>Show average of {selected.length} selected seasons</button>
          </div>
          {pending && <p className="hz-info">Calculations are queued or running. The page checks job status automatically; computation only begins from your Calculate request.</p>}
          {rows.filter((r) => r.status === "failed").map((r) =>
            <p className="hz-error" key={r.year}>{r.year}: {r.error}. Select Calculate to retry.</p>)}
        </section>
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
          <h3>3. Combined average · {periodName}</h3>
          {combined ? <>
            <p><strong>{(combined.selected_years ?? []).join(", ")}</strong> · Mean NDVI: {fmt(combined.mean_ndvi)}</p>
            <SeasonalBoundaryMap grid={combined} title="Combined season relative zones" mode={mapMode} relative />
            <ZoneBreakdown grid={combined} relative />
            <p className="hz-explanation">This spatial map averages each year’s deviations from its own seasonal field mean, preventing greener or wetter years from automatically dominating the zone boundaries.</p>
            <p className="hz-stability"><strong>Cross-year spatial consistency:</strong> {combined.stable_relative_area_percent == null ? "Requires at least three comparable years" : combined.stable_relative_area_percent.toFixed(1) + "% of comparable cells"}</p>
            <p className="hz-explanation">{combined.notes}</p>
          </> : <p className="hz-explanation">Select completed seasons above and click “Show average” to produce the combined zone map.</p>}
        </section>
        <section className="hz-section">
          <h3>4. Individual yearly averages · {periodName}</h3>
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
            <p className="hz-explanation">No saved seasonal averages yet. Select years and use Calculate.</p>}
        </section>
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
