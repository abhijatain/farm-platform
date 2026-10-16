import { useMemo, useState } from "react";

import type {
  FieldWeather,
  FieldWeatherDay,
  SatelliteTrendActivity,
} from "../types/api";


type Props = {
  weather: FieldWeather | null;
  loading: boolean;
  error: string | null;
  activities: SatelliteTrendActivity[];
  startDate: string;
  endDate: string;
  degreeDayBaseC?: number | null;
};

const DAY_MS = 86_400_000;

function utcDate(value: string) {
  return new Date(value.slice(0, 10) + "T00:00:00Z").getTime();
}

function dateLabel(value: string) {
  return new Date(utcDate(value)).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
  });
}

function rainfallTotal(days: FieldWeatherDay[]) {
  const valid = days
    .map((day) => day.precipitation_mm)
    .filter((value): value is number => value != null && Number.isFinite(value));
  return valid.length > 0
    ? { total: valid.reduce((sum, value) => sum + value, 0), complete: valid.length === days.length }
    : null;
}

function amount(value: number | null | undefined, unit: string, digits = 1) {
  return value != null && Number.isFinite(value)
    ? value.toFixed(digits) + " " + unit
    : "—";
}

function RainfallChart({
  days,
  activities,
  startDate,
  endDate,
}: {
  days: FieldWeatherDay[];
  activities: SatelliteTrendActivity[];
  startDate: string;
  endDate: string;
}) {
  const [hoveredDate, setHoveredDate] = useState<string | null>(null);
  const plotted = days.filter((day) =>
    day.precipitation_mm != null && Number.isFinite(day.precipitation_mm) && day.precipitation_mm >= 0
  );
  const latest = plotted[plotted.length - 1];
  const width = 960;
  const height = 230;
  const left = 52;
  const right = 24;
  const top = 20;
  const bottom = 40;
  const plotHeight = height - top - bottom;
  const start = utcDate(startDate);
  const end = Math.max(utcDate(endDate), start + DAY_MS);
  const span = end - start;
  const x = (day: string) => left + (utcDate(day) - start) / span * (width - left - right);
  const values = days
    .map((d) => d.precipitation_mm)
    .filter((v): v is number => v != null && Number.isFinite(v) && v >= 0);
  const maxRain = Math.max(5, ...values);
  const barWidth = Math.max(2, Math.min(9, (width - left - right) / Math.max(1, span / DAY_MS + 1) * 0.78));
  const y = (mm: number) => top + plotHeight * (1 - mm / maxRain);
  const hasRain = values.length > 0;

  return (
    <div className="weather-metric-chart-card">
      <div className="weather-metric-chart-heading">
        <div>
          <strong>Daily precipitation</strong>
          <p>Weather-model rainfall. Hover a bar or chart date to read the actual model value.</p>
        </div>
        <div className="weather-metric-latest">
          <span>Latest daily rain</span><strong>{amount(latest?.precipitation_mm, "mm")}</strong>
          <small>{latest ? dateLabel(latest.date) : "No data"}</small>
        </div>
      </div>
      <div className="weather-chart-scroll">
      <svg
        className="weather-rainfall-chart"
        viewBox={"0 0 " + width + " " + height}
        role="img"
        aria-label="Daily modeled precipitation with irrigation and farm-activity markers"
        onPointerMove={(event) => {
          if (!plotted.length) return;
          const bounds = event.currentTarget.getBoundingClientRect();
          if (!bounds.width) return;
          const sx = (event.clientX - bounds.left) * width / bounds.width;
          const hoverTime = start + ((sx-left)/(width-left-right))*span;
          const nearest = plotted.reduce((best, day) =>
            Math.abs(utcDate(day.date)-hoverTime) < Math.abs(utcDate(best.date)-hoverTime)
              ? day : best
          );
          setHoveredDate(nearest.date);
        }}
        onPointerLeave={() => setHoveredDate(null)}
      >
        {hoveredDate && <line className="weather-hover-line"
          x1={x(hoveredDate)} x2={x(hoveredDate)} y1={top} y2={height-bottom} />}
        {[0, 0.5, 1].map((ratio) => (
          <g key={ratio}>
            <line className="weather-gridline" x1={left} x2={width - right} y1={top + (1 - ratio) * plotHeight} y2={top + (1 - ratio) * plotHeight} />
            <text className="weather-axis-label" x={left - 9} y={top + (1 - ratio) * plotHeight + 3} textAnchor="end">
              {(maxRain * ratio).toFixed(0)}
            </text>
          </g>
        ))}
        {days.filter((day) => day.precipitation_mm != null && day.precipitation_mm >= 0).map((day) => {
          const dateX = x(day.date);
          const mm = day.precipitation_mm ?? 0;
          const isForecast = day.source === "forecast";
          return (
            <g key={day.date}>
              <rect
                x={dateX - barWidth / 2}
                y={y(mm)}
                width={barWidth}
                height={Math.max(1, top + plotHeight - y(mm))}
                className={isForecast ? "weather-bar forecast" : day.source === "historical_forecast" ? "weather-bar historical-forecast" : day.source === "recent_model" ? "weather-bar recent" : "weather-bar historical"}
              />
              <title>
                {dateLabel(day.date) + " · " + amount(mm, "mm") + " precipitation · " + day.source.replace("_", " ") +
                  " · max " + amount(day.temperature_max_c, "°C")}
              </title>
            </g>
          );
        })}
        {activities.map((activity) => {
          const activityDate = activity.occurred_at.slice(0, 10);
          const markerX = x(activityDate);
          if (markerX < left || markerX > width - right) return null;
          return (
            <g key={activity.id}>
              <line
                className="weather-activity-line"
                x1={markerX} x2={markerX} y1={top} y2={height - bottom}
              />
              <title>{activityDate + " · " + activity.activity_type.replace(/_/g, " ") + (activity.notes ? " · " + activity.notes : "")}</title>
            </g>
          );
        })}
        {Array.from({ length: 5 }, (_, i) => {
          const time = start + (span * i) / 4;
          const date = new Date(time).toISOString().slice(0, 10);
          return (
            <text key={i} x={left + (width - left - right) * i / 4} y={height - 15} textAnchor="middle" className="weather-axis-label">
              {dateLabel(date)}
            </text>
          );
        })}
        <text className="weather-axis-title" x={left} y={10}>Rainfall (mm)</text>
      </svg>
      {hoveredDate && plotted.find((day) => day.date === hoveredDate) && (
        <div className="weather-hover-readout" role="status">
          <strong>{dateLabel(hoveredDate)}</strong>
          <span>{amount(plotted.find((day) => day.date === hoveredDate)?.precipitation_mm, "mm")} modeled rain</span>
          <small>{plotted.find((day) => day.date === hoveredDate)?.source.replace(/_/g," ")}</small>
        </div>
      )}
      {!hasRain && <p className="weather-no-data">No precipitation readings were returned for this period.</p>}
      </div>
    </div>
  );
}


