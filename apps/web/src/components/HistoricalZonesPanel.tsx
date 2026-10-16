import { useCallback, useEffect, useRef, useState } from "react";
import { calculateSeasonalZones, combineSeasonalZones, getSeasonalZones } from "../lib/api";
import type { CropCycle, Field, SeasonalZoneGrid, SeasonalZonesResponse } from "../types/api";
import "./HistoricalZonesPanel.css";

type Props = { field: Field; cropCycle: CropCycle | null };

function SeasonalBoundaryMap({ grid, title }: { grid: SeasonalZoneGrid; title: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    canvas.width = grid.width;
    canvas.height = grid.height;
    const context = canvas.getContext("2d");
    if (!context) return;
    const pixels = context.createImageData(grid.width, grid.height);
    const mean = grid.mean_ndvi;
    for (let i = 0; i < grid.width * grid.height; i++) {
      const value = grid.pixels[i], offset = i * 4;
      if (!grid.mask[i] || value === null || mean == null) continue;
      const relative = value - mean;
      const rgb = relative < -0.08
        ? [226, 119, 76] : relative > 0.08
          ? [55, 143, 94] : [192, 206, 174];
      pixels.data[offset] = rgb[0];
      pixels.data[offset + 1] = rgb[1];
      pixels.data[offset + 2] = rgb[2];
      pixels.data[offset + 3] = 255;
    }
    context.putImageData(pixels, 0, 0);
  }, [grid]);
  return (
    <div className="hz-map">
      <canvas ref={ref} role="img" aria-label={title + ", NDVI average zones within field boundary"} />
      <div className="hz-legend">
        <span><i className="hz-weak" /> Below field average</span>
        <span><i className="hz-middle" /> Near average</span>
        <span><i className="hz-strong" /> Above average</span>
      </div>
    </div>
  );
}
function fmt(value: number | null | undefined) {
  return value == null ? "—" : value.toFixed(3);
}
export default function HistoricalZonesPanel({ field, cropCycle }: Props) {
  const [data, setData] = useState<SeasonalZonesResponse | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const [combined, setCombined] = useState<SeasonalZoneGrid | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const refresh = useCallback(async () => {
    if (!cropCycle) return;
    const response = await getSeasonalZones(field.id, cropCycle.id);
    setData(response);
    return response;
  }, [cropCycle?.id, field.id]);

  useEffect(() => {
    let active = true;
    setData(null);
    setSelected([]);
    setCombined(null);
    setLoading(true);
    setError(null);
    if (!cropCycle) { setLoading(false); return; }
    void getSeasonalZones(field.id, cropCycle.id).then((r) => {
      if (active) {
        setData(r);
        setSelected(r.seasons.filter((s) => s.status === "completed").slice(0, 6).map((s) => s.year));
      }
    }).catch((e: unknown) => {
      if (active) setError(e instanceof Error ? e.message : "Unable to load historical seasons.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [field.id, cropCycle?.id]);

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
      const result = await calculateSeasonalZones(field.id, cropCycle.id, missing);
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
      setCombined(await combineSeasonalZones(field.id, cropCycle.id, selected));
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
          <h2>Historical Zones · {cropCycle.crop_name}</h2>
          <p>Calculate one compact average per year, then combine chosen seasons without keeping historical imagery.</p>
        </div>
        <button type="button" onClick={() => void refresh().catch((e) => setError(String(e)))} disabled={loading || busy}>Refresh status</button>
      </header>
      {data && <p className="hz-explanation">
        Reference growing window: {data.reference_window.start}, {data.reference_window.length_days} days.
        { " " }Older years use the selected crop-cycle calendar as a proxy, not verified planting dates.
      </p>}
      {error && <p className="hz-error" role="alert">{error}</p>}
      {info && <p className="hz-info" role="status">{info}</p>}
      {loading && <p>Loading available seasons…</p>}
      {data && <>
        <section className="hz-section">
          <h3>Select rice-style crop seasons (up to six years)</h3>
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
            <button type="button" className="hz-primary" disabled={busy || missing.length === 0}
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
          <h3>Combined average of selected seasons</h3>
          {combined ? <>
            <p><strong>{(combined.selected_years ?? []).join(", ")}</strong> · Mean NDVI: {fmt(combined.mean_ndvi)}</p>
            <p className="hz-area-summary">Relative low: <strong>{fmt(combined.weak_area_acres ?? null)} ac</strong> · Relative high: <strong>{fmt(combined.strong_area_acres ?? null)} ac</strong></p>
            <SeasonalBoundaryMap grid={combined} title="Combined season relative zones" />
            <p className="hz-explanation">{combined.notes}</p>
          </> : <p className="hz-explanation">Select completed seasons above and click “Show average” to produce the combined zone map.</p>}
        </section>
        <section className="hz-section">
          <h3>Individual seasonal averages</h3>
          <p>Each map is saved once as a small, aligned NDVI average. Raw source scenes are not saved.</p>
          <div className="hz-season-grid">
            {data.seasons.filter((r) => r.status === "completed" && r.result).map((r) => (
              <article className="hz-season-card" key={r.id}>
                <h4>{cropCycle.crop_name} {r.year}</h4>
                <p>{r.start_date} to {r.end_date}</p>
                <p>{r.window_source === "recorded_crop_cycle" ? "Actual saved crop-cycle dates" : "Projected crop calendar · estimated dates"}</p>
                <p>Season mean NDVI: <strong>{fmt(r.result?.mean_ndvi)}</strong> · {r.result?.scene_count} clear dates</p>
                {r.result && <>
                  <p className="hz-area-summary">Relative low: <strong>{fmt(r.result.weak_area_acres ?? null)} ac</strong> · Relative high: <strong>{fmt(r.result.strong_area_acres ?? null)} ac</strong></p>
                  <SeasonalBoundaryMap grid={r.result} title={r.year + " NDVI season mean zones"} />
                </>}
              </article>
            ))}
          </div>
          {!data.seasons.some((r) => r.status === "completed") &&
            <p className="hz-explanation">No saved seasonal averages yet. Select years and use Calculate.</p>}
        </section>
      </>}
      <p className="hz-disclaimer">Zones are relative NDVI differences (±0.08 around each map’s field average), not measured yield, soil tests or evidence of disease. Each selected year contributes equally to the combined map. A field with fewer than three usable scenes is marked failed rather than given a fabricated seasonal average.</p>
    </section>
  );
}
