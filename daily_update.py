
"""Update daily fixture snapshots without exposing API credentials."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from io import StringIO

import requests
import pandas as pd


ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "data" / "daily_fixtures.json"
TZ = ZoneInfo("Europe/Berlin")

LEAGUES = {
    "Bundesliga": 78,
    "2. Bundesliga": 79,
    "La Liga": 140,
    "Serie A": 135,
    "Premier League": 39,
    "Ligue 1": 61,
    "MLS": 253,
}

KEY = os.environ.get("API_SPORTS_KEY", "").strip()
DEL_ID = os.environ.get("DEL_LEAGUE_ID", "").strip()


def fetch(url, *, params=None, headers=None):
    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=25,
        )

        if response.status_code >= 400:
            try:
                details = response.json()

                if isinstance(details, dict):
                    details = {
                        k: v
                        for k, v in details.items()
                        if k in ("errors", "message", "error", "results")
                    }

            except ValueError:
                details = "No JSON error details returned"

            print(
                f"API request failed: HTTP {response.status_code}, "
                f"endpoint={url}, details={str(details)[:700]}"
            )
            return None

        obj = response.json()

        if isinstance(obj, dict) and obj.get("errors"):
            print(
                f"API returned errors: endpoint={url}, "
                f"details={str(obj['errors'])[:700]}"
            )
            return None

        return obj

    except (requests.RequestException, ValueError) as exc:
        print(
            f"Fetch unavailable: endpoint={url}, "
            f"error={type(exc).__name__}"
        )
        return None


def main():
    now = datetime.now(TZ)

    days = [
        (now.date() + timedelta(days=i)).isoformat()
        for i in (0, 1)
    ]

    snapshot = {
        "updated_at": now.isoformat(),
        "dates": days,
        "nhl": {},
        "football": {},
        "del": {},
    }

    print(
        f"API_SPORTS_KEY configured: "
        f"{'yes' if KEY else 'no'} "
        f"(value never displayed)"
    )

    for date in days:

        # NHL
        nhl = fetch(
            f"https://api-web.nhle.com/v1/score/{date}"
        )

        if nhl is not None:
            snapshot["nhl"][date] = nhl

        if KEY:
            headers = {
                "x-apisports-key": KEY
            }

            # Football
            for league, ident in LEAGUES.items():

                year = (
                    int(date[:4])
                    if league == "MLS" or int(date[5:7]) >= 7
                    else int(date[:4]) - 1
                )

                obj = fetch(
                    "https://v3.football.api-sports.io/fixtures",
                    params={
                        "league": ident,
                        "season": year,
                        "date": date,
                        "timezone": "Europe/Berlin",
                    },
                    headers=headers,
                )

                if obj is not None:
                    snapshot["football"][f"{league}|{date}"] = (
                        obj.get("response", [])
                    )

            # DEL
            if DEL_ID:

                season = (
                    int(date[:4])
                    if int(date[5:7]) >= 7
                    else int(date[:4]) - 1
                )

                obj = fetch(
                    "https://v1.hockey.api-sports.io/games",
                    params={
                        "league": DEL_ID,
                        "season": season,
                        "date": date,
                        "timezone": "Europe/Berlin",
                    },
                    headers=headers,
                )

                if obj is not None:
                    snapshot["del"][date] = obj.get("response", [])

    if not any(snapshot[k] for k in ("nhl", "football", "del")):
        raise SystemExit(
            "No valid data retrieved; preserving previous snapshot."
        )

    TARGET.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    TARGET.write_text(
        json.dumps(
            snapshot,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    actual_matches = sum(
        len(items)
        for items in snapshot["football"].values()
    )

    del_matches = sum(
        len(items)
        for items in snapshot["del"].values()
    )

    print(
        f"Updated {TARGET}: {now.isoformat()}, "
        f"NHL dates={len(snapshot['nhl'])}, "
        f"football entries={len(snapshot['football'])}, "
        f"football matches={actual_matches}, "
        f"DEL matches={del_matches}"
    )


def test_del_player_stats():
    """Test access to the official DEL player statistics table."""

    url = (
        "https://www.penny-del.org/statistik/"
        "saison-2026-27/hauptrunde/playerstats/basis"
    )

    try:
        response = requests.get(
            url,
            timeout=25,
            headers={
                "User-Agent": "Mozilla/5.0 SportRadar/1.0"
            },
        )

        print(
            f"DEL Statistiktest: HTTP {response.status_code}"
        )

        print(
            f"DEL Statistiktest: "
            f"HTML-Zeichen={len(response.text)}"
        )

        has_table = "<table" in response.text.lower()

        print(
            f"DEL Statistiktest: "
            f"Tabellen vorhanden={has_table}"
        )

        if response.status_code != 200 or not has_table:
            print(
                "DEL Statistiktest: "
                "Keine auswertbare HTML-Tabelle gefunden."
            )
            return

        tables = pd.read_html(
            StringIO(response.text)
        )

        print(
            f"DEL Statistiktest: "
            f"Anzahl Tabellen={len(tables)}"
        )

        for index, table in enumerate(tables[:5], start=1):
            print(
                f"DEL Statistiktest: "
                f"Tabelle {index}: "
                f"Zeilen={len(table)}, "
                f"Spalten={list(map(str, table.columns))}"
            )

    except (requests.RequestException, ValueError, ImportError) as exc:
        print(
            f"DEL Statistiktest fehlgeschlagen: "
            f"{type(exc).__name__}: {str(exc)[:200]}"
        )


if __name__ == "__main__":
    main()
    test_del_player_stats()
