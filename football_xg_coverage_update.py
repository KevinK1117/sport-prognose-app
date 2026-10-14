"""Incrementally extend verified TEAM xG/xGA to all SportRadar football competitions.

API-Football fixture statistics may include 'expected_goals'. If absent, NEVER
infer xG from goals/shots. Caches verified match values across daily runs.
Requires API_SPORTS_KEY and a plan with fixture statistics for each competition.
"""
import json, os, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'data'/'football_context.json'
CACHE=ROOT/'data'/'football_fixture_xg_cache.json'
LEAGUES={'Bundesliga':78,'2. Bundesliga':79,'La Liga':140,'Serie A':135,
         'Premier League':39,'Ligue 1':61,'MLS':253,'Champions League':2,
         'Europa League':3,'Saudi Pro League':307}
KEY=os.getenv('API_SPORTS_KEY','').strip()
MAX_STAT_REQUESTS=int(os.getenv('FOOTBALL_XG_MAX_REQUESTS','45'))
API='https://v3.football.api-sports.io'

def norm(value):
    import re,unicodedata
    s=''.join(c for c in unicodedata.normalize('NFKD',str(value or '').casefold()) if not unicodedata.combining(c))
    return re.sub('[^a-z0-9]','',s)

def load(path):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}

def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(path)

def request(session,path,params):
    try:
        r=session.get(API+path,params=params,timeout=25)
        if r.status_code in (401,403,429):
            print('API access/rate limit:',r.status_code,path)
            return None
        r.raise_for_status();obj=r.json()
        if obj.get('errors'):
            print('API provider error:',path,str(obj['errors'])[:180]);return None
        return obj.get('response') or []
    except (requests.RequestException,ValueError,TypeError) as exc:
        print('API unavailable:',path,type(exc).__name__);return None

def stat_xg(stats):
    for item in stats or []:
        if str(item.get('type','')).strip().lower() in ('expected goals','expected_goals','xg'):
            try:
                v=float(item.get('value'))
                if 0<=v<=15:return v
            except (ValueError,TypeError):pass
    return None

def main():
    if not KEY:
        print('API_SPORTS_KEY missing; keeping existing xG data');return
    session=requests.Session();session.headers.update({'x-apisports-key':KEY})
    now=datetime.now(timezone.utc);today=now.date()
    cache=load(CACHE);matches=cache.get('matches') or {}
    # Collect fixture IDs across ten competitions, only finished fixtures.
    # A rolling 35-day discovery window plus persistent cache accumulates history.
    pending={league:[] for league in LEAGUES}
    for league,league_id in LEAGUES.items():
        # Football seasons start in summer except MLS (calendar-year).
        season=today.year if league=='MLS' or today.month>=7 else today.year-1
        rows=request(session,'/fixtures',{'league':league_id,'season':season,
              'from':(today-timedelta(days=35)).isoformat(),'to':(today-timedelta(days=1)).isoformat()})
        if rows is None:continue
        for f in rows:
            fixture=f.get('fixture') or {};status=(fixture.get('status') or {}).get('short')
            if status not in ('FT','AET','PEN'):continue
            fid=fixture.get('id');teams=f.get('teams') or {}
            if not fid:continue
            key=str(fid)
            if key not in matches:
                pending[league].append((key,league,fixture.get('date'),teams))
    # Round-robin across leagues so smaller competitions aren't starved.
    remaining=max(0,MAX_STAT_REQUESTS);successful=0
    while remaining and any(pending.values()):
        for league in LEAGUES:
            if not pending[league] or not remaining:continue
            fid,competition,date,teams=pending[league].pop(0)
            remaining-=1
            rows=request(session,'/fixtures/statistics',{'fixture':fid})
            if rows is None:continue  # retry next day
            by_id={str((r.get('team') or {}).get('id')):r for r in rows}
            home=teams.get('home') or {};away=teams.get('away') or {}
            hs=by_id.get(str(home.get('id')),{});aws=by_id.get(str(away.get('id')), {})
            hx=stat_xg(hs.get('statistics'));ax=stat_xg(aws.get('statistics'))
            if hx is None or ax is None:
                # Provider lacks real xG for this fixture; don't retry endlessly.
                matches[fid]={'unavailable':True,'competition':competition,'date':date}
                continue
            matches[fid]={'competition':competition,'date':date,'home':home.get('name'),
                'away':away.get('name'),'home_xg':hx,'away_xg':ax,'source':'API-Football /fixtures/statistics'}
            successful+=1
    # Keep the most recent 20 verified fixtures for each team across competitions.
    per_team={}
    for rec in matches.values():
        if rec.get('unavailable') or not rec.get('date'):continue
        for side in ('home','away'):
            name=rec.get(side);key=norm(name)
            if not key:continue
            xg=rec.get(side+'_xg');xga=rec.get(('away' if side=='home' else 'home')+'_xg')
            if not isinstance(xg,(int,float)) or not isinstance(xga,(int,float)):continue
            per_team.setdefault(key,[]).append((rec['date'],xg,xga,name,rec['competition']))
    context=load(OUT);team_context=context.setdefault('teams',{})
    added=0
    for key,items in per_team.items():
        items=sorted(items,reverse=True)[:20]
        if len(items)<3:continue
        existing=team_context.get(key) or {}
        # Prefer Understat's established domestic-season data when available.
        if str(existing.get('source','')).startswith('https://understat.com/'):
            continue
        team_context[key]={'name':items[0][3],'league':items[0][4],
            'xg_game':round(sum(x[1] for x in items)/len(items),4),
            'xga_game':round(sum(x[2] for x in items)/len(items),4),
            'games':len(items),'as_of':today.isoformat(),
            'source':'API-Football verified fixture expected_goals (mixed competitions)',
            'sample':'last_20_available'}
        added+=1
    context['updated_at']=now.isoformat()
    save(CACHE,{'matches':matches,'updated_at':now.isoformat()})
    save(OUT,context)
    print('xG coverage:',successful,'new verified fixtures;',len(matches),'cached fixtures;',added,'team records updated')
    print('Note: this expands TEAM xG/xGA, not player xG/90; missing provider xG remains unavailable.')

if __name__=='__main__':main()
