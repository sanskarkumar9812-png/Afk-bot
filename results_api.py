"""
Thin client for Jolpica-F1 (https://github.com/jolpica/jolpica-f1), the
free, open-source, Ergast-compatible API that succeeded the now-retired
Ergast API. No API key needed.

Used to auto-fetch a race's top 3 finishers so prediction rounds can be
scored without an admin manually typing the result. This is a best-effort
convenience layer: if the API is unreachable, hasn't published a result
yet, or its schema changes, callers get None back and should fall back to
the manual /setresult command.
"""

import logging

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.jolpi.ca/ergast/f1"
TIMEOUT_SECONDS = 10


def get_top3_for_round(season: int, round_number: int):
    """Returns [p1_family_name, p2_family_name, p3_family_name] or None if
    the result isn't available yet / the request failed."""
    url = f"{BASE_URL}/{season}/{round_number}/results.json"
    try:
        resp = requests.get(url, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()
        races = data["MRData"]["RaceTable"]["Races"]
        if not races:
            return None  # not run yet, or round number doesn't exist

        results = races[0]["Results"]
        if len(results) < 3:
            return None

        top3 = []
        for r in results[:3]:
            driver = r["Driver"]
            # Family name alone matches how predictions are typically typed
            # (e.g. "Verstappen"); callers do case-insensitive comparison.
            top3.append(driver["familyName"])
        return top3

    except Exception as e:
        logger.warning("Jolpica fetch failed for %s round %s: %s", season, round_number, e)
        return None
