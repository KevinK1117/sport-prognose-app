"""NHL matchup context. MoneyPuck team xGA and officially started goalies only.

No projected/rumored goalie is treated as confirmed. Missing provider fields stay missing.
"""
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
FIX = ROOT / 'data' / 'daily_fixtures.json'
OUT = ROOT / 'data' / 'nhl_matchups.json'
HEAD = {'User-Agent': 'SportRadar non-commercial hockey statistics'}

def number(v):
    try:
        x = float(v)
        return x if x >= 0 and x < 1e10 else None
    except (ValueError, TypeError):
        return None

def opponent_factors():
    year = datetime.now(timezone.utc).year
    if datetime.now(timezone.utc).month < 7:
        year -= 1
    url = f'https://moneypuck.com/moneypuck/teamData/seasonSummary/{year}/regular/teams.csv'
    try:
        response = requests.get(url, timeout=55, headers=HEAD)
        response.raise_for_status()
        if len(response.content) > 20_000_000:
            raise ValueError('Team file too large')
        rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
        candidates = {}
        for row in rows:
            if str(row.get('situation', '')).lower() not in ('all', 'allsituations'):
                continue
            team = str(row.get('team') or row.get('teamCode') or '').upper()
            if len(team) != 3:
                continue
            # xGoalsAgainst is the opponent's allowed expected goals (season total).
            xga = number(row.get('xGoalsAgainst') or row.get('xGoalsAgainstIncludingEmptyNet'))
            games = number(row.get('games_played') or row.get('gamesPlayed'))
            if xga is None or not games or games < 3:
                continue
            candidates[team] = xga / games
        if len(candidates) < 20:
            print('NHL team xGA: insufficient comparable teams/fields; no opponent adjustment')
            return {}
        baseline = sum(candidates.values()) / len(candidates)
        return {team: round(max(.8, min(1.2, xga / baseline)), 4) for team, xga in candidates.items()}
    except (requests.RequestException, ValueError, UnicodeError) as exc:
        print('NHL team xGA unavailable:', type(exc).__name__)
        return {}

def goals_against_fallback():
    """NHL official standings goals against per game; NOT an xGA measurement."""
    try:
        response = requests.get('https://api-web.nhle.com/v1/standings/now', timeout=25, headers=HEAD)
        response.raise_for_status()
        standings = response.json().get('standings') or []
        candidates = {}
        for row in standings:
            abbr = row.get('teamAbbrev') or {}
            team = str(abbr.get('default') if isinstance(abbr, dict) else abbr or '').upper()
            games = number(row.get('gamesPlayed'))
            ga = number(row.get('goalAgainst'))
            if len(team) == 3 and games and games >= 3 and ga is not None:
                candidates[team] = ga / games
        if len(candidates) < 20:
            print('NHL goals-against fallback: insufficient standings data')
            return {}
        baseline = sum(candidates.values()) / len(candidates)
        if baseline <= 0:
            return {}
        print('NHL opponent factors: official goals-against fallback (not xGA)')
        return {team: round(max(.8, min(1.2, ga / baseline)), 4) for team, ga in candidates.items()}
    except (requests.RequestException, ValueError, TypeError) as exc:
        print('NHL goals-against fallback unavailable:', type(exc).__name__)
        return {}

def confirmed_goalie(game):
    # The NHL boxscore is a confirmation of who actually STARTED, not a pregame prediction.
    state = str(game.get('gameState') or '').upper()
    if state not in ('LIVE', 'CRIT', 'OFF', 'FINAL'):
        return None
    game_id = game.get('id')
    if not game_id:
        return None
    try:
        response = requests.get(f'https://api-web.nhle.com/v1/gamecenter/{game_id}/boxscore', timeout=18, headers=HEAD)
        response.raise_for_status()
        box = response.json()
        result = {}
        sides = (box.get('playerByGameStats') or {})
        for side in ('homeTeam', 'awayTeam'):
            goalies = (sides.get(side) or {}).get('goalies') or []
            starters = [g for g in goalies if g.get('starter') is True]
            if len(starters) == 1:
                g = starters[0]
                name = g.get('name') or g.get('firstName') or ''
                if isinstance(name, dict):
                    name = name.get('default', '')
                surname = g.get('lastName') or ''
                if isinstance(surname, dict):
                    surname = surname.get('default', '')
                result[side] = {'id': g.get('playerId'), 'name': (str(name) + ' ' + str(surname)).strip() or str(g.get('playerId') or ''), 'confirmed': True}
        return result or None
    except (requests.RequestException, ValueError, TypeError):
        return None

def main():
    try:
        snapshot = json.loads(FIX.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        print('NHL matchup: fixture snapshot unavailable')
        return
    factors = opponent_factors()
    factor_source = "MoneyPuck team xGA"
    if not factors:
        factors = goals_against_fallback()
        factor_source = "NHL official goals against (proxy, not xGA)" if factors else "unavailable"
    payload = {'updated_at': datetime.now(timezone.utc).isoformat(), 'source': factor_source + ' / NHL official boxscore', 'opponent_factor_source': factor_source, 'games': {}}
    for item in (snapshot.get('nhl') or {}).values():
        if not isinstance(item, dict):
            continue
        for game in item.get('games') or []:
            home = str((game.get('homeTeam') or {}).get('abbrev') or '').upper()
            away = str((game.get('awayTeam') or {}).get('abbrev') or '').upper()
            if not home or not away:
                continue
            key = str(game.get('id') or f'{home}-{away}')
            record = {'home': home, 'away': away, 'game_state': game.get('gameState'), 'goalie_status': 'unconfirmed'}
            if home in factors:
                record['away_opponent_factor'] = factors[home]
            if away in factors:
                record['home_opponent_factor'] = factors[away]
            goalies = confirmed_goalie(game)
            if goalies:
                record['confirmed_starters'] = goalies
                record['goalie_status'] = 'confirmed_after_start'
            payload['games'][key] = record
    if not payload['games']:
        print('NHL matchup: no games; old file retained')
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    temp = OUT.with_suffix('.tmp')
    temp.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    temp.replace(OUT)
    print('NHL matchup records:', len(payload['games']), 'opponent teams:', len(factors))

if __name__ == '__main__':
    main()
