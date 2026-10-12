"""Collect verified NHL individual game logs daily; never synthesize xG/PP minutes."""
import concurrent.futures
import json
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'data'/'daily_player_stats.json'
FIX=ROOT/'data'/'daily_fixtures.json'
SESSION=requests.Session()

def get(path):
    try:
        r=SESSION.get('https://api-web.nhle.com/v1/'+path,timeout=18)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException,ValueError):
        return None

def number(value):
    try:return float(value)
    except (ValueError,TypeError):return None

def toi(value):
    if isinstance(value,(float,int)):return float(value)
    try:
        parts=str(value).split(':')
        return int(parts[0])+int(parts[1])/60 if len(parts)==2 else None
    except (ValueError,TypeError):return None

def main():
    if not FIX.exists():raise SystemExit('daily_fixtures.json fehlt; zuerst daily_update.py ausführen')
    fixture=json.loads(FIX.read_text(encoding='utf-8'))
    clubs=set()
    for payload in fixture.get('nhl',{}).values():
        for game in (payload.get('games',[]) if isinstance(payload,dict) else []):
            for side in ('homeTeam','awayTeam'):
                team=game.get(side) or {}
                if isinstance(team.get('abbrev'),str):clubs.add(team['abbrev'])
    print('NHL teams scheduled:',len(clubs))
    players=[]
    for club in sorted(clubs):
        stats=get(f'club-stats/{club}/now')
        if not isinstance(stats,dict):continue
        for p in stats.get('skaters',[]):
            pid=p.get('playerId') or p.get('id')
            if not pid:continue
            first=p.get('firstName') or '';last=p.get('lastName') or ''
            if isinstance(first,dict):first=first.get('default','')
            if isinstance(last,dict):last=last.get('default','')
            players.append((pid,club,(str(first)+' '+str(last)).strip(),p))
    now=datetime.now(timezone.utc)
    season=now.year if now.month>=7 else now.year-1
    code=f'{season}{season+1}'
    def collect(entry):
        pid,club,name,season_row=entry
        log=get(f'player/{pid}/game-log/{code}/2')
        if not isinstance(log,dict):return None
        games=[]
        for g in log.get('gameLog',[]):
            date=str(g.get('gameDate',''))[:10]
            if not date or date>=now.date().isoformat():continue
            games.append({'date':date,'goals':int(g.get('goals') or 0),'shots':int(g.get('shots') or 0),'toi':toi(g.get('toi') or g.get('timeOnIce'))})
        games.sort(key=lambda x:x['date'],reverse=True)
        if not games:return None
        def summary(sample):
            minutes=[g['toi'] for g in sample if g['toi'] is not None]
            return {'games':len(sample),'goals':sum(g['goals'] for g in sample),'shots':sum(g['shots'] for g in sample),'toi_game':round(sum(minutes)/len(minutes),2) if minutes else None,'shots_on_target_game':round(sum(g['shots'] for g in sample)/len(sample),2)}
        return str(pid),{'name':name,'team':club,'sport':'NHL','source':'NHL API / player game-log','updated_at':now.isoformat(),'season':summary(games),'last20':summary(games[:20]),'last5':summary(games[:5]),'games':games[:20],'ixg60':None,'pp_toi_game':None,'pp1':None}
    result={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for item in pool.map(collect,players):
            if item:result[item[0]]=item[1]
    if not result:raise SystemExit('Keine NHL-Spielerlogs abrufbar; bisherige Daten bleiben erhalten')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({'updated_at':now.isoformat(),'nhl':result,'source':'NHL API'},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('NHL player records:',len(result),'saved:',OUT)

if __name__=='__main__':main()