/** Cumulative available-day heat sum. Missing days are not filled or guessed. */
function GrowingHeatChart({ days, baseC }: { days: FieldWeatherDay[]; baseC: number }) {
  const [hovered, setHovered] = useState<number | null>(null);
  const observed = days
    .filter((day) =>
      day.source !== "forecast" &&
      day.temperature_max_c != null && Number.isFinite(day.temperature_max_c) &&
      day.temperature_min_c != null && Number.isFinite(day.temperature_min_c)
    )
    .sort((a,b) => a.date.localeCompare(b.date));
  let running = 0;
  const points = observed.map((day) => {
    const increment = Math.max(0, ((day.temperature_max_c ?? 0) + (day.temperature_min_c ?? 0))/2 - baseC);
    running += increment;
    return {date:day.date, daily:increment, total:running};
  });
  if (!points.length) return <p className="weather-context-status">No temperature history available for accumulated heat estimates.</p>;
  const width=960, height=210, left=50, right=22, top=18, bottom=35;
  const low=utcDate(points[0].date), high=Math.max(low+DAY_MS,utcDate(points[points.length-1].date));
  const max=Math.max(5,points[points.length-1].total);
  const x=(date:string)=>left+(utcDate(date)-low)/(high-low)*(width-left-right);
  const y=(total:number)=>height-bottom-total/max*(height-top-bottom);
  const active = hovered == null ? null : points[hovered];
  return (
    <div className="weather-metric-chart-card">
      <div className="weather-metric-chart-heading">
        <div>
          <strong>Accumulated growing-degree days (estimated)</strong>
          <p>Daily mean temperature above {baseC} °C, summed only over available dates in this view. Missing days are not filled.</p>
        </div>
        <div className="weather-metric-latest">
          <span>Available-day total</span>
          <strong>{points[points.length-1].total.toFixed(0)} °C·days</strong>
          <small>{points.length} modeled days</small>
        </div>
      </div>
      <div className="weather-chart-scroll">
        <svg className="weather-rainfall-chart" viewBox={`0 0 ${width} ${height}`}
          role="img" aria-label="Estimated accumulated heat for available modeled weather dates"
          onPointerMove={(event)=>{
            const bounds=event.currentTarget.getBoundingClientRect();
            if(!bounds.width)return;
            const cursorX=(event.clientX-bounds.left)*width/bounds.width;
            let nearest=0;
            for(let i=1;i<points.length;i++){
              if(Math.abs(x(points[i].date)-cursorX)<Math.abs(x(points[nearest].date)-cursorX))nearest=i;
            }
            setHovered(nearest);
          }}
          onPointerLeave={()=>setHovered(null)}>
          {[0,0.5,1].map(f => <g key={f}>
            <line className="weather-gridline" x1={left} x2={width-right} y1={y(max*f)} y2={y(max*f)}/>
            <text className="weather-axis-label" x={left-8} y={y(max*f)+4} textAnchor="end">{(max*f).toFixed(0)}</text>
          </g>)}
          <path d={points.map((p,i)=>`${i===0?"M":"L"} ${x(p.date).toFixed(2)} ${y(p.total).toFixed(2)}`).join(" ")}
            stroke="#e5912f" strokeWidth={3} fill="none" strokeLinecap="round" strokeLinejoin="round"/>
          {active && <g>
            <line className="weather-hover-line" x1={x(active.date)} x2={x(active.date)} y1={top} y2={height-bottom}/>
            <circle cx={x(active.date)} cy={y(active.total)} r={5} fill="#cb6d13" stroke="white" strokeWidth={2}/>
          </g>}
          <text x={left} y={height-8} className="weather-axis-label">{dateLabel(points[0].date)}</text>
          <text x={width-right} y={height-8} textAnchor="end" className="weather-axis-label">{dateLabel(points[points.length-1].date)}</text>
        </svg>
        {active && <div className="weather-hover-readout" role="status">
          <strong>{dateLabel(active.date)}</strong>
          <span>{active.total.toFixed(1)} °C·days accumulated</span>
          <small>{active.daily.toFixed(1)} °C·days this day · modeled</small>
        </div>}
      </div>
      <p className="weather-heat-note">Not a full-season total unless every growing-season date is included. This temperature-based estimate does not independently determine crop stage.</p>
    </div>
  );
}

