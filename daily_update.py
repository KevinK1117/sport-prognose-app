"""Update daily fixture snapshots without exposing API credentials."""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

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
    "Champions League": 2,
    "Europa League": 3,
    "Saudi Pro League": 307,
}
KEY = os.environ.get("API_SPORTS_KEY", "").strip()
DEL_ID = os.environ.get("DEL_LEAGUE_ID", "").strip()


def fetch(url, *, params=None, headers=None):
    try:
        response = requests.get(url, params=params, headers=headers, timeout=25)
        if response.status_code >= 400:
            # Show the provider's reason without printing the request headers/API key.
            try:
                details = response.json()
                if isinstance(details, dict):
                    details = {k: v for k, v in details.items() if k in ("errors", "message", "error", "results")}
            except ValueError:
                details = "No JSON error details returned"
            print(f"API request failed: HTTP {response.status_code}, endpoint={url}, details={str(details)[:700]}")
            return None
        obj = response.json()
        if isinstance(obj, dict) and obj.get("errors"):
            print(f"API returned errors: endpoint={url}, details={str(obj['errors'])[:700]}")
            return None
        return obj
    except (requests.RequestException, ValueError) as exc:
        print(f"Fetch unavailable: endpoint={url}, error={type(exc).__name__}")
        return None


def main():
    now = datetime.now(TZ)
    days = [(now.date() + timedelta(days=i)).isoformat() for i in (0, 1)]
    snapshot = {"updated_at": now.isoformat(), "dates": days, "nhl": {}, "football": {}, "del": {}}
    # Keep separately populated DEL player data across fixture refreshes.
    try:
        old = json.loads(TARGET.read_text(encoding="utf-8"))
        for field in ("del_player_stats", "del_team_names"):
            if isinstance(old.get(field), dict):
                snapshot[field] = old[field]
    except (OSError, ValueError, AttributeError):
        pass
    print(f"API_SPORTS_KEY configured: {'yes' if KEY else 'no'} (value never displayed)")

    for date in days:
        nhl = fetch(f"https://api-web.nhle.com/v1/score/{date}")
        if nhl is not None:
            snapshot["nhl"][date] = nhl

        if KEY:
            headers = {"x-apisports-key": KEY}
            for league, ident in LEAGUES.items():
                year = int(date[:4]) if league == "MLS" or int(date[5:7]) >= 7 else int(date[:4]) - 1
                obj = fetch(
                    "https://v3.football.api-sports.io/fixtures",
                    params={"league": ident, "season": year, "date": date, "timezone": "Europe/Berlin"},
                    headers=headers,
                )
                if obj is not None:
                    snapshot["football"][f"{league}|{date}"] = obj.get("response", [])

            if DEL_ID:
                obj = fetch(
                    "https://v1.hockey.api-sports.io/games",
                    params={"league": DEL_ID, "date": date, "timezone": "Europe/Berlin"},
                    headers=headers,
                )
                if obj is not None:
                    snapshot["del"][date] = obj.get("response", [])

    if not any(snapshot[k] for k in ("nhl", "football", "del")):
        raise SystemExit("No valid data retrieved; preserving previous snapshot.")

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    actual_matches = sum(len(items) for items in snapshot["football"].values())
    print(f"Updated {TARGET}: {now.isoformat()}, NHL dates={len(snapshot['nhl'])}, football entries={len(snapshot['football'])}, football matches={actual_matches}")


if __name__ == "__main__":
    main()
