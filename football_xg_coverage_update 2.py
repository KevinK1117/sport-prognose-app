"""SportRadar: incremental verified TEAM xG/xGA coverage and per-league diagnostics.

Never substitute shots/goals for xG. Existing Understat data and penalties are kept.
"""
import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'data' / 'football_context.json'
CACHE = ROOT / 'data' / 'football_fixture_xg_cache.json'
LEAGUES = {'Bundesliga':78, '2. Bundesliga':79, 'La Liga':140,
           'Serie A':135, 'Premier League':39, 'Ligue 1':61,
           'MLS':253, 'Champions League':2, 'Europa League':3,
           'Saudi Pro League':307}
API = 'https://v3.football.api-sports.io'
KEY = os.getenv('API_SPORTS_KEY', '').strip()
MAX_REQUESTS = max(0, int(os.getenv('FOOTBALL_XG_MAX_REQUESTS', '45')))
LOOKBACK_DAYS = max(35, int(os.getenv('FOOTBALL_XG_LOOKBACK_DAYS', '120')))
RETRY_MISSING_DAYS = max(1, int(os.getenv('FOOTBALL_XG_RETRY_DAYS', '14')))
MIN_GAMES = max(1, int(os.getenv('FOOTBALL_XG_MIN_GAMES', '3')))


def norm(value):
    s = ''.join(c for c in unicodedata.normalize('NFKD', str(value or '').casefold())
                if not unicodedata.combining(c))
    return re.sub('[^a-z0-9]', '', s)


def load(path):
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def api_request(session, endpoint, params):
    try:
        response = session.get(API + endpoint, params=params, timeout=30)
        if response.status_code in (401, 403, 429):
            print('API blocked:', response.status_code, endpoint)
            return None
        response.raise_for_status()
        payload = response.json()
        if payload.get('errors'):
            print('API error:', endpoint, str(payload['errors'])[:220])
            return None
        return payload.get('response') or []
    except (requests.RequestException, ValueError, TypeError) as exc:
        print('API request failed:', endpoint, type(exc).__name__)
        return None


def get_xg(stats):
    for stat in stats or []:
        name = re.sub(r'[^a-z]', '', str(stat.get('type', '')).lower())
        if name not in ('expectedgoals', 'xg'):
            continue
        try:
            value = float(stat.get('value'))
            if 0 <= value <= 15:
                return value
        except (TypeError, ValueError):
            pass
    return None


