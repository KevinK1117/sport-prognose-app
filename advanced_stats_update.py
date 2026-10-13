"""Daily public xG sources: Understat (five football leagues), MoneyPuck (NHL).

No invented data. Failed provider requests preserve last successful CSV snapshot.
Check each provider's terms before commercial/public redistribution.
"""
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'data'/'advanced_player_metrics.csv'
TODAY=datetime.now(timezone.utc).date().isoformat()
HEAD={'User-Agent':'SportRadar personal sports statistics client (non-commercial)','X-Requested-With':'XMLHttpRequest','Referer':'https://understat.com/','Accept':'application/json, text/javascript, */*; q=0.01'}
COLS=['player_id','name','sport','team','position','image_url','as_of','sample','npxg90','xg90','ixg60','shots90','shots_on_target90','shots_in_box90','shots_on_target_game','attempts_game','expected_minutes','toi_game','pp_toi_game','high_danger_game','team_xg','penalty_taker','pp1','opponent_factor','source']

def num(x):
    try:return float(x)
    except (TypeError,ValueError):return None

def football():
    result=[]
    season=int(TODAY[:4]) if int(TODAY[5:7])>=7 else int(TODAY[:4])-1
    for league in ('Bundesliga','EPL','La_Liga','Serie_A','Ligue_1'):
        url=f'https://understat.com/getLeagueData/{league}/{season}'
        try:
            r=requests.get(url,headers=HEAD,timeout=35);r.raise_for_status();data=r.json()
            players=data.get('players',[])
            if not isinstance(players,list):raise ValueError('No player list')
            count=0
            for p in players:
                if not isinstance(p,dict):continue
                name=p.get('player_name') or p.get('player') or p.get('name')
                team=p.get('team_title') or p.get('team')
                pid=p.get('id') or p.get('player_id')
                minutes=num(p.get('time') or p.get('minutes'))
                games=num(p.get('games'))
                xg=num(p.get('xG'));npxg=num(p.get('npxG'))
                if not name or not team or not pid or not minutes or minutes<30 or xg is None:continue
                shots=num(p.get('shots'))
                row={'player_id':'understat:'+str(pid),'name':name,'sport':'Fußball','team':team,'as_of':TODAY,'sample':'season','xg90':round(xg*90/minutes,5),'npxg90':round(npxg*90/minutes,5) if npxg is not None else None,'shots90':round(shots*90/minutes,4) if shots is not None else None,'expected_minutes':round(min(90,minutes/games),2) if games and games>0 else None,'source':'Understat / '+url}
                # Historical minutes/game is a rough playing-time proxy, not a confirmed lineup.
                result.append(row);count+=1
            print('Understat',league,'players:',count)
        except (requests.RequestException,ValueError,KeyError) as exc:
            print('Understat unavailable:',league,type(exc).__name__)
    return result

def nhl():
    season=int(TODAY[:4]) if int(TODAY[5:7])>=7 else int(TODAY[:4])-1
    url=f'https://moneypuck.com/moneypuck/playerData/seasonSummary/{season}/regular/skaters.csv'
    try:
        r=requests.get(url,timeout=65,headers={'User-Agent':'SportRadar personal non-commercial research'});r.raise_for_status()
        if len(r.content)>40_000_000:raise ValueError('File too large')
        reader=csv.DictReader(io.StringIO(r.content.decode('utf-8-sig')))
        if not reader.fieldnames or 'playerId' not in reader.fieldnames:raise ValueError('Unexpected MoneyPuck columns')
        # Situation-specific PP time must come from 5on4 rows, not all-situations.
        source_rows=list(reader)
        pp_by_id={}
        for r in source_rows:
            if str(r.get('situation','')).lower() in ('5on4','5v4','pp'):
                pid=str(r.get('playerId') or '')
                pp_sec=num(r.get('icetime'))
                if pid and pp_sec is not None and pp_sec>=0:
                    pp_by_id[pid]=pp_sec
        rows=[]
        for p in source_rows:
            if p.get('situation') not in ('all','allSituations'):continue
            name=p.get('name') or p.get('playerName');pid=p.get('playerId')
            team=p.get('team') or p.get('teamCode')
            ice=num(p.get('icetime'))
            games=num(p.get('games_played') or p.get('gamesPlayed'))
            xg=num(p.get('I_F_xGoals') or p.get('I_F_xGoals_with_earned_rebounds'))
            shots=num(p.get('I_F_shotsOnGoal'))
            attempts=num(p.get('I_F_shotAttempts'))
            danger=num(p.get('I_F_highDangerShots'))
            if not all((name,pid,team,ice,games)) or xg is None or ice<=0 or games<=0:continue
            pp_seconds=pp_by_id.get(str(pid))
            rows.append({'player_id':'moneypuck:'+str(pid),'name':name,'sport':'NHL','team':team,'as_of':TODAY,'sample':'season','ixg60':round(xg*3600/ice,5),'toi_game':round(ice/60/games,3),'shots_on_target_game':round(shots/games,3) if shots is not None else None,'attempts_game':round(attempts/games,3) if attempts is not None else None,'pp_toi_game':round(pp_seconds/60/games,3) if pp_seconds is not None else None,'high_danger_game':round(danger/games,3) if danger is not None else None,'source':'MoneyPuck / '+url})
        print('MoneyPuck players:',len(rows));return rows
    except (requests.RequestException,UnicodeError,ValueError) as exc:
        print('MoneyPuck unavailable:',type(exc).__name__);return []

def main():
    incoming=football()+nhl()
    if not incoming:
        print('No provider results; retaining existing snapshot');return
    old=[]
    if OUT.exists():
        try:
            with OUT.open(encoding='utf-8-sig',newline='') as f:old=list(csv.DictReader(f))
        except (OSError,ValueError):pass
    # Retain prior league/sport records when one provider is down; never relabel stale as fresh.
    incoming_sources={(r['sport'],r['source'].split(' / ')[0],r['source'].split('/')[-2] if r['sport']=='Fußball' else 'NHL') for r in incoming}
    def source_key(r):
        s=r.get('source','');return (r.get('sport'),s.split(' / ')[0],s.split('/')[-2] if r.get('sport')=='Fußball' else 'NHL')
    preserved=[r for r in old if source_key(r) not in incoming_sources]
    combined=incoming+preserved
    OUT.parent.mkdir(parents=True,exist_ok=True)
    temp=OUT.with_suffix('.tmp')
    with temp.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=COLS,extrasaction='ignore');writer.writeheader();writer.writerows(combined)
    temp.replace(OUT)
    print('Saved',len(combined),'records; new',len(incoming),'at',OUT)

if __name__=='__main__':main()
