"""Refresh public fixture snapshots daily; never persist private API credentials."""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / 'data' / 'daily_fixtures.json'
TZ = ZoneInfo('Europe/Berlin')
LEAGUES = {'Bundesliga':78,'2. Bundesliga':79,'La Liga':140,'Serie A':135,'Premier League':39,'Ligue 1':61,'MLS':253}
KEY = os.environ.get('API_SPORTS_KEY', '')
DEL_ID = os.environ.get('DEL_LEAGUE_ID', '')


def fetch(url, *, params=None, headers=None):
    try:
        r = requests.get(url, params=params, headers=headers, timeout=25)
        r.raise_for_status()
        obj = r.json()
        if isinstance(obj, dict) and obj.get('errors'):
            return None
        return obj
    except (requests.RequestException, ValueError) as exc:
        print(f'Fetch unavailable: {url}: {exc}')
        return None


def main():
    now = datetime.now(TZ)
    days = [(now.date() + timedelta(days=i)).isoformat() for i in (0,1)]
    snapshot = {'updated_at':now.isoformat(), 'dates':days, 'nhl':{}, 'football':{}, 'del':{}}
    for date in days:
        nhl = fetch(f'https://api-web.nhle.com/v1/score/{date}')
        if nhl is not None:
            snapshot['nhl'][date] = nhl
        if KEY:
            headers = {'x-apisports-key':KEY}
            for league, ident in LEAGUES.items():
                year = int(date[:4]) if league == 'MLS' or int(date[5:7]) >= 7 else int(date[:4])-1
                obj = fetch('https://v3.football.api-sports.io/fixtures',params={'league':ident,'season':year,'date':date,'timezone':'Europe/Berlin'},headers=headers)
                if obj is not None:
                    snapshot['football'][f'{league}|{date}'] = obj.get('response',[])
            if DEL_ID:
                obj = fetch('https://v1.hockey.api-sports.io/games',params={'league':DEL_ID,'date':date,'timezone':'Europe/Berlin'},headers=headers)
                if obj is not None:
                    snapshot['del'][date] = obj.get('response',[])
    if not any(snapshot[k] for k in ('nhl','football','del')):
        raise SystemExit('No valid data retrieved; preserving previous snapshot.')
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'Updated {TARGET}: {now.isoformat()}, NHL dates={len(snapshot["nhl"])}, football fixtures={len(snapshot["football"])}')

if __name__ == '__main__':
    main()
