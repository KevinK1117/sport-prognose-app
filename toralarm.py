"""SportRadar ntfy goal alerts. Run periodically in GitHub Actions."""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

ROOT = Path(__file__).resolve().parent
FAVORITES = ROOT / 'data' / 'favorites.json'
STATE = ROOT / 'data' / 'toralarm_state.json'
TZ = ZoneInfo('Europe/Berlin')
API_KEY = os.environ.get('API_SPORTS_KEY', '')
TOPIC = os.environ.get('NTFY_TOPIC', '')


def get(url, **kwargs):
    try:
        r = requests.get(url, timeout=18, **kwargs)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError):
        return None


def check_nhl(fav, date):
    pid = fav.get('player_id')
    if not pid: return []
    now = datetime.now(TZ)
    yr = now.year if now.month >= 7 else now.year - 1
    payload = get(f'https://api-web.nhle.com/v1/player/{pid}/game-log/{yr}{yr+1}/2')
    if not isinstance(payload, dict): return []
    out = []
    for game in payload.get('gameLog') or []:
        if game.get('gameDate') not in date: continue
        goals = int(game.get('goals') or 0)
        if goals:
            out.append((f'nhl:{pid}:{game.get("gameId") or game.get("gameDate")}', goals, fav.get('name','Spieler'), 'NHL'))
    return out


def check_football(fav, date):
    if not API_KEY or not fav.get('player_id') or not fav.get('team_id'): return []
    headers = {'x-apisports-key': API_KEY}
    fixtures = get('https://v3.football.api-sports.io/fixtures', params={'team':fav['team_id'], 'date':date, 'timezone':'Europe/Berlin'}, headers=headers)
    if not isinstance(fixtures,dict): return []
    out=[]
    for fixture in fixtures.get('response') or []:
        fixture_id=(fixture.get('fixture') or {}).get('id')
        status=(fixture.get('fixture') or {}).get('status') or {}
        if not fixture_id or status.get('short') in ('NS','TBD','PST','CANC'): continue
        data=get('https://v3.football.api-sports.io/fixtures/players',params={'fixture':fixture_id},headers=headers)
        if not isinstance(data,dict): continue
        for team in data.get('response') or []:
            for entry in team.get('players') or []:
                if str((entry.get('player') or {}).get('id')) != str(fav['player_id']): continue
                goals=sum(int((stat.get('goals') or {}).get('total') or 0) for stat in entry.get('statistics') or [])
                if goals: out.append((f'football:{fav["player_id"]}:{fixture_id}',goals,fav.get('name','Spieler'),fav.get('league','Fußball')))
    return out


def main():
    if not TOPIC:
        print('NTFY_TOPIC fehlt'); return
    try: favorites=json.loads(FAVORITES.read_text(encoding='utf-8'))
    except (OSError,ValueError): favorites={}
    try: state=json.loads(STATE.read_text(encoding='utf-8'))
    except (OSError,ValueError): state={}
    if not isinstance(favorites,dict): favorites={}
    if not isinstance(state,dict): state={}
    now=datetime.now(TZ)
    dates={(now.date()-timedelta(days=1)).isoformat(),now.date().isoformat()}
    changed=False
    for fav in favorites.values():
        if not isinstance(fav,dict): continue
        league=fav.get('league','')
        try:
            found=check_nhl(fav,dates) if league=='NHL' else (sum((check_football(fav,d) for d in dates),[]) if league not in ('DEL','nhl','hockey') else [])
        except (ValueError,TypeError,requests.RequestException): continue
        for ident,goals,name,competition in found:
            previous=int(state.get(ident,0))
            if goals<=previous: continue
            message=f'⚽ TOR! {name} ({competition}) hat getroffen. Tore in diesem Spiel: {goals}.'
            try:
                r=requests.post(f'https://ntfy.sh/{TOPIC}',data=message.encode('utf-8'),headers={'Title':'SportRadar Toralarm','Tags':'soccer,rotating_light'},timeout=18)
                r.raise_for_status()
            except requests.RequestException:
                print('Push-Versand fehlgeschlagen, wird später erneut versucht'); continue
            state[ident]=goals;changed=True
            print('Push gesendet:',ident)
    if changed:
        STATE.parent.mkdir(parents=True,exist_ok=True)
        STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__': main()
