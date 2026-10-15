import { useMemo } from "react";

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
    <div className="weather-chart-scroll">
      <svg
        className="weather-rainfall-chart"
        viewBox={"0 0 " + width + " " + height}
        role="img"
        aria-label="Daily modeled precipitation with irrigation and farm-activity markers"
      >
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
                className={isForecast ? "weather-bar forecast" : day.source === "recent_model" ? "weather-bar recent" : "weather-bar historical"}
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
      {!hasRain && <p className="weather-no-data">No precipitation readings were returned for this period.</p>}
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

          <div className="weather-chart-legend">
            <span><i className="weather-key historical" /> Historical reanalysis</span>
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
            Historical = weather reanalysis; recent = latest weather-model estimates;
            future = forecast. Values describe a model grid cell, not exact field rainfall.
            Sources may use different models and resolutions. ET₀ is reference
            evapotranspiration, not measured crop water consumption.
          </p>
        </>
      )}
    </article>
  );
}
