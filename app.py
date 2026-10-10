import math
import json
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title='SportRadar | Torprognosen', page_icon='🎯', layout='wide')
st.markdown('''<style>
.block-container{max-width:1050px;padding-top:1.2rem}h1,h2,h3{color:#30333e}.match{background:#eef0f5;border:1px solid #d5d6da;border-radius:16px;padding:15px 18px;margin:15px 0 9px;font-weight:650}.player{background:#fafafa;border:1px solid #d8d8dc;border-radius:22px;padding:20px;margin:10px 0}.pct{font-size:29px;font-weight:750;float:right}.muted{color:#858791;font-size:14px}.pill{display:inline-block;background:#ededee;border-radius:12px;padding:7px 11px;margin:7px 5px 0 0;font-size:14px}.stTabs [data-baseweb="tab-highlight"]{background:#ef5350}.stTabs [aria-selected="true"]{color:#ef5350!important}div[data-testid="stMetric"]{background:#fafafa;border:1px solid #ddd;border-radius:14px;padding:12px}</style>''', unsafe_allow_html=True)
TZ=ZoneInfo('Europe/Berlin')
LEAGUES={'Bundesliga':78,'2. Bundesliga':79,'La Liga':140,'Serie A':135,'Premier League':39,'Ligue 1':61,'MLS':253}

def secret(name):
    try:return st.secrets.get(name,'')
    except Exception:return ''

@st.cache_data(ttl=1800,show_spinner=False)
def api(path,params=None,provider='football'):
    key=secret('API_SPORTS_KEY')
    if not key:return None
    base='https://v3.football.api-sports.io' if provider=='football' else 'https://v1.hockey.api-sports.io'
    try:
        r=requests.get(base+'/'+path,params=params or {},headers={'x-apisports-key':key},timeout=18)
        r.raise_for_status(); data=r.json()
        if data.get('errors'):return None
        return data.get('response',[])
    except (requests.RequestException,ValueError):return None

@st.cache_data(ttl=1800,show_spinner=False)
def nhl(path):
    try:
        r=requests.get('https://api-web.nhle.com/v1/'+path,timeout=15);r.raise_for_status();return r.json()
    except (requests.RequestException,ValueError):return None

def daily_snapshot():
    path = Path(__file__).resolve().parent / 'data' / 'daily_fixtures.json'
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}

def fixtures_for(sport, day, league=None):
    snap = daily_snapshot()
    date = day.isoformat()
    if date not in snap.get('dates', []):
        return None
    if sport == 'football':
        return snap.get('football', {}).get(f'{league}|{date}')
    return snap.get(sport, {}).get(date)

def season(day,league):
    # MLS plays in calendar years; European football and hockey cross calendar years.
    return day.year if league=='MLS' else day.year if day.month>=7 else day.year-1

def probability(goals,games,minutes=None,period=1.0,prior=0.12,prior_games=8):
    # Gamma-Poisson shrinkage: avoids extreme estimates with very small samples.
    if games is None or games<=0:return None
    rate=(max(0,goals)+prior*prior_games)/(games+prior_games)
    if minutes is not None and minutes>0:rate*=min(1.35,max(.45,minutes/75))
    return 100*(-math.expm1(-rate*period))

def show_player(name,team,p,goals,games,shots=None,minutes=None,form=None,half=None):
    score=f'{p:.1f} %' if p is not None else '–'
    pills=[f'{goals} Tore',f'{games} Spiele']
    if shots is not None:pills.append(f'{shots} Schüsse')
    if minutes is not None:pills.append(f'{minutes:.1f} Min Ø')
    if form is not None:pills.append(f'Form: {form}')
    if half is not None:pills.append(f'1. HZ: {half:.1f} %')
    chips=''.join(f'<span class="pill">{x}</span>' for x in pills)
    st.markdown(f'<div class="player"><span class="pct">{score}</span><b>{name}</b><div class="muted">{team} · geschätzte Torchance</div><div>{chips}</div></div>',unsafe_allow_html=True)

