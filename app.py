
"""SportRadar: football, NHL and DEL goalscorer estimates."""

import html
import json
import math
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st


st.set_page_config(
    page_title="SportRadar | Torprognosen",
    page_icon="🎯",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1050px;
        padding-top: 1.2rem;
    }
    h1, h2, h3 {
        color: #30333e;
    }
    .player {
        background: #fafafa;
        border: 1px solid #d8d8dc;
        border-radius: 18px;
        padding: 15px;
        margin: 10px 0;
    }
    .player-head {
        font-weight: 700;
        font-size: 1.08rem;
    }
    .muted {
        color: #777b85;
        font-size: .88rem;
    }
    .pair {
        display: flex;
        gap: 10px;
        margin-top: 12px;
    }
    .prob {
        flex: 1;
        background: #eef0f5;
        border-radius: 12px;
        padding: 12px 9px;
        text-align: center;
    }
    .prob strong {
        display: block;
        font-size: 1.4rem;
        color: #30333e;
    }
    .prob small {
        color: #646a77;
    }
    .pill {
        display: inline-block;
        background: #ededee;
        border-radius: 10px;
        padding: 5px 9px;
        margin: 9px 5px 0 0;
        font-size: .83rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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


def secret(name):
    try:
        value = st.secrets.get(name, "")
        if value:
            return str(value)
    except Exception:
        pass
    return os.environ.get(name, "")


@st.cache_data(ttl=1800, show_spinner=False)
def api(path, params=None, provider="football", key=""):
    if not key:
        return None

    if provider == "football":
        base = "https://v3.football.api-sports.io"
    else:
        base = "https://v1.hockey.api-sports.io"

    try:
        response = requests.get(
            f"{base}/{path}",
            params=params or {},
            headers={"x-apisports-key": key},
            timeout=20,
        )
        response.raise_for_status()

        payload = response.json()

        if not isinstance(payload, dict):
            return None

        if payload.get("errors"):
            return None

        return payload.get("response", [])

    except (requests.RequestException, ValueError):
        return None


@st.cache_data(ttl=1800, show_spinner=False)
def nhl(path):
    try:
        response = requests.get(
            "https://api-web.nhle.com/v1/" + path,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    except (requests.RequestException, ValueError):
        return None


@st.cache_data(ttl=60, show_spinner=False)
def daily_snapshot():
    path = (
        Path(__file__).resolve().parent
        / "data"
        / "daily_fixtures.json"
    )

    try:
        result = json.loads(
            path.read_text(encoding="utf-8")
        )
        return result if isinstance(result, dict) else {}

    except (OSError, ValueError):
        return {}


def fixtures_for(sport, day, league=None):
    snapshot = daily_snapshot()
    date = day.isoformat()

    if date not in snapshot.get("dates", []):
        return None

    if sport == "football":
        key = f"{league}|{date}"
        return snapshot.get("football", {}).get(key)

    return snapshot.get(sport, {}).get(date)


def season(day, league):
    if league == "MLS" or day.month >= 7:
        return day.year
    return day.year - 1


def probability(
    goals,
    games,
    minutes=None,
    period=1.0,
    prior=0.12,
    prior_games=8,
):
    """Smoothed Poisson estimate of scoring at least once."""

    if games is None or games <= 0:
        return None

    rate = (
        max(0, goals) + prior * prior_games
    ) / (games + prior_games)

    if minutes is not None and minutes > 0:
        rate *= min(
            1.35,
            max(0.45, minutes / 75),
        )

    return 100 * (-math.expm1(-rate * period))


def pct(value):
    if value is None:
        return "–"
    return f"{value:.1f} %".replace(".", ",")


def show_player(player, period_label):
    name = html.escape(str(player["name"]))
    team = html.escape(str(player["team"]))

    pills = [
        f'{player["goals"]} Tore',
        f'{player["games"]} Spiele',
    ]

    if player.get("shots") is not None:
        pills.append(f'{player["shots"]} Schüsse')

    if player.get("minutes") is not None:
        pills.append(
            f'{player["minutes"]:.0f} Min Ø'
        )

    chips = "".join(
        '<span class="pill">'
        + html.escape(str(item))
        + "</span>"
        for item in pills
    )

    st.markdown(
        f"""
        <div class="player">
          <div class="player-head">{name}</div>
          <div class="muted">{team}</div>
          <div class="pair">
            <div class="prob">
              <small>{html.escape(period_label)}</small>
              <strong>{pct(player.get("half"))}</strong>
            </div>
            <div class="prob">
              <small>Gesamtspiel</small>
              <strong>{pct(player.get("p"))}</strong>
            </div>
          </div>
          <div>{chips}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_players(players, period_label):
    if not players:
        st.info(
            "Keine verlässlichen Spielerstatistiken verfügbar."
        )
        return

    tab1, tab2 = st.tabs(
        ["🎯 Spielerprognosen", "📊 Tabelle"]
    )

    with tab1:
        for player in players:
            show_player(player, period_label)

    with tab2:
        table = []

        for player in players:
            minutes = player.get("minutes")

            table.append({
                "Spieler": player["name"],
                "Team": player["team"],
                period_label: pct(player.get("half")),
                "Gesamtspiel": pct(player.get("p")),
                "Tore": player["goals"],
                "Spiele": player["games"],
                "Schüsse": player.get("shots"),
                "Min Ø": (
                    round(minutes, 1)
                    if minutes is not None
                    else None
                ),
            })

        st.dataframe(
            pd.DataFrame(table),
            hide_index=True,
            use_container_width=True,
        )


@st.cache_data(ttl=3600, show_spinner=False)
def football_players(league_id, year, team_id, key):
    if not team_id:
        return []

    result = {}

    for page in range(1, 16):
        rows = api(
            "players",
            {
                "league": league_id,
                "season": year,
                "team": team_id,
                "page": page,
            },
            key=key,
        )

        if rows is None:
            return (
                None
                if page == 1
                else list(result.values())
            )

        for entry in rows:
            player = entry.get("player") or {}

            for stats in entry.get("statistics") or []:
                team = stats.get("team") or {}

                if team.get("id") != team_id:
                    continue

                games = stats.get("games") or {}
                goals = stats.get("goals") or {}
                shots = stats.get("shots") or {}

                apps = games.get("appearences") or 0

                if not apps:
                    continue

                total_goals = goals.get("total") or 0
                total_minutes = games.get("minutes")

                if (
                    isinstance(total_minutes, (int, float))
                    and total_minutes > 0
                ):
                    avg_minutes = total_minutes / apps
                else:
                    avg_minutes = None

                ident = (
                    player.get("id")
                    or player.get("name")
                )

                result[ident] = {
                    "name": (
                        player.get("name")
                        or "Unbekannt"
                    ),
                    "team": team.get("name") or "",
                    "goals": total_goals,
                    "games": apps,
                    "shots": shots.get("total"),
                    "minutes": avg_minutes,
                    "p": probability(
                        total_goals,
                        apps,
                        avg_minutes,
                    ),
                    "half": probability(
                        total_goals,
                        apps,
                        avg_minutes,
                        period=0.45,
                    ),
                }

        if len(rows) < 20:
            break

    return list(result.values())


def football_view(day, league):
    year = season(day, league)

    fixtures = fixtures_for(
        "football",
        day,
        league,
    )

    if fixtures is None:
        fixtures = api(
            "fixtures",
            {
                "league": LEAGUES[league],
                "season": year,
                "date": day.isoformat(),
                "timezone": "Europe/Berlin",
            },
            key=secret("API_SPORTS_KEY"),
        )

    if fixtures is None:
        st.warning(
            "Fußball-Spielplan nicht verfügbar. "
            "API-Zugang prüfen."
        )
        return

    if not fixtures:
        st.info("Keine Begegnungen an diesem Tag.")
        return

    if league == "MLS":
        st.caption(f"Saison {year}")
    else:
        st.caption(
            f"Saison {year}/{str(year + 1)[-2:]}"
        )

    fixtures = sorted(
        fixtures,
        key=lambda match: (
            (match.get("fixture") or {})
            .get("timestamp") or 0
        ),
    )

    for match in fixtures:
        fixture = match.get("fixture") or {}
        teams = match.get("teams") or {}

        home = teams.get("home") or {}
        away = teams.get("away") or {}

        try:
            time = datetime.fromtimestamp(
                fixture["timestamp"],
                TZ,
            ).strftime("%H:%M")

        except (
            KeyError,
            TypeError,
            ValueError,
            OverflowError,
        ):
            time = "–"

        title = (
            f'⚽ {time} Uhr · '
            f'{home.get("name", "?")} – '
            f'{away.get("name", "?")}'
        )

        with st.expander(title, expanded=True):
            st.caption(
                "Geschätzte Wahrscheinlichkeit für "
                "mindestens ein Tor. "
                "1. Halbzeit: angenommene 45 % "
                "der Torintensität."
            )

            key = secret("API_SPORTS_KEY")

            if not key:
                st.info(
                    "API_SPORTS_KEY in Streamlit "
                    "Secrets eintragen."
                )
                continue

            with st.spinner(
                "Spielerstatistiken laden …"
            ):
                home_players = football_players(
                    LEAGUES[league],
                    year,
                    home.get("id"),
                    key,
                )

                away_players = football_players(
                    LEAGUES[league],
                    year,
                    away.get("id"),
                    key,
                )

            if (
                home_players is None
                or away_players is None
            ):
                st.warning(
                    "Spielerstatistiken nicht "
                    "vollständig verfügbar."
                )
                continue

            players = sorted(
                home_players + away_players,
                key=lambda p: p.get("p") or 0,
                reverse=True,
            )

            show_players(
                players[:25],
                "1. Halbzeit",
            )


@st.cache_data(ttl=3600, show_spinner=False)
def nhl_skaters(abbrev):
    payload = nhl(f"club-stats/{abbrev}/now")

    if not isinstance(payload, dict):
        return None

    result = []

    for item in payload.get("skaters") or []:
        games = item.get("gamesPlayed") or 0

        if not games:
            continue

        goals = item.get("goals") or 0

        first = item.get("firstName") or {}
        last = item.get("lastName") or {}

        if isinstance(first, dict):
            first = first.get("default", "")

        if isinstance(last, dict):
            last = last.get("default", "")

        result.append({
            "name": (
                f"{first} {last}".strip()
                or "Unbekannt"
            ),
            "team": abbrev,
            "goals": goals,
            "games": games,
            "shots": item.get("shots"),
            "minutes": None,
            "p": probability(
                goals,
                games,
                prior=0.18,
            ),
            "half": probability(
                goals,
                games,
                period=1 / 3,
                prior=0.18,
            ),
        })

    return result


def nhl_view(day):
    schedule = fixtures_for("nhl", day)

    if schedule is None:
        schedule = nhl(
            "score/" + day.isoformat()
        )

    if not isinstance(schedule, dict):
        st.warning(
            "NHL-Spielplan nicht verfügbar."
        )
        return

    games = schedule.get("games") or []

    if not games:
        st.info(
            "Keine NHL-Spiele an diesem Tag."
        )
        return

    for game in games:
        home = game.get("homeTeam") or {}
        away = game.get("awayTeam") or {}

        try:
            start = game.get(
                "startTimeUTC", ""
            ).replace("Z", "+00:00")

            time = datetime.fromisoformat(
                start
            ).astimezone(TZ).strftime("%H:%M")

        except (ValueError, TypeError):
            time = "–"

        title = (
            f'🏒 {time} Uhr · '
            f'{away.get("abbrev", "?")} @ '
            f'{home.get("abbrev", "?")}'
        )

        with st.expander(title, expanded=True):
            st.caption(
                "1. Drittel: angenommene "
                "gleichmäßige Torintensität "
                "über drei Drittel."
            )

            players = []

            for team in (home, away):
                abbrev = team.get("abbrev")

                if abbrev:
                    rows = nhl_skaters(abbrev)

                    if rows:
                        players.extend(rows)

            players.sort(
                key=lambda p: p.get("p") or 0,
                reverse=True,
            )

            show_players(
                players[:25],
                "1. Drittel",
            )


def safe_nonnegative_int(value):
    try:
        number = int(value)

        if number < 0:
            return None

        return number

    except (TypeError, ValueError, OverflowError):
        return None


def del_player_estimates():
    """Build estimates from saved official DEL stats."""

    snapshot = daily_snapshot()

    raw_players = snapshot.get(
        "del_player_stats", []
    )

    if not isinstance(raw_players, list):
        return []

    players = []

    for item in raw_players:
        if not isinstance(item, dict):
            continue

        name = str(
            item.get("name") or ""
        ).strip()

        team_id = str(
            item.get("team_id") or ""
        ).strip()

        games = safe_nonnegative_int(
            item.get("games")
        )

        goals = safe_nonnegative_int(
            item.get("goals")
        )

        if not name or not team_id:
            continue

        if games is None or games == 0:
            continue

        if goals is None or goals > games * 20:
            continue

        # This is a statistical estimate, not a betting odd.
        full = probability(
            goals,
            games,
            prior=0.18,
            prior_games=8,
        )

        first = probability(
            goals,
            games,
            period=1 / 3,
            prior=0.18,
            prior_games=8,
        )

        players.append({
            "name": name,
            "team": team_id,
            "team_id": team_id,
            "games": games,
            "goals": goals,
            "shots": None,
            "minutes": None,
            "p": full,
            "half": first,
        })

    return sorted(
        players,
        key=lambda p: p.get("p") or 0,
        reverse=True,
    )


def del_view(day):
    snapshot = daily_snapshot()

    rows = fixtures_for("del", day)

    if rows is None:
        league_id = secret("DEL_LEAGUE_ID")

        if not league_id:
            league_id = "19"

        rows = api(
            "games",
            {
                "league": league_id,
                "season": season(day, "DEL"),
                "date": day.isoformat(),
                "timezone": "Europe/Berlin",
            },
            provider="hockey",
            key=secret("API_SPORTS_KEY"),
        )

    if rows is None:
        st.warning(
            "DEL-Spielplan derzeit nicht verfügbar."
        )
        return

    players = del_player_estimates()

    if not rows:
        st.info(
            "Keine DEL-Spiele an diesem Tag."
        )

    else:
        st.subheader("🏒 DEL-Spielplan")

        for match in rows:
            teams = match.get("teams") or {}

            home = teams.get("home") or {}
            away = teams.get("away") or {}

            home_name = home.get(
                "name", "Heim"
            )

            away_name = away.get(
                "name", "Gast"
            )

            title = (
                f"🏒 {home_name} – {away_name}"
            )

            with st.expander(
                title,
                expanded=True,
            ):
                st.caption(
                    "Spiel aus dem gespeicherten "
                    "DEL-Spielplan."
                )

                st.info(
                    "Die Zuordnung der Spieler-"
                    "Kennungen zu diesen beiden "
                    "Mannschaften wird noch geprüft. "
                    "Deshalb werden hier noch keine "
                    "Spieler automatisch zugeordnet."
                )

    st.divider()

    st.subheader(
        "🎯 DEL-Spielerprognosen"
    )

    if not players:
        st.warning(
            "Noch keine gültigen DEL-"
            "Spielerstatistiken gespeichert. "
            "Bitte das GitHub-Tagesupdate prüfen."
        )
        return

    team_ids = sorted(
        {p["team_id"] for p in players},
        key=lambda value: (
            int(value.split("_")[-1])
            if value.split("_")[-1].isdigit()
            else 9999
        ),
    )

    st.success(
        f"{len(players)} DEL-Spieler mit "
        f"Statistiken verfügbar · "
        f"{len(team_ids)} Team-Kennungen"
    )

    st.caption(
        "Die Prognosen basieren auf "
        "bisherigen Saisontoren und Spielen. "
        "Für das 1. Drittel wird ein Drittel "
        "der geschätzten Torintensität "
        "angenommen. Gegner, Aufstellung "
        "und Eiszeit werden hier noch "
        "nicht berücksichtigt."
    )

    st.warning(
        "Die Mannschaftsnamen sind noch "
        "nicht verifiziert. Die Prognosen "
        "werden deshalb nach Team-Kennung "
        "angezeigt und noch nicht einem "
        "konkreten Spiel zugewiesen."
    )

    selected_team = st.selectbox(
        "DEL-Team-Kennung",
        ["Alle Spieler"] + team_ids,
    )

    if selected_team == "Alle Spieler":
        filtered = players
    else:
        filtered = [
            p for p in players
            if p["team_id"] == selected_team
        ]

    st.caption(
        f"{len(filtered)} Spieler in "
        "der Auswahl"
    )

    show_players(
        filtered[:30],
        "1. Drittel",
    )

    with st.expander(
        "🔎 Team-Kennungen prüfen"
    ):
        st.write(
            "Diese Kennungen stammen aus "
            "den Teamlogos der offiziellen "
            "DEL-Spielerstatistik."
        )

        counts = []

        for team_id in team_ids:
            count = sum(
                p["team_id"] == team_id
                for p in players
            )

            counts.append({
                "Team-Kennung": team_id,
                "Spieler": count,
            })

        st.dataframe(
            pd.DataFrame(counts),
            hide_index=True,
            use_container_width=True,
        )


st.title(
    "🎯 SportRadar – "
    "Torschützen heute & morgen"
)

st.caption(
    "Deutsche Zeit · Saison automatisch · "
    "Poisson-Modell mit Stichproben-Glättung"
)

sport = st.radio(
    "Sportart",
    ["🏒 Eishockey", "⚽ Fußball"],
    horizontal=True,
)

if sport.startswith("🏒"):
    leagues = ["NHL", "DEL"]
else:
    leagues = list(LEAGUES)

league = st.selectbox(
    "Liga",
    leagues,
)

day_choice = st.radio(
    "Spieltag",
    ["Heute", "Morgen"],
    horizontal=True,
)

day = (
    datetime.now(TZ).date()
    + timedelta(
        days=int(day_choice == "Morgen")
    )
)

st.caption(
    day.strftime("%d.%m.%Y")
)

snapshot = daily_snapshot()

if snapshot.get("updated_at"):
    try:
        updated = datetime.fromisoformat(
            snapshot["updated_at"]
        ).astimezone(TZ)

        st.caption(
            "🕗 Letzte gespeicherte "
            "Aktualisierung: "
            + updated.strftime(
                "%d.%m.%Y %H:%M"
            )
            + " Uhr"
        )

    except ValueError:
        st.caption(
            "🕗 Gespeicherter Datenstand vorhanden"
        )

else:
    st.caption(
        "🕗 Noch kein täglicher Snapshot "
        "vorhanden"
    )

if st.button(
    "🔄 Daten neu laden"
):
    st.cache_data.clear()
    st.rerun()

if sport.startswith("🏒"):
    if league == "NHL":
        nhl_view(day)
    else:
        del_view(day)

else:
    football_view(
        day,
        league,
    )

st.divider()

st.caption(
    "Modellschätzungen, keine Garantien "
    "oder Wettquoten. Aufstellung, "
    "Verletzungen, Gegnerstärke und "
    "kleine Stichproben sind nicht "
    "vollständig berücksichtigt. "
    "Der Button lädt Daten neu, "
    "startet aber keinen GitHub-Workflow."
)
