import { useEffect, useMemo, useState } from "react";
import { Activity, CloudRain, FileText, Printer, RefreshCcw, Sprout } from "lucide-react";
import { getFieldWeather, getSatelliteChange } from "../lib/api";
import type {
  CropCycle, Farm, Field, FieldSatelliteChange, FieldWeather,
  SatelliteMetricType, SatelliteObservation, Season, TimelineItem,
} from "../types/api";
import "./FieldReport.css";

type Props = {
  farm: Farm;
  field: Field;
  season: Season | null;
  cropCycle: CropCycle | null;
  timeline: TimelineItem[];
  observations: SatelliteObservation[];
  timelineLoading: boolean;
  timelineError: string | null;
  satelliteLoading: boolean;
  satelliteError: string | null;
};

const dateText = (value: string | null | undefined) => {
  if (!value) return "Not recorded";
  const date = new Date(value.length === 10 ? value + "T12:00:00" : value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
};

const numberText = (n: number, digits = 2) =>
  n.toLocaleString("en-IN", { maximumFractionDigits: digits });

const valueOrDash = (n: number | null | undefined, suffix = "", digits = 2) =>
  n == null || !Number.isFinite(n) ? "—" : numberText(n, digits) + suffix;

function latestUsableMetric(observations: SatelliteObservation[], kind: SatelliteMetricType) {
  return [...observations]
    .sort((a, b) => b.observed_on.localeCompare(a.observed_on))
    .flatMap((observation) =>
      observation.metrics
        .filter((m) => m.metric_type === kind &&
          m.median != null &&
          (m.valid_pixel_percent ?? 0) >= 80)
        .map((metric) => ({ observation, metric })))
    [0] ?? null;
}

export default function FieldReport({
  farm, field, season, cropCycle, timeline, observations,
  timelineLoading, timelineError, satelliteLoading, satelliteError,
}: Props) {
  const [weather, setWeather] = useState<FieldWeather | null>(null);
  const [weatherError, setWeatherError] = useState<string | null>(null);
  const [weatherLoading, setWeatherLoading] = useState(false);
  const [change, setChange] = useState<FieldSatelliteChange | null>(null);
  const [changeError, setChangeError] = useState<string | null>(null);
  const [changeLoading, setChangeLoading] = useState(false);
  const [reload, setReload] = useState(0);

  const ndvi = useMemo(() => latestUsableMetric(observations, "ndvi"), [observations]);
  const ndmi = useMemo(() => latestUsableMetric(observations, "ndmi"), [observations]);
  const radar = useMemo(() => latestUsableMetric(observations, "sar_rvi"), [observations]);

  useEffect(() => {
    let cancelled = false;
    setWeatherLoading(true);
    setWeatherError(null);
    setWeather(null);
    void getFieldWeather(field.id)
      .then((result) => { if (!cancelled) setWeather(result); })
      .catch(() => { if (!cancelled) setWeatherError("Weather data is unavailable right now."); })
      .finally(() => { if (!cancelled) setWeatherLoading(false); });
    return () => { cancelled = true; };
  }, [field.id, reload]);

  useEffect(() => {
    let cancelled = false;
    setChange(null);
    setChangeError(null);
    if (!ndvi) return;
    setChangeLoading(true);
    void getSatelliteChange(field.id, "ndvi", "previous")
      .then((result) => { if (!cancelled) setChange(result); })
      .catch(() => { if (!cancelled) setChangeError("A comparable NDVI change is unavailable."); })
      .finally(() => { if (!cancelled) setChangeLoading(false); });
    return () => { cancelled = true; };
  }, [field.id, ndvi?.observation.id, reload]);

  const activities = useMemo(() =>
    timeline
      .filter((item) => !season || item.season_id === season.id)
      .sort((a, b) => b.occurred_at.localeCompare(a.occurred_at)),
    [timeline, season]);

  const historicalWeather = useMemo(() => {
    if (!weather) return [];
    const today = new Date().toISOString().slice(0, 10);
    return weather.days
      .filter((day) => day.date <= today)
      .sort((a, b) => b.date.localeCompare(a.date))
      .slice(0, 7);
  }, [weather]);
  const rainReadings = historicalWeather.filter((day) => day.precipitation_mm != null);
  const rainfall = rainReadings.length
    ? rainReadings.reduce((sum, day) => sum + (day.precipitation_mm ?? 0), 0)
    : null;

  const harvested = cropCycle?.yield_kg != null && cropCycle.harvested_area_acres != null
    && cropCycle.harvested_area_acres > 0
    ? cropCycle.yield_kg / cropCycle.harvested_area_acres
    : null;
  const grossValue = cropCycle?.yield_kg != null && cropCycle.selling_price_per_kg != null
    ? cropCycle.yield_kg * cropCycle.selling_price_per_kg
    : null;
  const latestScenes = useMemo(() =>
    [...observations].sort((a, b) => b.observed_on.localeCompare(a.observed_on)).slice(0, 6),
    [observations]);
  const observationValue = (observation: SatelliteObservation, kind: SatelliteMetricType) => {
    const m = observation.metrics.find((item) => item.metric_type === kind
      && (item.valid_pixel_percent ?? 0) >= 80);
    return valueOrDash(m?.median, "", 3);
  };

  return (
    <article className="workspace-page report-page" aria-label="Field report">
      <div className="report-heading">
        <div>
          <span className="workspace-eyebrow">FIELD REPORT · {dateText(new Date().toISOString())}</span>
          <h2>{field.name}</h2>
          <p>{farm.name} · {season?.name ?? "All seasons"} · {numberText(field.area_acres)} acres</p>
        </div>
        <div className="report-actions">
          <button type="button" className="secondary-action" onClick={() => setReload((v) => v + 1)}>
            <RefreshCcw size={16} /> Refresh data
          </button>
          <button type="button" className="primary-action" onClick={() => window.print()}>
            <Printer size={16} /> Print / Save PDF
          </button>
        </div>
      </div>

      <div className="report-summary-grid">
        <div className="report-stat"><span>Field area</span><strong>{numberText(field.area_acres)} ac</strong><small>{numberText(field.area_hectares)} hectares</small></div>
        <div className="report-stat"><span>Recorded activities</span><strong>{timelineLoading ? "…" : timelineError ? "—" : numberText(activities.length, 0)}</strong><small>{season ? "Selected season" : "All seasons"}</small></div>
        <div className="report-stat"><span>Latest usable NDVI</span><strong>{satelliteLoading ? "…" : valueOrDash(ndvi?.metric.median, "", 3)}</strong><small>{ndvi ? dateText(ndvi.observation.observed_on) : "No ≥80% coverage observation"}</small></div>
        <div className="report-stat"><span>Latest usable NDMI</span><strong>{satelliteLoading ? "…" : valueOrDash(ndmi?.metric.median, "", 3)}</strong><small>{ndmi ? dateText(ndmi.observation.observed_on) : "No ≥80% coverage observation"}</small></div>
      </div>

      <div className="report-section-grid">
        <section className="report-section">
          <h3><Sprout size={19} /> Crop & harvest</h3>
          <dl className="report-key-values">
            <div><dt>Season</dt><dd>{season?.name ?? "Not selected"}</dd></div>
            <div><dt>Crop</dt><dd>{cropCycle?.crop_name ?? "Not recorded"}{cropCycle?.variety ? " · " + cropCycle.variety : ""}</dd></div>
            <div><dt>Crop status</dt><dd>{cropCycle?.status ?? "No crop cycle"}</dd></div>
            <div><dt>Planted</dt><dd>{dateText(cropCycle?.planted_on)}</dd></div>
            <div><dt>Harvested</dt><dd>{dateText(cropCycle?.harvested_on)}</dd></div>
            <div><dt>Total harvest</dt><dd>{valueOrDash(cropCycle?.yield_kg, " kg", 0)}</dd></div>
            <div><dt>Yield per harvested acre</dt><dd>{valueOrDash(harvested, " kg/ac", 0)}</dd></div>
            <div><dt>Estimated gross value</dt><dd>{grossValue == null ? "—" : "₹" + numberText(grossValue, 0)}</dd></div>
          </dl>
          <p className="report-note">Gross value is not profit; no costs have been deducted.</p>
        </section>

        <section className="report-section">
          <h3><CloudRain size={19} /> Weather context</h3>
          {weatherLoading ? <p className="report-note">Loading weather…</p> :
            weatherError ? <p className="report-note" role="status">{weatherError}</p> :
            <div className="report-weather">
              <span>Modeled precipitation · most recent 7 days</span>
              <strong>{valueOrDash(rainfall, " mm", 1)}</strong>
              <p className="report-note">
                {rainReadings.length} of {historicalWeather.length} days have precipitation estimates.
                {weather?.warnings.length ? " Some weather periods may be incomplete." : ""}
                {" "}Weather comes from modeled regional data, not a field rain gauge.
              </p>
            </div>}
          <h4>Comparable satellite change</h4>
          {changeLoading ? <p className="report-note">Comparing observations…</p> :
            changeError ? <p className="report-note">{changeError}</p> :
            change?.status === "complete" && change.scalar.median_change != null
              ? <div className="report-weather">
                  <span>NDVI median change · previous usable observation</span>
                  <strong>{change.scalar.median_change > 0 ? "+" : ""}{numberText(change.scalar.median_change, 3)}</strong>
                  <p className="report-note">{dateText(change.before?.observed_on)} → {dateText(change.after?.observed_on)}</p>
                </div>
              : <p className="report-note">Not enough comparable observations for a date-to-date change.</p>}
        </section>
      </div>

      <section className="report-section">
        <h3><Activity size={19} /> Recent farm activities</h3>
        {timelineLoading ? <p className="report-note">Loading recorded activities…</p> :
          timelineError ? <p className="report-note" role="alert">{timelineError}</p> :
          activities.length === 0 ? <p className="report-note">No activities recorded for this period.</p> :
          <div className="report-table-scroll">
            <table className="report-table">
              <thead><tr><th>Date</th><th>Activity</th><th>Crop</th><th>Notes</th></tr></thead>
              <tbody>{activities.slice(0, 8).map((item) => (
                <tr key={item.id}>
                  <td>{dateText(item.occurred_at)}</td>
                  <td>{item.activity_type.replace(/_/g, " ")}</td>
                  <td>{item.crop_name ?? "—"}</td>
                  <td>{item.notes ?? "—"}</td>
                </tr>
              ))}</tbody>
            </table>
            {activities.length > 8 && <p className="report-note">Showing the latest 8 of {activities.length} activities.</p>}
          </div>}
      </section>

      <section className="report-section">
        <h3><FileText size={19} /> Satellite observation history</h3>
        {satelliteLoading ? <p className="report-note">Loading satellite history…</p> :
          satelliteError ? <p className="report-note" role="alert">{satelliteError}</p> :
          latestScenes.length === 0 ? <p className="report-note">No satellite observations have been ingested for this field.</p> :
          <div className="report-table-scroll">
            <table className="report-table">
              <thead><tr><th>Date</th><th>Source</th><th>NDVI median</th><th>NDMI median</th></tr></thead>
              <tbody>{latestScenes.map((observation) => (
                <tr key={observation.id}>
                  <td>{dateText(observation.observed_on)}</td>
                  <td>{observation.source}</td>
                  <td>{observationValue(observation, "ndvi")}</td>
                  <td>{observationValue(observation, "ndmi")}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>}
        {radar && <p className="report-note">Most recent usable radar RVI: {valueOrDash(radar.metric.median, "", 3)} on {dateText(radar.observation.observed_on)}. Radar readings are not a direct health diagnosis.</p>}
        <p className="report-note">NDVI/NDMI values require at least 80% valid coverage. Blank cells mean unavailable or unsuitable data, not zero. Satellite variation alone cannot diagnose disease or prescribe treatment.</p>
      </section>
    </article>
  );
}
