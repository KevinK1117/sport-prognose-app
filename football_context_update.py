"""Daily football team xG/xGA and historical penalty evidence. Missing data stays missing."""
import csv, json, os, re, unicodedata
from datetime import datetime, timezone
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'data'/'football_context.json'
FIX=ROOT/'data'/'daily_fixtures.json'
LEAGUES=('Bundesliga','EPL','La_Liga','Serie_A','Ligue_1')
HEAD={'User-Agent':'SportRadar statistics research','X-Requested-With':'XMLHttpRequest','Referer':'https://understat.com/'}
def norm(x):
    s=''.join(c for c in unicodedata.normalize('NFKD',str(x or '').casefold()) if not unicodedata.combining(c))
    return re.sub('[^a-z0-9]','',s)
def number(x):
    try:return float(x)
    except (TypeError,ValueError):return None
def main():
    now=datetime.now(timezone.utc); season=now.year if now.month>=7 else now.year-1
    old={}
    if OUT.exists():
        try:old=json.loads(OUT.read_text())
        except (ValueError,OSError):pass
    teams=dict(old.get('teams') or {}); penalties=dict(old.get('penalties') or {})
    for league in LEAGUES:
        url=f'https://understat.com/getLeagueData/{league}/{season}'
        try:
            response=requests.get(url,headers=HEAD,timeout=35);response.raise_for_status();data=response.json()
            found=0
            for item in (data.get('teams') or {}).values():
                name=item.get('title');history=item.get('history') or []
                if not name or not history:continue
                # Only completed historical games; do not use future matches.
                past=[h for h in history if str(h.get('date',''))[:10]<now.date().isoformat() and number(h.get('xG')) is not None and number(h.get('xGA')) is not None]
                if not past:continue
                xg=sum(number(h['xG']) for h in past)/len(past)
                xga=sum(number(h['xGA']) for h in past)/len(past)
                teams[norm(name)]={'name':name,'league':league,'xg_game':round(xg,4),'xga_game':round(xga,4),'games':len(past),'as_of':now.date().isoformat(),'source':url}
                found+=1
            print('Understat team context:',league,found)
        except (requests.RequestException,ValueError,TypeError) as e:print('Team context unavailable:',league,type(e).__name__)
    # API-Football season player statistics provide past penalties scored/missed,
    # not confirmation of the next penalty taker. Keep them labelled as evidence.
    key=os.environ.get('API_SPORTS_KEY','').strip()
    if key and FIX.exists():
        try:fixtures=json.loads(FIX.read_text()).get('football') or {}
        except (ValueError,OSError):fixtures={}
        candidates={}
        for fixture_list in fixtures.values():
            for game in fixture_list if isinstance(fixture_list,list) else []:
                league=game.get('league') or {};season_id=league.get('season')
                for side in ('home','away'):
                    team=(game.get('teams') or {}).get(side) or {};tid=team.get('id')
                    if tid and season_id:candidates[(tid,season_id)]=team.get('name','')
        # Bounded calls; API-Football player endpoint is paginated.
        for (tid,year),team_name in list(candidates.items())[:24]:
            try:
                r=requests.get('https://v3.football.api-sports.io/players',params={'team':tid,'season':year,'page':1},headers={'x-apisports-key':key},timeout=22)
                r.raise_for_status();payload=r.json()
                if payload.get('errors'):continue
                if int((payload.get('paging') or {}).get('total') or 1)>1:
                    print('Penalty evidence skipped (pagination incomplete):',team_name);continue
                for record in payload.get('response') or []:
                    player=record.get('player') or {};pid=player.get('id')
                    if not pid:continue
                    for stat in record.get('statistics') or []:
                        if (stat.get('team') or {}).get('id')!=tid:continue
                        p=stat.get('penalty') or {};scored=number(p.get('scored'));missed=number(p.get('missed'))
                        if scored is None and missed is None:continue
                        penalties[str(pid)]={'name':player.get('name'),'team':team_name,'team_id':tid,'season':year,'scored':scored,'missed':missed,'as_of':now.date().isoformat(),'source':'API-Football /players (historical evidence only)'}
            except (requests.RequestException,ValueError,TypeError) as e:print('Penalty evidence unavailable:',team_name,type(e).__name__)
    if not teams and not penalties:
        print('No new context; old file retained');return
    OUT.parent.mkdir(exist_ok=True,parents=True)
    OUT.write_text(json.dumps({'updated_at':now.isoformat(),'teams':teams,'penalties':penalties},ensure_ascii=False),encoding='utf-8')
    print('Saved team context',len(teams),'penalty records',len(penalties))
if __name__=='__main__':main()
