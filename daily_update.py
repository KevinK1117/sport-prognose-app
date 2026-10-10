

"""Update SportRadar fixtures and DEL player statistics daily."""

import json
import os
import re
from datetime import datetime, timedelta
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
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
                        k: v for k, v in details.items()
                        if k in (
                            "errors",
                            "message",
                            "error",
                            "results",
                        )
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


def del_season(date):
    """Return DEL season start year."""
    year = int(date[:4])
    month = int(date[5:7])
    return year if month >= 7 else year - 1


class DELTeamParser(HTMLParser):
    """Extract team logo identifiers from player statistic rows."""

    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_row = False
        self.current_team = None
        self.team_ids = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)

        if tag == "table":
            self.in_table = True

        if not self.in_table:
            return

        if tag == "tr":
            self.in_row = True
            self.current_team = None

        if self.in_row and tag == "img":
            src = attributes.get("src", "")

            match = re.search(
                r"/(team_\d+)\.svg",
                src,
                flags=re.IGNORECASE,
            )

            if match:
                self.current_team = match.group(1)

    def handle_endtag(self, tag):
        if tag == "tr" and self.in_row:
            self.team_ids.append(self.current_team)
            self.in_row = False

        if tag == "table":
            self.in_table = False


def fetch_del_player_stats(season):
    """Fetch player stats and identify teams from HTML logos."""

    season_label = f"{season}-{str(season + 1)[-2:]}"

    url = (
        "https://www.penny-del.org/statistik/"
        f"saison-{season_label}/hauptrunde/playerstats/basis"
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
            f"DEL Spielerstatistik: HTTP {response.status_code}"
        )

        response.raise_for_status()

        tables = pd.read_html(StringIO(response.text))

        required_columns = {
            "Spieler",
            "GP",
            "G",
        }

        selected_table = None

        for table in tables:
            table.columns = [
                str(column).strip()
                for column in table.columns
            ]

            if required_columns.issubset(table.columns):
                selected_table = table
                break

        if selected_table is None:
            print(
                "DEL Spielerstatistik: "
                "Keine passende Tabelle gefunden."
            )
            return None

        parser = DELTeamParser()
        parser.feed(response.text)

        # HTML tables contain a header row before player rows.
        team_ids = parser.team_ids

        if len(team_ids) == len(selected_table) + 1:
            team_ids = team_ids[1:]

        print(
            f"DEL Spielerstatistik: "
            f"Tabellenzeilen={len(selected_table)}, "
            f"Team-Kennungen={len(team_ids)}"
        )

        if len(team_ids) != len(selected_table):
            print(
                "DEL Spielerstatistik: "
                "Team-Zuordnung nicht eindeutig. "
                "Keine Spielerwerte gespeichert."
            )
            return None

        players = []

        for index, (_, row) in enumerate(
            selected_table.iterrows()
        ):
            name = row.get("Spieler")
            team_id = team_ids[index]

            games = pd.to_numeric(
                row.get("GP"),
                errors="coerce",
            )

            goals = pd.to_numeric(
                row.get("G"),
                errors="coerce",
            )

            if pd.isna(name) or pd.isna(games) or pd.isna(goals):
                continue

            if not team_id:
                continue

            name = str(name).strip()
            games = int(games)
            goals = int(goals)

            if not name or games < 0 or goals < 0:
                continue

            player = {
                "name": name,
                "team_id": team_id,
                "games": games,
                "goals": goals,
            }

            for source, target in (
                ("A", "assists"),
                ("P", "points"),
                ("POS", "position"),
                ("Nat", "nationality"),
            ):
                if source in selected_table.columns:
                    value = row.get(source)

                    if not pd.isna(value):
                        player[target] = (
                            value.item()
                            if hasattr(value, "item")
                            else str(value)
                        )

            players.append(player)

        if not players:
            print(
                "DEL Spielerstatistik: "
                "Keine gültigen Spielerwerte gefunden."
            )
            return None

        distinct_teams = sorted(
            set(player["team_id"] for player in players)
        )

        print(
            f"DEL Spielerstatistik: "
            f"{len(players)} Spieler gespeichert"
        )

        print(
            f"DEL Spielerstatistik: "
            f"{len(distinct_teams)} Team-Kennungen"
        )

        print(
            f"DEL Team-Kennungen: {distinct_teams}"
        )

        return players

    except (
        requests.RequestException,
        ValueError,
        ImportError,
        TypeError,
    ) as exc:
        print(
            "DEL Spielerstatistik fehlgeschlagen: "
            f"{type(exc).__name__}: {str(exc)[:200]}"
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
        "del_player_stats": [],
    }

    print(
        "API_SPORTS_KEY configured: "
        f"{'yes' if KEY else 'no'} "
        "(value never displayed)"
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
                    snapshot["football"][
                        f"{league}|{date}"
                    ] = obj.get("response", [])

            # DEL fixtures
            if DEL_ID:
                obj = fetch(
                    "https://v1.hockey.api-sports.io/games",
                    params={
                        "league": DEL_ID,
                        "season": del_season(date),
                        "date": date,
                        "timezone": "Europe/Berlin",
                    },
                    headers=headers,
                )

                if obj is not None:
                    snapshot["del"][date] = obj.get(
                        "response", []
                    )

    # Official DEL player statistics
    season = del_season(days[0])
    players = fetch_del_player_stats(season)

    if players is not None:
        snapshot["del_player_stats"] = players

    elif TARGET.exists():
        try:
            previous = json.loads(
                TARGET.read_text(encoding="utf-8")
            )

            previous_players = previous.get(
                "del_player_stats", []
            )

            if isinstance(previous_players, list):
                snapshot["del_player_stats"] = previous_players
                print(
                    "DEL Spielerstatistik: "
                    "Vorherige Werte beibehalten"
                )

        except (OSError, ValueError, TypeError):
            pass

    if not any(
        snapshot[k]
        for k in ("nhl", "football", "del")
    ):
        raise SystemExit(
            "No valid fixture data retrieved; "
            "preserving previous snapshot."
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

    football_matches = sum(
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
        f"football matches={football_matches}, "
        f"DEL matches={del_matches}, "
        f"DEL players={len(snapshot['del_player_stats'])}"
    )


if __name__ == "__main__":
    main()