def main():
    if not KEY:
        print('API_SPORTS_KEY missing; existing context retained')
        return
    now = datetime.now(timezone.utc)
    today = now.date()
    session = requests.Session()
    session.headers.update({'x-apisports-key': KEY})
    cache = load(CACHE)
    matches = cache.get('matches') or {}
    if not isinstance(matches, dict):
        matches = {}
    diagnostics = defaultdict(Counter)
    pending = {name: [] for name in LEAGUES}

    for league, league_id in LEAGUES.items():
        season = today.year if league == 'MLS' or today.month >= 7 else today.year - 1
        # Current season, with bounded lookback; the cache persists older fixtures.
        rows = api_request(session, '/fixtures', {
            'league': league_id, 'season': season,
            'from': (today - timedelta(days=LOOKBACK_DAYS)).isoformat(),
            'to': (today - timedelta(days=1)).isoformat()})
        if rows is None:
            diagnostics[league]['fixture_api_failed'] += 1
            continue
        for item in rows:
            fixture = item.get('fixture') or {}
            if (fixture.get('status') or {}).get('short') not in ('FT', 'AET', 'PEN'):
                continue
            fid = fixture.get('id')
            if not fid:
                continue
            fid = str(fid)
            diagnostics[league]['finished_found'] += 1
            previous = matches.get(fid) or {}
            if isinstance(previous.get('home_xg'), (int, float)) and isinstance(previous.get('away_xg'), (int, float)):
                diagnostics[league]['verified_cached'] += 1
                continue
            last_attempt = previous.get('checked_at')
            if previous.get('unavailable') and last_attempt:
                try:
                    age = (today - datetime.fromisoformat(last_attempt[:10]).date()).days
                    if age < RETRY_MISSING_DAYS:
                        diagnostics[league]['retry_wait'] += 1
                        continue
                except ValueError:
                    pass
            pending[league].append((fid, fixture.get('date'), item.get('teams') or {}))

    remaining = MAX_REQUESTS
    while remaining and any(pending.values()):
        for league in LEAGUES:
            if not remaining or not pending[league]:
                continue
            fid, date, teams = pending[league].pop(0)
            remaining -= 1
            diagnostics[league]['stats_requested'] += 1
            rows = api_request(session, '/fixtures/statistics', {'fixture': fid})
            if rows is None:
                diagnostics[league]['stats_api_failed'] += 1
                continue  # Retry on next run
            by_id = {str((r.get('team') or {}).get('id')): r for r in rows}
            home, away = teams.get('home') or {}, teams.get('away') or {}
            hx = get_xg((by_id.get(str(home.get('id'))) or {}).get('statistics'))
            ax = get_xg((by_id.get(str(away.get('id'))) or {}).get('statistics'))
            if hx is None or ax is None:
                diagnostics[league]['provider_xg_missing'] += 1
                matches[fid] = {'unavailable': True, 'competition': league,
                                'date': date, 'checked_at': today.isoformat()}
                continue
            matches[fid] = {'competition': league, 'date': date,
                            'home': home.get('name'), 'away': away.get('name'),
                            'home_id': home.get('id'), 'away_id': away.get('id'),
                            'home_xg': hx, 'away_xg': ax,
                            'source': 'API-Football /fixtures/statistics'}
            diagnostics[league]['new_verified'] += 1

    # Group by provider team ID when available; names remain fallback for old cache.
    per_team = defaultdict(list)
    for match in matches.values():
        if not isinstance(match, dict) or match.get('unavailable') or not match.get('date'):
            continue
        for side in ('home', 'away'):
            name = match.get(side)
            key = norm(name)
            xg = match.get(side + '_xg')
            xga = match.get(('away' if side == 'home' else 'home') + '_xg')
            if not key or not isinstance(xg, (int, float)) or not isinstance(xga, (int, float)):
                continue
            per_team[key].append((match['date'], xg, xga, name, match.get('competition', '')))

    context = load(OUT)
    teams_context = context.setdefault('teams', {})
    if not isinstance(teams_context, dict):
        teams_context = {}
        context['teams'] = teams_context
    updated = 0
    insufficient = 0
    understat_preferred = 0
    for key, games in per_team.items():
        games = sorted(games, key=lambda x: x[0], reverse=True)[:20]
        if len(games) < MIN_GAMES:
            insufficient += 1
            continue
        old = teams_context.get(key) or {}
        if str(old.get('source', '')).startswith('https://understat.com/'):
            understat_preferred += 1
            continue
        teams_context[key] = {
            'name': games[0][3], 'league': games[0][4],
            'xg_game': round(sum(g[1] for g in games) / len(games), 4),
            'xga_game': round(sum(g[2] for g in games) / len(games), 4),
            'games': len(games), 'as_of': today.isoformat(),
            'source': 'API-Football verified fixture expected_goals (mixed competitions)',
            'sample': 'last_20_available'}
        updated += 1
    context['updated_at'] = now.isoformat()
    save(CACHE, {'matches': matches, 'updated_at': now.isoformat()})
    save(OUT, context)
    for league in LEAGUES:
        c = diagnostics[league]
        print(f"{league}: finished={c['finished_found']} cached_verified={c['verified_cached']} "
              f"requested={c['stats_requested']} new_xg={c['new_verified']} "
              f"provider_missing={c['provider_xg_missing']} retry_wait={c['retry_wait']} "
              f"api_errors={c['stats_api_failed'] + c['fixture_api_failed']}")
    print(f'xG coverage summary: verified_cache={sum(1 for v in matches.values() if isinstance(v,dict) and isinstance(v.get("home_xg"),(int,float)))} '
          f'teams_updated={updated} teams_below_{MIN_GAMES}_games={insufficient} '
          f'understat_preferred={understat_preferred} stat_request_budget={MAX_REQUESTS - remaining}/{MAX_REQUESTS}')
    print('Only actual provider TEAM xG is used; player xG/90 is not generated.')


if __name__ == '__main__':
    main()