def football_players(league,year,team_ids):
    # Paginated player season totals; API quota depends on subscription.
    result=[]
    for page in range(1,9):
        rows=api('players',{'league':league,'season':year,'page':page})
        if rows is None:return None
        for entry in rows:
            for s in entry.get('statistics',[]):
                team=s.get('team') or {}
                if team.get('id') not in team_ids:continue
                g=s.get('games') or {}; goals=s.get('goals') or {}; shots=s.get('shots') or {}
                apps=g.get('appearences') or 0
                if not apps:continue
                mins=g.get('minutes') or 0
                n=goals.get('total') or 0
                avgmins=mins/apps
                p=probability(n,apps,avgmins)
                result.append({'name':entry.get('player',{}).get('name','Unbekannt'),'team':team.get('name',''),'goals':n,'games':apps,'shots':shots.get('total'),'minutes':avgmins,'p':p,'half':probability(n,apps,avgmins,period=.45)})
        if len(rows)<20:break
    return sorted(result,key=lambda x:x['p'] or 0,reverse=True)

def football_view(day,league):
    year=season(day,league)
    fixtures=fixtures_for('football',day,league)
    if fixtures is None:
        fixtures=api('fixtures',{'league':LEAGUES[league],'season':year,'date':day.isoformat(),'timezone':'Europe/Berlin'})
    if fixtures is None:
        st.warning('Fußballdaten nicht verfügbar. API_SPORTS_KEY in Streamlit Secrets hinterlegen und API-Tarif prüfen.');return
    if not fixtures:st.info('Keine Begegnungen an diesem Tag.');return
    st.caption(f'Saison {year}/{str(year+1)[-2:]}' if league!='MLS' else f'Saison {year}')
    for match in sorted(fixtures,key=lambda m:m.get('fixture',{}).get('timestamp',0)):
        f=match.get('fixture',{});teams=match.get('teams',{})
        home=teams.get('home',{});away=teams.get('away',{})
        local=datetime.fromtimestamp(f.get('timestamp',0),TZ).strftime('%H:%M')
        title=f'⚽ {local} Uhr · {home.get("name","?")} – {away.get("name","?")}'
        with st.expander(title,expanded=True):
            st.caption('Vorhersagen sind Modellschätzungen auf Basis aggregierter Saisonwerte, keine Wettquoten. 1.-Halbzeit-Werte verwenden eine angenommene Torverteilung.')
            with st.spinner('Spielerstatistiken laden …'):
                players=football_players(LEAGUES[league],year,{home.get('id'),away.get('id')})
            if players is None:st.warning('Spielerstatistiken fehlen oder API-Kontingent erreicht.');continue
            if not players:st.info('Noch keine Spielerdaten für diese Paarung vorhanden.');continue
            tabs=st.tabs(['🎯 Top-Torschützen','⏱️ 1. Halbzeit','📊 Tabelle'])
            with tabs[0]:
                for p in players[:15]:show_player(p['name'],p['team'],p['p'],p['goals'],p['games'],p['shots'],p['minutes'],half=p['half'])
            with tabs[1]:
                for p in sorted(players,key=lambda p:p['half'] or 0,reverse=True)[:15]:show_player(p['name'],p['team'],p['half'],p['goals'],p['games'],p['shots'],p['minutes'])
            with tabs[2]:
                st.dataframe(pd.DataFrame([{**p,'p':round(p['p'],1),'half':round(p['half'],1)} for p in players]).rename(columns={'name':'Spieler','team':'Team','goals':'Tore','games':'Spiele','shots':'Schüsse','minutes':'Min Ø','p':'Tor %','half':'1. HZ %'}),hide_index=True,use_container_width=True)

