"""Update verified NHL player game logs without overwriting valid data on failure."""
import concurrent.futures
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'data' / 'daily_player_stats.json'
FIX = ROOT / 'data' / 'daily_fixtures.json'
BASE = 'https://api-web.nhle.com/v1/'


def get(path):
    for attempt in range(3):
        try:
            response = requests.get(BASE + path, timeout=20, headers={'User-Agent': 'SportRadar/1.0 (NHL public statistics)'})
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            if attempt == 2:
                print(f'WARN API {path}: {type(exc).__name__}: {exc}')
            else:
                time.sleep(0.5 * (attempt + 1))
    return None


def toi(value):
    if isinstance(value, (int, float)):
        return float(value)
    try:
        parts = str(value).split(':')
        return int(parts[0]) + int(parts[1]) / 60 if len(parts) == 2 else None
    except (ValueError, TypeError):
        return None


def season_codes(today):
    start = today.year if today.month >= 7 else today.year - 1
    return [f'{start}{start + 1}', f'{start - 1}{start}']


def scheduled_clubs(fixture):
    clubs = set()
    nhl = fixture.get('nhl') or {}
    payloads = nhl.values() if isinstance(nhl, dict) else (nhl if isinstance(nhl, list) else [])
    for payload in payloads:
        if isinstance(payload, dict):
            games = payload.get('games', [])
        elif isinstance(payload, list):
            games = payload
        else:
            continue
        for game in games:
            if not isinstance(game, dict):
                continue
            for side in ('homeTeam', 'awayTeam'):
                team = game.get(side) or {}
                if isinstance(team, dict):
                    abbreviation = team.get('abbrev')
                    if isinstance(abbreviation, str) and abbreviation:
                        clubs.add(abbreviation)
    return clubs


def name_part(value):
    if isinstance(value, dict):
        return value.get('default') or next(iter(value.values()), '')
    return str(value or '')


def main():
    now = datetime.now(timezone.utc)
    if not FIX.exists():
        print('WARN: daily_fixtures.json fehlt; vorhandene Spielerstatistiken bleiben erhalten.')
        return
    try:
        fixture = json.loads(FIX.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        print(f'WARN: Fixtures nicht lesbar: {exc}')
        return

    clubs = scheduled_clubs(fixture)
    print('NHL teams scheduled:', len(clubs))
    if not clubs:
        print('WARN: Keine NHL-Teams im Spielplan; vorhandene Daten bleiben erhalten.')
        return

    players = {}
    for club in sorted(clubs):
        stats = get(f'club-stats/{club}/now')
        if not isinstance(stats, dict):
            continue
        for row in stats.get('skaters', []):
            pid = row.get('playerId') or row.get('id')
            if pid:
                name = (name_part(row.get('firstName')) + ' ' + name_part(row.get('lastName'))).strip()
                players[str(pid)] = (pid, club, name)
    print('NHL skaters found:', len(players))
    if not players:
        print('WARN: Keine NHL-Kaderdaten verfügbar; vorhandene Daten bleiben erhalten.')
        return

    codes = season_codes(now.date())
    today = now.date().isoformat()

    def collect(entry):
        pid, club, name = entry
        games = []
        for code in codes:
            log = get(f'player/{pid}/game-log/{code}/2')
            if not isinstance(log, dict):
                continue
            for game in log.get('gameLog', []):
                date = str(game.get('gameDate', ''))[:10]
                if not date or date >= today:
                    continue
                try:
                    goals = int(game.get('goals') or 0)
                    shots = int(game.get('shots') or 0)
                except (ValueError, TypeError):
                    continue
                record = {'date': date, 'goals': goals, 'shots': shots,
                          'toi': toi(game.get('toi') or game.get('timeOnIce'))}
                # NHL game-log fields vary by season. Only store PP goals when
                # the official response explicitly supplies the value.
                pp_goals = game.get('powerPlayGoals')
                if pp_goals is not None:
                    try: record['pp_goals'] = max(0, int(pp_goals))
                    except (TypeError, ValueError): pass
                games.append(record)
            if games:
                break
        if not games:
            return None
        games.sort(key=lambda item: item['date'], reverse=True)

        def summary(sample):
            minutes = [g['toi'] for g in sample if g['toi'] is not None]
            return {'games': len(sample), 'goals': sum(g['goals'] for g in sample),
                    'shots': sum(g['shots'] for g in sample),
                    'toi_game': round(sum(minutes) / len(minutes), 2) if minutes else None,
                    'shots_on_target_game': round(sum(g['shots'] for g in sample) / len(sample), 2),
                    'pp_goals': sum(g['pp_goals'] for g in sample if 'pp_goals' in g) if any('pp_goals' in g for g in sample) else None,
                    'pp_goals_games_reported': sum('pp_goals' in g for g in sample)}

        return str(pid), {'name': name, 'team': club, 'sport': 'NHL',
                          'source': 'NHL API / player game-log', 'updated_at': now.isoformat(),
                          'season': summary(games), 'last20': summary(games[:20]),
                          'last5': summary(games[:5]), 'games': games[:20],
                          'ixg60': None, 'pp_toi_game': None, 'pp1': None}

    result = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for item in pool.map(collect, players.values()):
            if item:
                result[item[0]] = item[1]
    print('NHL player records fetched:', len(result))
    if not result:
        print('WARN: Keine NHL-Spielerlogs abrufbar; bisherige Daten bleiben erhalten.')
        return

    # Preserve previous records not included in today's fixtures and avoid data loss.
    if OUT.exists():
        try:
            previous = json.loads(OUT.read_text(encoding='utf-8'))
            previous_nhl = previous.get('nhl', {})
            if isinstance(previous_nhl, dict):
                result = {**previous_nhl, **result}
        except (OSError, ValueError) as exc:
            print('WARN: Bisherige Spielerdatei nicht lesbar:', exc)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUT.with_suffix('.json.tmp')
    temporary.write_text(json.dumps({'updated_at': now.isoformat(), 'nhl': result,
                                     'source': 'NHL API'}, ensure_ascii=False,
                                    separators=(',', ':')), encoding='utf-8')
    temporary.replace(OUT)
    print('NHL player records saved:', len(result), 'file:', OUT)


if __name__ == '__main__':
    main()
    try:
        from nhl_matchup_update import main as update_nhl_matchups
        update_nhl_matchups()
    except (ImportError, OSError, ValueError) as exc:
        print('WARN NHL matchup update:', type(exc).__name__)
