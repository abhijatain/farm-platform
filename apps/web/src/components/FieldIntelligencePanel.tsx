import { useEffect, useState } from "react";
import { getCropPhenologyIntelligence, getFieldObservationIntelligence } from "../lib/api";
import type { CropCycle, CropPhenologyIntelligence, Field, FieldObservationIntelligence } from "../types/api";
import "./FieldIntelligencePanel.css";

type Props = { field: Field; cropCycle: CropCycle | null };
const fmt = (v: number | null) => v == null ? "—" : v.toFixed(3);

export default function FieldIntelligencePanel({ field, cropCycle }: Props) {
  const [sensors, setSensors] = useState<FieldObservationIntelligence | null>(null);
  const [sensorError, setSensorError] = useState<string | null>(null);
  const [phenology, setPhenology] = useState<CropPhenologyIntelligence | null>(null);
  const [phenologyError, setPhenologyError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    setSensors(null); setSensorError(null);
    void getFieldObservationIntelligence(field.id).then(v => {
      if (active) setSensors(v);
    }).catch((e: unknown) => {
      if (active) setSensorError(e instanceof Error ? e.message : "Unavailable");
    });
    return () => { active = false; };
  }, [field.id, refresh]);
  useEffect(() => {
    let active = true;
    setPhenology(null); setPhenologyError(null);
    if (cropCycle) {
      void getCropPhenologyIntelligence(cropCycle.id).then(v => {
        if (active) setPhenology(v);
      }).catch((e: unknown) => {
        if (active) setPhenologyError(e instanceof Error ? e.message : "Unavailable");
      });
    }
    return () => { active = false; };
  }, [cropCycle?.id, refresh]);

  return (
    <section className="intelligence-panel">
      <div className="intelligence-heading">
        <div>
          <span className="workspace-eyebrow">SATELLITE INTELLIGENCE</span>
          <h3>Comparable optical, radar & crop growth</h3>
          <p>Two-pass comparisons use existing recent observations. Multi-year
            analysis has moved to the separate Historical Zones tab and never starts automatically.</p>
        </div>
        <button type="button" onClick={() => setRefresh(n => n + 1)}>Refresh comparisons</button>
      </div>
      <section className="intelligence-block">
        <h4>Radar and optical date comparisons</h4>
        {sensorError && <p className="intelligence-error" role="alert">{sensorError}</p>}
        {!sensors && !sensorError && <p className="intelligence-muted">Loading comparisons…</p>}
        {sensors && (sensors.comparisons.length === 0
          ? <p className="intelligence-muted">No suitably clear, comparable observations yet.</p>
          : <div className="intelligence-table-scroll"><table className="intelligence-table">
            <thead><tr><th>Index</th><th>Source/orbit</th><th>Latest</th><th>Previous</th><th>Difference</th><th>Coverage</th></tr></thead>
            <tbody>{sensors.comparisons.map(c => <tr key={c.metric_type + ":" + c.orbit_key + ":" + c.source}>
              <td>{c.metric_type.toUpperCase()}</td><td>{c.orbit_key ?? c.source}</td>
              <td>{fmt(c.latest_value)}<small>{c.latest_date}</small></td>
              <td>{fmt(c.previous_value)}<small>{c.previous_date ?? "No second pass"}</small></td>
              <td>{c.change != null && c.change > 0 ? "+" : ""}{fmt(c.change)}</td>
              <td>{c.latest_valid_percent.toFixed(0)}%</td>
            </tr>)}</tbody>
          </table></div>)}
        {sensors?.notes.map(note => <p className="intelligence-muted" key={note}>{note}</p>)}
      </section>
      {cropCycle && <section className="intelligence-block">
        <h4>Growth-stage interpretation</h4>
        {phenologyError && <p className="intelligence-error" role="alert">{phenologyError}</p>}
        {!phenology && !phenologyError && <p className="intelligence-muted">Loading crop context…</p>}
        {phenology && <>
          <p><strong>{phenology.crop_name}</strong> · {phenology.stage_code?.replace(/_/g, " ") ?? "Unknown"}
            <span className="intelligence-source">{phenology.stage_source.replace(/_/g, " ")}</span></p>
          <p>{phenology.guidance}</p>
          {phenology.recommended_indices.length > 0 &&
            <p className="intelligence-index-list">Indices to inspect:
              {phenology.recommended_indices.map(index => <span key={index}>{index.toUpperCase()}</span>)}
            </p>}
          <h5>Previous seasons at comparable days after planting</h5>
          {!phenology.historical_comparisons.length
            ? <p className="intelligence-muted">No suitably comparable historical observations have been ingested.</p>
            : <div className="intelligence-table-scroll"><table className="intelligence-table">
              <thead><tr><th>Year</th><th>Crop</th><th>Age</th><th>NDVI</th><th>Coverage</th></tr></thead>
              <tbody>{phenology.historical_comparisons.map(c => <tr key={c.crop_cycle_id}>
                <td>{c.observed_on}</td><td>{c.crop}</td><td>{c.days_after_planting} days</td>
                <td>{fmt(c.ndvi_median)}</td><td>{c.valid_percent.toFixed(0)}%</td>
              </tr>)}</tbody>
            </table></div>}
          {phenology.warnings.map(w => <p className="intelligence-muted" key={w}>{w}</p>)}
        </>}
      </section>}
    </section>
  );
}