export default function WeatherContextPanel({
  weather,
  loading,
  error,
  activities,
  startDate,
  endDate,
  degreeDayBaseC,
}: Props) {
  const today = new Date().toISOString().slice(0, 10);

  const historicDays = useMemo(
    () => weather?.days.filter((day) => day.date <= today && day.date >= startDate && day.date <= endDate) ?? [],
    [weather, today, startDate, endDate],
  );
  const recent = historicDays.filter((day) => utcDate(day.date) >= utcDate(today) - 6 * DAY_MS);
  const forecast = weather?.days.filter((day) => day.source === "forecast") ?? [];
  const recentRain = rainfallTotal(recent);
  const forecastRain = rainfallTotal(forecast);
  const latest = historicDays[historicDays.length - 1];

  const plottedStart = Math.max(
    utcDate(startDate),
    utcDate(endDate) - 89 * DAY_MS,
  );
  const chartStart = new Date(plottedStart).toISOString().slice(0, 10);
  const chartEnd = forecast.length > 0 ? forecast[forecast.length - 1].date : endDate;
  const chartDays = weather?.days.filter((day) => day.date >= chartStart && day.date <= chartEnd) ?? [];

  return (
    <article className="weather-context-panel">
      <div className="weather-context-heading">
        <div>
          <span className="workspace-eyebrow">WEATHER CONTEXT</span>
          <h4>Rainfall, temperature and field conditions</h4>
          <p>
            Gridded modeled weather at the field center. Not an on-farm station reading.
            Use rainfall alongside radar changes as context, not proof of cause.
          </p>
        </div>
        <span className="weather-provider-label">Open-Meteo · local-day totals</span>
      </div>

      {loading && <p className="weather-context-status">Loading field weather history and forecast…</p>}
      {error && !loading && (
        <p className="weather-context-status error">
          Weather could not be loaded: {error}. Satellite trends remain available.
        </p>
      )}
      {!loading && !error && weather && (
        <>
          <div className="weather-summary-cards">
            <div>
              <span>Rain · last 7 calendar days</span>
              <strong>{amount(recentRain?.total, "mm")}</strong>
              <small>{recentRain && !recentRain.complete ? "Partial coverage" : "Modeled precipitation"}</small>
            </div>
            <div>
              <span>Latest modeled air temperature</span>
              <strong>{amount(latest?.temperature_max_c, "°C")}</strong>
              <small>{latest ? dateLabel(latest.date) + " · daily high" : "No reading"}</small>
            </div>
            <div>
              <span>Humidity · daily mean</span>
              <strong>{amount(latest?.relative_humidity_mean_percent, "%", 0)}</strong>
              <small>{latest ? dateLabel(latest.date) : "No reading"}</small>
            </div>
            <div>
              <span>Wind · daily maximum</span>
              <strong>{amount(latest?.wind_speed_max_kmh, "km/h")}</strong>
              <small>At 10 m height</small>
            </div>
            <div>
              <span>Forecast precipitation · next 6 days</span>
              <strong>{amount(forecastRain?.total, "mm")}</strong>
              <small>{forecastRain && !forecastRain.complete ? "Partial forecast" : "Forecast, not observed"}</small>
            </div>
          </div>

          <div className="weather-timeline-heading">
            <h5>Precipitation and field activities</h5>
            <span>{dateLabel(chartStart)} – {dateLabel(chartEnd)}</span>
          </div>
          {chartDays.length > 0 && (
            <RainfallChart days={chartDays} activities={activities} startDate={chartStart} endDate={chartEnd} />
          )}
          {degreeDayBaseC != null && Number.isFinite(degreeDayBaseC) && chartDays.length > 0 && (
            <GrowingHeatChart days={chartDays} baseC={degreeDayBaseC} />
          )}

          <div className="weather-chart-legend">
            <span><i className="weather-key historical" /> Historical reanalysis</span>
            <span><i className="weather-key historical-forecast" /> Historical forecast fallback</span>
            <span><i className="weather-key recent" /> Recent modeled weather</span>
            <span><i className="weather-key forecast" /> Forecast</span>
            <span><i className="weather-key activity" /> Farm activity</span>
          </div>

          {forecast.length > 0 && (
            <div className="weather-forecast-days">
              {forecast.map((day) => (
                <div key={day.date} className="weather-forecast-day">
                  <span>{dateLabel(day.date)}</span>
                  <strong>{amount(day.precipitation_mm, "mm")}</strong>
                  <small>{amount(day.temperature_min_c, "°C", 0)} – {amount(day.temperature_max_c, "°C", 0)}</small>
                  <small>Humidity {amount(day.relative_humidity_mean_percent, "%", 0)}</small>
                  <small>ET₀ {amount(day.reference_et0_mm, "mm")}</small>
                </div>
              ))}
            </div>
          )}

          {weather.warnings.map((warning) => (
            <p className="weather-warning" key={warning}>{warning}</p>
          ))}
          <p className="weather-method-note">
            Historical = reanalysis; historical forecast = archived model estimates (fallback); recent = latest weather-model estimates;
            future = forecast. Values describe a model grid cell, not exact field rainfall.
            Sources may use different models and resolutions. ET₀ is reference
            evapotranspiration, not measured crop water consumption.
          </p>
        </>
      )}
    </article>
  );
}