def nhl_view(day):
    schedule=fixtures_for('nhl',day) or nhl('score/'+day.isoformat())
    if not schedule:st.warning('NHL-Daten aktuell nicht erreichbar.');return
    games=schedule.get('games',[])
    if not games:st.info('Keine NHL-Spiele an diesem Tag.');return
    for g in games:
        home=g.get('homeTeam',{});away=g.get('awayTeam',{})
        ts=g.get('startTimeUTC','')
        try:time=datetime.fromisoformat(ts.replace('Z','+00:00')).astimezone(TZ).strftime('%H:%M')
        except ValueError:time='–'
        with st.expander(f'🏒 {time} Uhr · {away.get("abbrev","?")} @ {home.get("abbrev","?")}',expanded=True):
            st.caption('NHL: offizielle Spieldaten. Spielerwerte aus Saisonstatistiken, sofern verfügbar.')
            allplayers=[]
            for team in (home,away):
                ab=team.get('abbrev','')
                roster=nhl('club-stats/'+ab+'/now') if ab else None
                for p in (roster or {}).get('skaters',[]):
                    gp=p.get('gamesPlayed',0);goals=p.get('goals',0)
                    if not gp:continue
                    name=p.get('firstName',{}).get('default','')+' '+p.get('lastName',{}).get('default','')
                    shots=p.get('shots')
                    allplayers.append({'name':name.strip(),'team':ab,'goals':goals,'games':gp,'shots':shots,'p':probability(goals,gp,prior=.18)})
            allplayers.sort(key=lambda p:p['p'] or 0,reverse=True)
            tabs=st.tabs(['🎯 Top-Torschützen','📊 Tabelle'])
            with tabs[0]:
                for p in allplayers[:20]:show_player(p['name'],p['team'],p['p'],p['goals'],p['games'],p['shots'])
                if not allplayers:st.info('Noch keine Saison-Spielerstatistiken verfügbar.')
            with tabs[1]:
                if allplayers:st.dataframe(pd.DataFrame(allplayers),hide_index=True,use_container_width=True)
            st.caption('NHL-Schüsse/Eiszeit/Form nur bei verlässlich gelieferten Daten; nicht verfügbare Werte werden ausgelassen.')

def del_view(day):
    # DEL league ID is provider-specific: configure rather than assuming an ID.
    league_id=secret('DEL_LEAGUE_ID')
    if not league_id:
        st.warning('DEL_LEAGUE_ID in Secrets konfigurieren. Die Hockey-API muss DEL und Spielerstatistiken im gewählten Tarif abdecken.');return
    rows=fixtures_for('del',day)
    if rows is None:
        rows=api('games',{'league':league_id,'date':day.isoformat(),'timezone':'Europe/Berlin'},provider='hockey')
    if rows is None:st.warning('DEL-Spiele derzeit nicht abrufbar.');return
    if not rows:st.info('Keine DEL-Spiele gefunden.');return
    for m in rows:
        teams=m.get('teams',{});h=teams.get('home',{});a=teams.get('away',{})
        with st.expander(f'🏒 {h.get("name","Heim")} – {a.get("name","Gast")}',expanded=True):
            st.tabs(['🎯 Top-Torschützen','📊 Tabelle'])
            st.info('Für DEL-Spielerprognosen wird ein Feed mit aktuellen Spieler-Toren, Schüssen und Eiszeit benötigt. Ohne diesen werden keine Wahrscheinlichkeiten erfunden.')

st.title('🎯 SportRadar – Torschützen heute & morgen')
st.caption('Deutsche Zeit · Saison automatisch · Poisson-Modell mit Stichproben-Glättung')
sport=st.radio('Sportart',['🏒 Eishockey','⚽ Fußball'],horizontal=True)
if sport.startswith('🏒'):league=st.selectbox('Liga',['NHL','DEL'])
else:league=st.selectbox('Liga',list(LEAGUES))
day_choice=st.radio('Spieltag',['Heute','Morgen'],horizontal=True)
day=datetime.now(TZ).date()+timedelta(days=int(day_choice=='Morgen'))
st.caption(day.strftime('%d.%m.%Y'))
snapshot=daily_snapshot()
if snapshot.get('updated_at'):
    st.caption('🕗 Letzte tägliche Aktualisierung: '+snapshot['updated_at'][:16].replace('T',' ')+' Uhr (Deutschland)')
else:
    st.caption('🕗 Automatische Aktualisierung täglich 08:00 Uhr nach GitHub-Veröffentlichung und Einrichtung der Secrets')
if st.button('🔄 Daten aktualisieren'):
    st.cache_data.clear();st.rerun()
if sport.startswith('🏒'):
    (nhl_view if league=='NHL' else del_view)(day)
else:football_view(day,league)
st.divider()
st.caption('Hinweis: Schätzungen sind keine garantierten Trefferwahrscheinlichkeiten. Kleine Stichproben, Aufstellungen, Verletzungen und Gegnerstärke können die Aussagekraft begrenzen. Keine erfundenen Spieler- oder Schussdaten.')
