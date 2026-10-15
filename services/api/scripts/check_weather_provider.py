"""Local weather-provider diagnostics (never outputs credentials or request URLs).

Run from services/api:
    uv run python scripts/check_weather_provider.py \
        --latitude 30.7 --longitude 76.7 \
        --start 2026-06-18 --end 2026-10-08

Use your own field center coordinates. This is NOT an HTTP debug endpoint.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

# Running this script directly keeps services/api, not app/, on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.weather import (  # noqa: E402
    WeatherProviderError,
    _fetch_historical_forecast,
    _fetch_weather,
    _parse_daily,
    _today,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Open-Meteo history and forecast connectivity.")
    parser.add_argument("--latitude", type=float, required=True)
    parser.add_argument("--longitude", type=float, required=True)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    args = parser.parse_args()

    today = _today()
    if not (-90 <= args.latitude <= 90 and -180 <= args.longitude <= 180):
        parser.error("Invalid coordinates.")
    if args.end > today or args.start > args.end:
        parser.error("Choose a past or present date range.")
    if (args.end - args.start).days > 366:
        parser.error("Maximum 367 days per request.")

    shared = {"latitude": args.latitude, "longitude": args.longitude}
    archived_end = min(args.end, today - timedelta(days=8))
    archived = {
        **shared,
        "start_date": args.start.isoformat(),
        "end_date": archived_end.isoformat(),
    }
    candidates = []
    if args.start <= archived_end:
        candidates.extend([
            ("Historical reanalysis", lambda: _fetch_weather(archive=True, params=archived), "historical"),
            ("Historical forecast fallback", lambda: _fetch_historical_forecast(archived), "historical_forecast"),
        ])
    if args.end >= today - timedelta(days=7):
        candidates.append((
            "Recent model",
            lambda: _fetch_weather(archive=False, params={**shared, "past_days": 7, "forecast_days": 7}),
            "recent_model",
        ))

    had_success = False
    for name, action, source in candidates:
        try:
            response = action()
            points = _parse_daily(response, source, today=today)
            filtered = [
                value for value in points
                if args.start <= value.date <= args.end
            ]
            usable_temperature_days = sum(
                1 for value in filtered
                if value.temperature_max_c is not None and value.temperature_min_c is not None
            )
            print(
                f"{name}: OK · {len(filtered)} days in selected range; "
                f"{usable_temperature_days} with complete daily temperatures"
            )
            had_success = had_success or bool(filtered)
        except WeatherProviderError as exc:
            print(f"{name}: FAILED · {exc}")
    if not had_success:
        print("No source returned usable days. Review DNS, TLS, provider status and request limits.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
