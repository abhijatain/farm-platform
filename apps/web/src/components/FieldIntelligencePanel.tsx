import { useEffect, useMemo, useState } from "react";
import { getCropPhenologyIntelligence, getFieldObservationIntelligence, getFieldSpatialHistory } from "../lib/api";
import type { CropCycle, CropPhenologyIntelligence, Field, FieldObservationIntelligence, FieldSpatialHistory, RelativeZone, TrackedZone } from "../types/api";
import "./FieldIntelligencePanel.css";

type Props = { field: Field; cropCycle: CropCycle | null };
type Metric = "ndvi" | "ndmi" | "ndre";
type Geometry = RelativeZone["geometry"];

function formatDate(date: string | null) {
  return date
    ? new Date(date.slice(0, 10) + "T12:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })
    : "—";
}
function signed(value: number | null, unit = "") {
  return value == null ? "—" : (value > 0 ? "+" : "") + value.toFixed(3) + (unit === "dB" ? " dB" : "");
}
function area(value: number) { return value.toFixed(3) + " ac"; }

function polygonPaths(geometry: Geometry | Field["boundary"], project: (x: number, y: number) => [number, number]) {
  const polys: number[][][][] = geometry.type === "Polygon"
    ? [geometry.coordinates as number[][][]]
    : geometry.coordinates as number[][][][];
  return polys.flatMap((poly) => poly.map((ring) =>
    ring.map(([x, y], i) => {
      const [px, py] = project(x, y);
      return (i ? "L" : "M") + px.toFixed(2) + " " + py.toFixed(2);
    }).join(" ") + " Z"
  )).join(" ");
}

function ZoneMap({ field, zones, tracks, show }: {
  field: Field;
  zones: RelativeZone[];
  tracks: TrackedZone[];
  show: "history" | "tracking";
}) {
  const map = useMemo(() => {
    const ring = field.boundary.coordinates[0];
    if (!ring?.length) return null;
    const xs = ring.map((p) => p[0]), ys = ring.map((p) => p[1]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs);
    const y0 = Math.min(...ys), y1 = Math.max(...ys);
    const scale = Math.min(380 / Math.max(x1 - x0, 1e-8), 210 / Math.max(y1 - y0, 1e-8));
    const left = (420 - (x1 - x0) * scale) / 2;
    const top = (260 - (y1 - y0) * scale) / 2;
    const project = (x: number, y: number): [number, number] =>
      [left + (x - x0) * scale, top + (y1 - y) * scale];
    return { outline: polygonPaths(field.boundary, project), project };
  }, [field.boundary]);
  if (!map) return <p>Field boundary is unavailable.</p>;
  const items = show === "history"
    ? zones.map((z) => ({ key: z.id, geometry: z.geometry, className: z.classification.includes("low") ? "low" : "high" }))
    : tracks.map((z) => ({ key: z.id, geometry: z.geometry, className: z.transition }));
  return (
    <div className="intelligence-zone-map">
      <svg viewBox="0 0 420 260" role="img" aria-label={show === "history" ? "Repeated field-relative anomaly zones" : "Recent anomaly transitions"}>
        <path d={map.outline} fill="#eaf2e8" stroke="#466c52" strokeWidth="2" fillRule="evenodd" />
        {items.map((item) => (
          <path key={item.key} d={polygonPaths(item.geometry, map.project)}
            fillRule="evenodd" className={"intelligence-area " + item.className} />
        ))}
        <path d={map.outline} fill="none" stroke="#315d41" strokeWidth="2" />
      </svg>
      {items.length === 0 && <p className="intelligence-no-zone">No qualified spatial zones for these observations.</p>}
    </div>
  );
}

export default function FieldIntelligencePanel({ field, cropCycle }: Props) {
  const [metric, setMetric] = useState<Metric>("ndvi");
  const [years, setYears] = useState(10);
  const [display, setDisplay] = useState<"history" | "tracking">("tracking");
  const [refresh, setRefresh] = useState(0);
  const [spatial, setSpatial] = useState<FieldSpatialHistory | null>(null);
  const [spatialLoading, setSpatialLoading] = useState(true);
  const [spatialError, setSpatialError] = useState<string | null>(null);
  const [sensor, setSensor] = useState<FieldObservationIntelligence | null>(null);
  const [sensorError, setSensorError] = useState<string | null>(null);
  const [phenology, setPhenology] = useState<CropPhenologyIntelligence | null>(null);
  const [phenologyError, setPhenologyError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setSpatialLoading(true);
    setSpatial(null);
    setSpatialError(null);
    void getFieldSpatialHistory(field.id, metric, years)
      .then((v) => { if (active) setSpatial(v); })
      .catch((e: unknown) => { if (active) setSpatialError(e instanceof Error ? e.message : "Unable to examine spatial history."); })
      .finally(() => { if (active) setSpatialLoading(false); });
    return () => { active = false; };
  }, [field.id, metric, years, refresh]);

  useEffect(() => {
    let active = true;
    setSensor(null);
    setSensorError(null);
    void getFieldObservationIntelligence(field.id, 2)
      .then((v) => { if (active) setSensor(v); })
      .catch((e: unknown) => { if (active) setSensorError(e instanceof Error ? e.message : "Unable to examine satellite comparisons."); });
    return () => { active = false; };
  }, [field.id, refresh]);

  useEffect(() => {
    let active = true;
    setPhenology(null);
    setPhenologyError(null);
    if (cropCycle) {
      void getCropPhenologyIntelligence(cropCycle.id)
        .then((v) => { if (active) setPhenology(v); })
        .catch((e: unknown) => { if (active) setPhenologyError(e instanceof Error ? e.message : "Crop interpretation unavailable."); });
    }
    return () => { active = false; };
  }, [cropCycle?.id, refresh]);

  const selected = display === "history" ? spatial?.zones ?? [] : spatial?.tracking ?? [];
  return (
    <section className="intelligence-panel" aria-label="Zones and field intelligence">
      <header className="intelligence-heading">
        <div>
          <span className="workspace-eyebrow">FIELD INTELLIGENCE</span>
          <h3>Historical zones, anomalies and crop signals</h3>
          <p>Interpret actual satellite and crop observations. These are scouting clues, not disease or yield predictions.</p>
        </div>
        <button type="button" onClick={() => setRefresh((n) => n + 1)}>Refresh intelligence</button>
      </header>

      <section className="intelligence-block">
        <h4>1. Historical relative zones and anomaly tracking</h4>
        <div className="intelligence-controls">
          <label>Index <select value={metric} onChange={(e) => setMetric(e.target.value as Metric)}>
            <option value="ndvi">NDVI</option><option value="ndmi">NDMI</option><option value="ndre">NDRE</option>
          </select></label>
          <label>Lookback <select value={years} onChange={(e) => setYears(Number(e.target.value))}>
            <option value={2}>2 years</option><option value={5}>5 years</option><option value={10}>10 years</option>
          </select></label>
          <label>View <select value={display} onChange={(e) => setDisplay(e.target.value as "history" | "tracking")}>
            <option value="tracking">Recent transitions</option><option value="history">Repeated multi-year zones</option>
          </select></label>
        </div>
        {spatialLoading ? <p role="status">Computing quality-screened spatial history…</p> :
          spatialError ? <p className="intelligence-error" role="alert">{spatialError}</p> :
          spatial ? <>
            <p className="intelligence-muted">
              {spatial.observation_count} usable optical dates across {spatial.year_count} years
              {spatial.date_range ? " · " + formatDate(spatial.date_range[0]) + " – " + formatDate(spatial.date_range[1]) : ""}
              {spatial.cell_size_m != null ? " · " + spatial.cell_size_m + " m analysis cells" : ""}
            </p>
            <ZoneMap field={field} zones={spatial.zones} tracks={spatial.tracking} show={display} />
            <div className="intelligence-legend">
              {display === "history" ? <>
                <span><i className="low"/>Repeated relative low</span><span><i className="high"/>Repeated relative high</span>
              </> : <>
                <span><i className="new"/>New</span><span><i className="persistent"/>Persistent</span><span><i className="resolved"/>Resolved</span>
              </>}
            </div>
            {selected.length > 0 && <div className="intelligence-zone-rows">
              {selected.map((z) => <div key={z.id}>
                <strong>{"classification" in z ? z.classification.replace(/_/g, " ") : z.anomaly_type.replace(/_/g, " ") + " · " + z.transition}</strong>
                <span>{area(z.area_acres)}</span>
              </div>)}
            </div>}
            {spatial.status !== "candidate_zones" && <p className="intelligence-caution">
              Historical management zones are withheld until enough multi-year quality imagery exists.
            </p>}
            {spatial.warnings.map((w) => <p className="intelligence-muted" key={w}>{w}</p>)}
          </> : null}
      </section>

      <section className="intelligence-block">
        <h4>2. Comparable radar and optical changes</h4>
        {sensorError && <p className="intelligence-error">{sensorError}</p>}
        {!sensor && !sensorError && <p>Loading comparable passes…</p>}
        {sensor && <>
          {sensor.comparisons.length === 0
            ? <p className="intelligence-muted">No qualifying comparable observations. This does not mean the field is healthy.</p>
            : <div className="intelligence-table-scroll"><table className="intelligence-table">
              <thead><tr><th>Signal</th><th>Pass</th><th>Current</th><th>Previous</th><th>Difference</th><th>Quality</th></tr></thead>
              <tbody>{sensor.comparisons.map((c) =>
                <tr key={c.metric_type + ":" + (c.orbit_key ?? c.source)}>
                  <td>{c.metric_type.toUpperCase()}<small>{c.orbit_key ?? c.source}</small></td>
                  <td>{formatDate(c.latest_date)}<small>{c.days_between == null ? "1 pass only" : c.days_between + " days apart"}</small></td>
                  <td>{c.latest_value.toFixed(3)}</td>
                  <td>{c.previous_value == null ? "—" : c.previous_value.toFixed(3)}</td>
                  <td>{signed(c.change, c.unit)}</td>
                  <td>{c.latest_valid_percent.toFixed(0)}% valid</td>
                </tr>)}</tbody>
              </table></div>}
          {sensor.notes.map((w) => <p className="intelligence-muted" key={w}>{w}</p>)}
        </>}
      </section>

      {cropCycle && <section className="intelligence-block">
        <h4>3. Growth-stage-aware satellite context</h4>
        {phenologyError && <p className="intelligence-error">{phenologyError}</p>}
        {!phenology && !phenologyError && <p>Loading growth-stage context…</p>}
        {phenology && <>
          <p><strong>{phenology.crop_name}</strong> · {phenology.stage_code?.replace(/_/g, " ") ?? "Stage unknown"}
            <span className="intelligence-source">{phenology.stage_source.replace(/_/g, " ")}</span>
          </p>
          <p>{phenology.guidance}</p>
          {phenology.recommended_indices.length > 0 && <p className="intelligence-index-list">
            Indices to inspect: {phenology.recommended_indices.map((index) => <span key={index}>{index.toUpperCase()}</span>)}
          </p>}
          <h5>Earlier seasons near the same planting age</h5>
          {phenology.historical_comparisons.length === 0 ? <p className="intelligence-muted">No qualifying earlier same-crop, similar-age observations.</p> :
            <div className="intelligence-table-scroll"><table className="intelligence-table">
              <thead><tr><th>Date</th><th>Crop</th><th>Days after planting</th><th>NDVI median</th><th>Valid</th></tr></thead>
              <tbody>{phenology.historical_comparisons.map((c) =>
                <tr key={c.crop_cycle_id}>
                  <td>{formatDate(c.observed_on)}</td><td>{c.crop}</td><td>{c.days_after_planting}</td>
                  <td>{c.ndvi_median == null ? "—" : c.ndvi_median.toFixed(3)}</td><td>{c.valid_percent.toFixed(0)}%</td>
                </tr>)}</tbody>
            </table></div>}
          {phenology.warnings.map((warning) => <p className="intelligence-muted" key={warning}>{warning}</p>)}
        </>}
      </section>}
    </section>
  );
}
