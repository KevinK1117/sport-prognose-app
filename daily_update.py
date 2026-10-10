
"""SportRadar daily data update."""

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

KEY = os.environ.get("API_SPORTS_KEY", "").strip()
DEL_ID = os.environ.get("DEL_LEAGUE_ID", "").strip()

LEAGUES = {
    "Bundesliga": 78,
    "2. Bundesliga": 79,
    "La Liga": 140,
    "Serie A": 135,
    "Premier League": 39,
    "Ligue 1": 61,
    "MLS": 253,
}

DEL_BASE = "https://www.penny-del.org"


def fetch(url, params=None, headers=None):
    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=25,
        )

        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, dict) and payload.get("errors"):
            print(
                "API-Fehler:",
                str(payload["errors"])[:300],
            )
            return None

        return payload

    except (requests.RequestException, ValueError) as exc:
        print(
            "API-Abfrage fehlgeschlagen:",
            url,
            type(exc).__name__,
        )
        return None


def get_del_page(url):
    response = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 SportRadar/1.0"
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def del_season(date):
    year = int(date[:4])
    month = int(date[5:7])
    return year if month >= 7 else year - 1


def season_label(season):
    return f"{season}-{str(season + 1)[-2:]}"


def clean(value):
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if hasattr(value, "item"):
        value = value.item()

    if isinstance(value, str):
        return value.strip()

    return value


def team_id_from_image(src):
    """Works with team_3.svg and csm_team_5_hash.png."""
    match = re.search(
        r"team_(\d+)(?=[_.])",
        src or "",
        flags=re.IGNORECASE,
    )

    if match:
        return "team_" + match.group(1)

    return None


class DELTableParser(HTMLParser):
    """Read team logos and visible team names from HTML rows."""

    def __init__(self):
        super().__init__(convert_charrefs=True)

        self.table_depth = 0
        self.in_row = False
        self.in_heading = False
        self.row = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "table":
            self.table_depth += 1
            return

        if self.table_depth == 0:
            return

        if tag == "tr":
            self.in_row = True
            self.row = {
                "team_id": None,
                "name": "",
            }

        if not self.in_row:
            return

        if tag == "img":
            team_id = team_id_from_image(
                attrs.get("src", "")
            )

            if team_id and not self.row["team_id"]:
                self.row["team_id"] = team_id

        if tag in ("h5", "h6"):
            self.in_heading = True

    def handle_data(self, data):
        if self.in_row and self.in_heading:
            self.row["name"] += data

    def handle_endtag(self, tag):
        if tag in ("h5", "h6"):
            self.in_heading = False

        if tag == "tr" and self.in_row:
            self.row["name"] = (
                self.row["name"].strip()
            )
            self.rows.append(self.row)
            self.in_row = False
            self.row = None
            self.in_heading = False

        if tag == "table" and self.table_depth:
            self.table_depth -= 1


def fetch_del_team_names(season):
    """Match official DEL team names with logo identifiers."""

    label = season_label(season)

    url = (
        f"{DEL_BASE}/statistik/"
        f"saison-{label}/hauptrunde/"
        "teamstats/team-play"
    )

    try:
        page = get_del_page(url)

        parser = DELTableParser()
        parser.feed(page)

        mapping = {}
        conflicts = set()

        for row in parser.rows:
            team_id = row["team_id"]
            name = row["name"]

            if not team_id or not name:
                continue

            if (
                team_id in mapping
                and mapping[team_id] != name
            ):
                conflicts.add(team_id)
                continue

            mapping[team_id] = name

        for team_id in conflicts:
            mapping.pop(team_id, None)

        print(
            "DEL Teamnamen:",
            len(mapping),
            "eindeutige Zuordnungen",
        )

        for team_id in sorted(mapping):
            print(
                "DEL TEAM:",
                team_id,
                "=>",
                mapping[team_id],
            )

        if conflicts:
            print(
                "DEL Team-Konflikte:",
                sorted(conflicts),
            )

        return mapping

    except (requests.RequestException, ValueError) as exc:
        print(
            "DEL Teamnamen nicht verfügbar:",
            type(exc).__name__,
        )
        return {}


