"""Bounded read-only weather and carbon intensity adapter.

Uses Open-Meteo (no API key) for weather and Electricity Maps (free tier)
for grid carbon intensity. Both are fixed public endpoints with no
credentials required for basic use.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Any

WEATHER_ENDPOINT = "https://api.open-meteo.com/v1/forecast"
CARBON_ENDPOINT = "https://api.electricitymap.org/v3/carbon-intensity/latest"
MAX_RESPONSE_BYTES = 500_000
REQUEST_TIMEOUT = 8


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _filter_lat_lon(value: str, field: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field} is required")
    if len(value) > 20 or not re.fullmatch(r"-?\d+\.?\d*", value):
        raise ValueError(f"{field} must be a valid latitude/longitude")
    num = float(value)
    if field == "latitude" and not -90 <= num <= 90:
        raise ValueError("latitude must be between -90 and 90")
    if field == "longitude" and not -180 <= num <= 180:
        raise ValueError("longitude must be between -180 and 180")
    return value


def _get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "DataCenterCommander/0.1"},
        method="GET",
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=REQUEST_TIMEOUT) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ConnectionError("Response exceeded the 500 KB safety limit")
        payload = json.loads(raw or b"{}")
    except urllib.error.HTTPError as exc:
        raise ConnectionError(f"HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionError(f"Service unavailable ({type(exc).__name__})") from None
    except json.JSONDecodeError:
        raise ConnectionError("Invalid JSON response") from None
    if not isinstance(payload, dict):
        raise ConnectionError("Unexpected response format")
    return payload


def fetch_weather(
    *,
    latitude: str,
    longitude: str,
    forecast_days: int = 1,
) -> dict[str, Any]:
    """Fetch current weather and forecast from Open-Meteo.

    Returns temperature, humidity, wind speed, and weather code.
    Bounded to a single request; no pagination.
    """
    lat = _filter_lat_lon(latitude, "latitude")
    lon = _filter_lat_lon(longitude, "longitude")
    if not isinstance(forecast_days, int) or isinstance(forecast_days, bool) or not 1 <= forecast_days <= 7:
        raise ValueError("forecast_days must be an integer from 1 to 7")

    params = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,weather_code",
        "forecast_days": forecast_days,
        "timezone": "auto",
    })
    url = f"{WEATHER_ENDPOINT}?{params}"
    payload = _get_json(url)

    current = payload.get("current", {})
    daily = payload.get("daily", {})

    return {
        "provider": "Open-Meteo",
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_url": WEATHER_ENDPOINT,
        "query": {"latitude": lat, "longitude": lon, "forecast_days": forecast_days},
        "current": {
            "temperature_c": current.get("temperature_2m"),
            "relative_humidity_pct": current.get("relative_humidity_2m"),
            "weather_code": current.get("weather_code"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "time": current.get("time"),
        },
        "daily": [
            {
                "date": daily.get("time", [None])[i] if i < len(daily.get("time", [])) else None,
                "temp_max_c": daily.get("temperature_2m_max", [None])[i] if i < len(daily.get("temperature_2m_max", [])) else None,
                "temp_min_c": daily.get("temperature_2m_min", [None])[i] if i < len(daily.get("temperature_2m_min", [])) else None,
                "weather_code": daily.get("weather_code", [None])[i] if i < len(daily.get("weather_code", [])) else None,
            }
            for i in range(min(forecast_days, len(daily.get("time", []))))
        ],
        "commercial_basis": "Free public weather data; not for operational control.",
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_carbon_intensity(
    *,
    latitude: str,
    longitude: str,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Fetch current grid carbon intensity from Electricity Maps.

    Returns carbon intensity in gCO2eq/kWh for the given location.
    Requires a free API key from https://api.electricitymap.org/
    """
    lat = _filter_lat_lon(latitude, "latitude")
    lon = _filter_lat_lon(longitude, "longitude")

    key = (api_key or "").strip()
    if not key:
        raise ConnectionError(
            "ELECTRICITY_MAP_API_KEY is not configured in the server environment"
        )
    if len(key) > 512 or any(ch in key for ch in "\r\n\x00"):
        raise ValueError("Electricity Maps API key configuration is invalid")

    params = urllib.parse.urlencode({"lat": lat, "lon": lon})
    url = f"{CARBON_ENDPOINT}?{params}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "DataCenterCommander/0.1",
            "auth-token": key,
        },
        method="GET",
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=REQUEST_TIMEOUT) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ConnectionError("Response exceeded the 500 KB safety limit")
        payload = json.loads(raw or b"{}")
    except urllib.error.HTTPError as exc:
        raise ConnectionError(f"Electricity Maps returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionError(f"Electricity Maps unavailable ({type(exc).__name__})") from None
    except json.JSONDecodeError:
        raise ConnectionError("Electricity Maps returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise ConnectionError("Electricity Maps response did not match expected format")

    intensity = payload.get("carbonIntensity")
    try:
        intensity_val = Decimal(str(intensity)) if intensity is not None else None
    except (InvalidOperation, ValueError, TypeError):
        intensity_val = None

    return {
        "provider": "Electricity Maps",
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_url": CARBON_ENDPOINT,
        "query": {"latitude": lat, "longitude": lon},
        "carbon_intensity_gco2eq_per_kwh": str(intensity_val) if intensity_val is not None else None,
        "zone": payload.get("zone"),
        "datetime": payload.get("datetime"),
        "updated_at": payload.get("updatedAt"),
        "emission_factor_type": payload.get("emissionFactorType"),
        "is_estimated": payload.get("isEstimated"),
        "estimation_method": payload.get("estimationMethod"),
        "commercial_basis": "Free tier; rate-limited. Not for compliance reporting.",
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_weather_and_carbon(
    *,
    latitude: str,
    longitude: str,
    forecast_days: int = 1,
    carbon_api_key: str | None = None,
) -> dict[str, Any]:
    """Fetch both weather and carbon intensity in one call.

    Weather is always fetched (no key required). Carbon intensity requires
    an API key; if not provided, the carbon section will contain an error.
    """
    weather = fetch_weather(latitude=latitude, longitude=longitude, forecast_days=forecast_days)

    carbon_error = None
    carbon = None
    try:
        carbon = fetch_carbon_intensity(latitude=latitude, longitude=longitude, api_key=carbon_api_key)
    except (ConnectionError, ValueError) as exc:
        carbon_error = str(exc)

    return {
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "query": {"latitude": latitude, "longitude": longitude, "forecast_days": forecast_days},
        "weather": weather,
        "carbon_intensity": carbon,
        "carbon_error": carbon_error,
        "persisted": False,
        "execution_permitted": False,
    }
