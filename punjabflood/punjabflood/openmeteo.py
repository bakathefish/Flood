"""Keyless Open-Meteo client with a disk cache and quota-aware retries.

Endpoints used (all free, no key, attribution "Weather data by Open-Meteo.com"):

* ``archive-api``: ERA5 (0.25 degree) precipitation with ERA5-Land soil moisture, daily,
  from 1950; the last few days are ERA5T and may be revised, so the cache key carries the
  end date and callers re-pull recent windows.
* ``api`` (forecast): deterministic daily QPF from GFS, ECMWF IFS 0.25, ICON and the
  best-match blend, up to 16 days.
* ``ensemble-api``: ECMWF IFS 0.25 ensemble (51 members) daily precipitation.
* ``historical-forecast-api``: archived forecasts. Plain variables are stitched from the
  shortest lead; the ``_previous_dayN`` hourly variables give the forecast for each hour as
  issued N days earlier. Measured 2026-09-05: previous-day variables exist from
  2024-02 for gfs_seamless, ecmwf_ifs025, icon_seamless, gem_seamless and best_match;
  the stitched series exist from 2021 (GFS) and 2017 (ecmwf_ifs 0.4 degree).

Rate limits are per subdomain. A 429 whose reason says "Minutely" waits a minute; "Hourly"
waits to the next hour; "Daily" raises ``QuotaExhausted`` so the caller fails fast instead
of burning the next day's budget.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import requests

log = logging.getLogger(__name__)

HOSTS = {
    "archive": "https://archive-api.open-meteo.com/v1/archive",
    "forecast": "https://api.open-meteo.com/v1/forecast",
    "ensemble": "https://ensemble-api.open-meteo.com/v1/ensemble",
    "historical": "https://historical-forecast-api.open-meteo.com/v1/forecast",
}
ATTRIBUTION = "Weather data by Open-Meteo.com (CC BY 4.0)"
ARCHIVE_DAILY = (
    "precipitation_sum",
    "soil_moisture_0_to_7cm_mean",
    "soil_moisture_7_to_28cm_mean",
)


class QuotaExhausted(RuntimeError):
    """The daily request budget for a subdomain is spent; try again tomorrow."""


class OpenMeteoError(RuntimeError):
    pass


def canonical(params: dict) -> str:
    """Order-independent, list-tolerant string form of the query, used for the cache key."""
    norm = {}
    for k, v in params.items():
        if isinstance(v, list | tuple):
            v = ",".join(str(x) for x in v)
        norm[str(k)] = str(v)
    return json.dumps(norm, sort_keys=True, separators=(",", ":"))


class OpenMeteo:
    def __init__(
        self,
        cache_dir: Path | str = "data/cache/openmeteo",
        session: requests.Session | None = None,
        sleep=time.sleep,
        spacing_s: float = 0.25,
        timeout_s: float = 90.0,
        max_retries: int = 6,
        clock=None,
    ):
        self.cache_dir = Path(cache_dir)
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", "punjabflood/0.1 (keyless research client)")
        self.sleep = sleep
        self.spacing_s = spacing_s
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.clock = clock or (lambda: datetime.now(UTC))
        self._last = 0.0
        self.calls = 0
        self.cache_hits = 0

    # -- cache ------------------------------------------------------------------------
    def _cache_path(self, host: str, params: dict) -> Path:
        key = hashlib.sha1(canonical(params).encode("utf-8")).hexdigest()
        return self.cache_dir / host / f"{key}.json"

    # -- transport --------------------------------------------------------------------
    def get(self, host: str, params: dict, use_cache: bool = True) -> dict:
        url = HOSTS[host]
        path = self._cache_path(host, params)
        if use_cache and path.exists():
            self.cache_hits += 1
            return json.loads(path.read_text(encoding="utf-8"))["response"]
        query = {
            k: (",".join(map(str, v)) if isinstance(v, list | tuple) else v)
            for k, v in params.items()
        }
        for attempt in range(self.max_retries + 1):
            gap = self.spacing_s - (time.monotonic() - self._last)
            if gap > 0:
                self.sleep(gap)
            self._last = time.monotonic()
            self.calls += 1
            try:
                r = self.session.get(url, params=query, timeout=self.timeout_s)
            except requests.RequestException as exc:
                if attempt >= self.max_retries:
                    raise
                log.warning("open-meteo %s: %s; retry in 10 s", host, type(exc).__name__)
                self.sleep(10)
                continue
            if r.status_code == 200:
                j = r.json()
                if j.get("error"):
                    raise OpenMeteoError(j.get("reason", "unknown error"))
                if use_cache:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(
                        json.dumps(
                            {
                                "params": params,
                                "fetched_utc": self.clock().isoformat(),
                                "response": j,
                            }
                        ),
                        encoding="utf-8",
                    )
                return j
            if r.status_code == 429:
                reason = ""
                try:
                    reason = r.json().get("reason", "")
                except ValueError:
                    reason = r.text
                self._wait_for_quota(reason)
                continue
            if r.status_code >= 500 and attempt < self.max_retries:
                log.warning("open-meteo %s: HTTP %s; retry in 15 s", host, r.status_code)
                self.sleep(15)
                continue
            try:
                reason = r.json().get("reason", r.text[:200])
            except ValueError:
                reason = r.text[:200]
            raise OpenMeteoError(f"HTTP {r.status_code}: {reason}")
        raise OpenMeteoError(f"retry budget exhausted for {host} {params}")

    def _wait_for_quota(self, reason: str) -> None:
        low = reason.lower()
        if "daily" in low:
            raise QuotaExhausted(reason)
        if "hourly" in low:
            now = self.clock()
            secs = (60 - now.minute) * 60 - now.second + 5
            log.warning("open-meteo hourly limit; sleeping %d s", secs)
            self.sleep(secs)
            return
        log.info("open-meteo minutely limit; sleeping 61 s")
        self.sleep(61)

    # -- endpoints --------------------------------------------------------------------
    def archive_daily(
        self,
        lat: float,
        lon: float,
        start: str,
        end: str,
        daily: Iterable[str] = ARCHIVE_DAILY,
    ) -> dict:
        return self.get(
            "archive",
            {
                "latitude": lat,
                "longitude": lon,
                "start_date": start,
                "end_date": end,
                "daily": list(daily),
                "timezone": "UTC",
            },
        )

    def forecast_daily(
        self,
        lat: float,
        lon: float,
        models: Iterable[str] = ("gfs_seamless", "ecmwf_ifs025", "icon_seamless", "best_match"),
        days: int = 10,
        issue_date: str | None = None,
        past_days: int = 0,
    ) -> dict:
        """Deterministic daily QPF per model. ``issue_date`` (UTC date) is part of the cache
        key so one pull per day is kept and a later run the same day is served from disk.
        ``past_days`` adds the model's recent days (its analysis of rain already fallen)."""
        issue_date = issue_date or self.clock().date().isoformat()
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": ["precipitation_sum"],
            "models": list(models),
            "forecast_days": days,
            "timezone": "UTC",
            "_issue_date": issue_date,
        }
        if past_days:
            params["past_days"] = int(past_days)
        return self.get("forecast", params)

    def ensemble_daily(
        self,
        lat: float,
        lon: float,
        model: str = "ecmwf_ifs025",
        days: int = 7,
        issue_date: str | None = None,
    ) -> dict:
        issue_date = issue_date or self.clock().date().isoformat()
        return self.get(
            "ensemble",
            {
                "latitude": lat,
                "longitude": lon,
                "daily": ["precipitation_sum"],
                "models": model,
                "forecast_days": days,
                "timezone": "UTC",
                "_issue_date": issue_date,
            },
        )

    def previous_runs_hourly(
        self,
        lat: float,
        lon: float,
        model: str,
        start: str,
        end: str,
        leads: Iterable[int] = (1, 2, 3, 4, 5, 6, 7),
    ) -> dict:
        """Archived as-issued hourly precipitation: ``precipitation_previous_dayN`` is the
        value for that hour from the run issued N days earlier (plus ``precipitation`` for
        the shortest lead)."""
        hourly = ["precipitation"] + [f"precipitation_previous_day{n}" for n in leads]
        return self.get(
            "historical",
            {
                "latitude": lat,
                "longitude": lon,
                "start_date": start,
                "end_date": end,
                "hourly": hourly,
                "models": model,
                "timezone": "UTC",
            },
        )