def fetch_del_player_stats(season, team_names):
    """Fetch official DEL player stats and add team names."""

    label = season_label(season)

    url = (
        f"{DEL_BASE}/statistik/"
        f"saison-{label}/hauptrunde/"
        "playerstats/basis"
    )

    try:
        page = get_del_page(url)

        tables = pd.read_html(
            StringIO(page)
        )

        selected = None

        for table in tables:
            table.columns = [
                str(column).strip()
                for column in table.columns
            ]

            if {
                "Spieler",
                "GP",
                "G",
            }.issubset(table.columns):
                selected = table
                break

        if selected is None:
            print(
                "DEL: Keine passende Spielertabelle."
            )
            return None

        parser = DELTableParser()
        parser.feed(page)

        rows = parser.rows

        # The HTML header may be included as one extra row.
        if len(rows) == len(selected) + 1:
            rows = rows[1:]

        print(
            "DEL Tabellenzeilen:",
            len(selected),
            "HTML-Zeilen:",
            len(rows),
        )

        if len(rows) != len(selected):
            print(
                "DEL: Tabellenzeilen stimmen nicht "
                "überein. Keine unsichere Zuordnung."
            )
            return None

        players = []
        missing_logos = 0
        missing_names = set()

        for index, (_, row) in enumerate(
            selected.iterrows()
        ):
            name = clean(
                row.get("Spieler")
            )

            team_id = rows[index]["team_id"]

            games = pd.to_numeric(
                row.get("GP"),
                errors="coerce",
            )

            goals = pd.to_numeric(
                row.get("G"),
                errors="coerce",
            )

            if not isinstance(name, str) or not name:
                continue

            if not team_id:
                missing_logos += 1
                continue

            if pd.isna(games) or pd.isna(goals):
                continue

            games = int(games)
            goals = int(goals)

            if games < 0 or goals < 0:
                continue

            team_name = team_names.get(team_id)

            if not team_name:
                missing_names.add(team_id)

            player = {
                "name": name,
                "team_id": team_id,
                "games": games,
                "goals": goals,
            }

            # Only write verified team names.
            if team_name:
                player["team"] = team_name

            for source, target in (
                ("A", "assists"),
                ("P", "points"),
                ("POS", "position"),
                ("Nat", "nationality"),
            ):
                if source not in selected.columns:
                    continue

                value = clean(row.get(source))

                if value is not None:
                    player[target] = value

            players.append(player)

        print(
            "DEL Spieler gespeichert:",
            len(players),
        )

        print(
            "DEL Spieler ohne Teamlogo:",
            missing_logos,
        )

        print(
            "DEL Team-Kennungen ohne Namen:",
            sorted(missing_names),
        )

        named = sum(
            bool(p.get("team"))
            for p in players
        )

        print(
            "DEL Spieler mit Vereinsnamen:",
            named,
        )

        if not players:
            return None

        return players

    except (
        requests.RequestException,
        ValueError,
        TypeError,
        ImportError,
    ) as exc:
        print(
            "DEL Spielerstatistik fehlgeschlagen:",
            type(exc).__name__,
            str(exc)[:200],
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
        "del_team_names": {},
    }

    print(
        "API_SPORTS_KEY configured:",
        "yes" if KEY else "no",
    )

    for date in days:
        # NHL
        nhl = fetch(
            f"https://api-web.nhle.com/v1/score/{date}"
        )

        if nhl is not None:
            snapshot["nhl"][date] = nhl

        if not KEY:
            continue

        headers = {
            "x-apisports-key": KEY
        }

        # Football
        for league, ident in LEAGUES.items():
            year = (
                int(date[:4])
                if (
                    league == "MLS"
                    or int(date[5:7]) >= 7
                )
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

        # DEL
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

    # DEL team names and player statistics
    season = del_season(days[0])

    team_names = fetch_del_team_names(
        season
    )

    players = fetch_del_player_stats(
        season,
        team_names,
    )

    previous = {}

    if TARGET.exists():
        try:
            previous = json.loads(
                TARGET.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            previous = {}

    if players is not None:
        snapshot["del_player_stats"] = players

    else:
        previous_players = previous.get(
            "del_player_stats", []
        )

        if isinstance(previous_players, list):
            snapshot["del_player_stats"] = (
                previous_players
            )

            print(
                "DEL: Vorherige Spielerwerte "
                "beibehalten."
            )

    if team_names:
        snapshot["del_team_names"] = team_names

    else:
        previous_names = previous.get(
            "del_team_names", {}
        )

        if isinstance(previous_names, dict):
            snapshot["del_team_names"] = (
                previous_names
            )

    # Preserve the old snapshot if all fixture calls fail.
    if not any(
        snapshot[key]
        for key in ("nhl", "football", "del")
    ):
        raise SystemExit(
            "Keine gültigen Spieldaten geladen."
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

    football_count = sum(
        len(items)
        for items in snapshot["football"].values()
    )

    del_count = sum(
        len(items)
        for items in snapshot["del"].values()
    )

    print(
        "Update erfolgreich:",
        f"NHL dates={len(snapshot['nhl'])},",
        f"football matches={football_count},",
        f"DEL matches={del_count},",
        "DEL players="
        f"{len(snapshot['del_player_stats'])},",
        "DEL teams="
        f"{len(snapshot['del_team_names'])}",
    )


if __name__ == "__main__":
    main()


