


"""SportRadar – football, NHL and DEL goalscorer estimates."""
import html
import json
import math
import os
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="SportRadar | Torprognosen", page_icon="🎯", layout="wide")
st.markdown("""<style>
.block-container{max-width:1050px;padding-top:1.2rem}
.player{background:#fafafa;border:1px solid #d8d8dc;border-radius:18px;padding:15px;margin:10px 0;color:#30333e}
.player-head{font-weight:700;font-size:1.08rem}.muted{color:#777b85;font-size:.88rem}
.pair{display:flex;gap:10px;margin-top:12px}.prob{flex:1;background:#eef0f5;border-radius:12px;padding:12px 9px;text-align:center}
.prob strong{display:block;font-size:1.4rem;color:#30333e}.prob small{color:#646a77}
.pill{display:inline-block;background:#ededee;border-radius:10px;padding:5px 9px;margin:9px 5px 0 0;font-size:.83rem}
.sr-match{display:grid;grid-template-columns:minmax(0,1fr) 20px minmax(0,1fr);align-items:center;gap:6px;margin:5px 0 15px;padding:10px 4px}
.sr-match-team{display:flex;flex-direction:column;align-items:center;justify-content:center;min-width:0;gap:8px;text-align:center}
.sr-match-logo{width:58px;height:58px;display:flex;align-items:center;justify-content:center}
.sr-match-name{font-size:clamp(.83rem,2.8vw,1.04rem);font-weight:700;line-height:1.3;overflow-wrap:anywhere}
.sr-versus{text-align:center;font-size:1.3rem;font-weight:700;color:#858b95}
.sr-team-heading{display:flex;align-items:center;gap:10px;margin:20px 0 9px;font-size:1.15rem;font-weight:700;line-height:1.3}
.sr-small-logo{width:36px;height:36px;flex:none;display:flex;align-items:center;justify-content:center}
.team-logo-fallback{font-size:1.7rem}
@media(max-width:480px){.sr-match-logo{width:49px;height:49px}.sr-match{gap:4px;padding:7px 0}.sr-team-heading{font-size:1.02rem}}
</style>""", unsafe_allow_html=True)
TZ = ZoneInfo("Europe/Berlin")
LEAGUES = {"Bundesliga":78,"2. Bundesliga":79,"La Liga":140,"Serie A":135,"Premier League":39,"Ligue 1":61,"MLS":253}
DEL_TEAMS = {"team_1":"ERC Ingolstadt","team_2":"Adler Mannheim","team_3":"Eisbären Berlin","team_5":"Krefeld Pinguine","team_6":"Straubing Tigers","team_7":"Iserlohn Roosters","team_8":"Grizzlys Wolfsburg","team_9":"Pinguins Bremerhaven","team_11":"Kölner Haie","team_12":"EHC Red Bull München","team_13":"Augsburger Panther","team_14":"Nürnberg Ice Tigers","team_15":"Schwenninger Wild Wings","team_44":"Löwen Frankfurt"}
DEL_ALIASES = {"team_1":["Ingolstadt"],"team_2":["Mannheim"],"team_3":["Berlin","Eisbaeren Berlin"],"team_5":["Krefeld"],"team_6":["Straubing"],"team_7":["Iserlohn"],"team_8":["Wolfsburg"],"team_9":["Bremerhaven","Fischtown Pinguins","Fischtown Pinguins Bremerhaven"],"team_11":["Köln","Koeln","Kolner Haie"],"team_12":["München","Muenchen","Red Bull München","EHC München"],"team_13":["Augsburg"],"team_14":["Nürnberg","Nuernberg","Nuremberg Ice Tigers"],"team_15":["Schwenningen"],"team_44":["Frankfurt","Loewen Frankfurt","Frankfurt Lowen","Frankfurt Loewen","Frankfurt Löwen"]}


def secret(name):
    try:
        value=st.secrets.get(name,"")
        if value: return str(value)
    except Exception: pass
    return os.environ.get(name,"")


@st.cache_data(ttl=1800,show_spinner=False)
def api(path,params=None,provider="football",key=""):
    if not key: return None
    base="https://v3.football.api-sports.io" if provider=="football" else "https://v1.hockey.api-sports.io"
    try:
        r=requests.get(f"{base}/{path}",params=params or {},headers={"x-apisports-key":key},timeout=20)
        r.raise_for_status(); obj=r.json()
        if not isinstance(obj,dict) or obj.get("errors"): return None
        return obj.get("response",[])
    except (requests.RequestException,ValueError): return None


@st.cache_data(ttl=1800,show_spinner=False)
def nhl(path):
    try:
        r=requests.get("https://api-web.nhle.com/v1/"+path,timeout=20)
        r.raise_for_status(); return r.json()
    except (requests.RequestException,ValueError): return None


@st.cache_data(ttl=60,show_spinner=False)
def daily_snapshot():
    path=Path(__file__).resolve().parent/"data"/"daily_fixtures.json"
    try:
        obj=json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj,dict) else {}
    except (OSError,ValueError): return {}


def fixtures_for(sport,day,league=None):
    snap=daily_snapshot(); date=day.isoformat()
    if date not in snap.get("dates",[]): return None
    if sport=="football": return snap.get("football",{}).get(f"{league}|{date}")
    return snap.get(sport,{}).get(date)


def season(day,league):
    return day.year if league=="MLS" or day.month>=7 else day.year-1


def probability(goals,games,minutes=None,period=1.0,prior=0.12,prior_games=8):
    if not games or games<=0: return None
    rate=(max(0,goals)+prior*prior_games)/(games+prior_games)
    if minutes is not None and minutes>0: rate*=min(1.35,max(0.45,minutes/75))
    return 100*(-math.expm1(-rate*period))


def pct(value):
    return "–" if value is None else f"{value:.1f} %".replace(".",",")


def safe_logo(value):
    """Use only direct HTTPS image URLs, never arbitrary HTML."""
    if isinstance(value,str) and value.startswith("https://") and not any(c in value for c in '<>"\''):
        return value
    return None


def logo_html(logo, size=52):
    """Small, bounded team logo; retain an icon if no logo is provided."""
    url = safe_logo(logo)
    if not url:
        return '<span class="team-logo-fallback">🛡️</span>'
    return (
        f'<img src="{html.escape(url, quote=True)}" '
        f'alt="Vereinslogo" width="{size}" height="{size}" '
        'style="width:100%;height:100%;object-fit:contain" loading="lazy">'
    )


def team_heading(name, logo, away=False):
    """Compact inline logo and name; no stacked Streamlit columns."""
    label = html.escape(str(name))
    st.markdown(
        '<div class="sr-team-heading">'
        f'<span class="sr-small-logo">{logo_html(logo, 34)}</span>'
        f'<span>{label}</span></div>',
        unsafe_allow_html=True,
    )


def match_heading(home_name, home_logo, away_name, away_logo):
    """Three-column fixture banner that remains side-by-side on iPhone."""
    st.markdown(
        '<div class="sr-match">'
        '<div class="sr-match-team">'
        f'<span class="sr-match-logo">{logo_html(home_logo)}</span>'
        f'<span class="sr-match-name">{html.escape(str(home_name))}</span>'
        '</div>'
        '<span class="sr-versus">–</span>'
        '<div class="sr-match-team">'
        f'<span class="sr-match-logo">{logo_html(away_logo)}</span>'
        f'<span class="sr-match-name">{html.escape(str(away_name))}</span>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def show_player(player,period_label):
    name=html.escape(str(player["name"])); team=html.escape(str(player["team"]))
    pills=[f'{player["goals"]} Tore',f'{player["games"]} Spiele']
    if player.get("shots") is not None: pills.append(f'{player["shots"]} Schüsse')
    if player.get("minutes") is not None: pills.append(f'{player["minutes"]:.0f} Min Ø')
    chips="".join('<span class="pill">'+html.escape(str(item))+"</span>" for item in pills)
    st.markdown(f'''<div class="player"><div class="player-head">{name}</div><div class="muted">{team}</div><div class="pair"><div class="prob"><small>{html.escape(period_label)}</small><strong>{pct(player.get("half"))}</strong></div><div class="prob"><small>Gesamtspiel</small><strong>{pct(player.get("p"))}</strong></div></div><div>{chips}</div></div>''',unsafe_allow_html=True)


def show_players(players,period_label):
    if not players:
        st.info("Keine verlässlichen Spielerstatistiken verfügbar."); return
    tab1,tab2=st.tabs(["🎯 Spielerprognosen","📊 Tabelle"])
    with tab1:
        for p in players: show_player(p,period_label)
    with tab2:
        table=[]
        for p in players:
            minutes=p.get("minutes")
            table.append({"Spieler":p["name"],"Team":p["team"],period_label:pct(p.get("half")),"Gesamtspiel":pct(p.get("p")),"Tore":p["goals"],"Spiele":p["games"],"Schüsse":p.get("shots"),"Min Ø":round(minutes,1) if minutes is not None else None})
        st.dataframe(pd.DataFrame(table),hide_index=True,use_container_width=True)


def selection_limit(key):
    choice=st.radio("Spieler pro Mannschaft anzeigen",["Top 5","Top 10","Alle"],horizontal=True,key=key)
    return {"Top 5":5,"Top 10":10,"Alle":None}[choice]


def show_match_teams(home_name,home_logo,home_players,away_name,away_logo,away_players,period_label,widget_key):
    """Same layout across all sports; top N for EACH team."""
    limit=selection_limit(widget_key)
    home_players=sorted(home_players,key=lambda p:p.get("p") or 0,reverse=True)
    away_players=sorted(away_players,key=lambda p:p.get("p") or 0,reverse=True)
    team_heading(home_name,home_logo)
    show_players(home_players[:limit],period_label)
    team_heading(away_name,away_logo,away=True)
    show_players(away_players[:limit],period_label)


@st.cache_data(ttl=3600,show_spinner=False)
def football_players(league_id,year,team_id,key):
    if not team_id: return []
    result={}
    for page in range(1,16):
        rows=api("players",{"league":league_id,"season":year,"team":team_id,"page":page},key=key)
        if rows is None: return None if page==1 else list(result.values())
        for entry in rows:
            player=entry.get("player") or {}
            for stats in entry.get("statistics") or []:
                team=stats.get("team") or {}
                if team.get("id")!=team_id: continue
                games=stats.get("games") or {}; goals=stats.get("goals") or {}; shots=stats.get("shots") or {}
                apps=games.get("appearences") or 0
                if not apps: continue
                total_goals=goals.get("total") or 0; total_minutes=games.get("minutes")
                avg_minutes=total_minutes/apps if isinstance(total_minutes,(int,float)) and total_minutes>0 else None
                ident=player.get("id") or player.get("name")
                result[ident]={"name":player.get("name") or "Unbekannt","team":team.get("name") or "","goals":total_goals,"games":apps,"shots":shots.get("total"),"minutes":avg_minutes,"p":probability(total_goals,apps,avg_minutes),"half":probability(total_goals,apps,avg_minutes,period=0.45)}
        if len(rows)<20: break
    return list(result.values())


def football_view(day,league):
    year=season(day,league)
    fixtures=fixtures_for("football",day,league)
    if fixtures is None: fixtures=api("fixtures",{"league":LEAGUES[league],"season":year,"date":day.isoformat(),"timezone":"Europe/Berlin"},key=secret("API_SPORTS_KEY"))
    if fixtures is None: st.warning("Fußball-Spielplan nicht verfügbar."); return
    if not fixtures: st.info("Keine Begegnungen an diesem Tag."); return
    st.caption(f"Saison {year}" if league=="MLS" else f"Saison {year}/{str(year+1)[-2:]}")
    fixtures=sorted(fixtures,key=lambda m:(m.get("fixture") or {}).get("timestamp") or 0)
    for match in fixtures:
        fixture=match.get("fixture") or {}; teams=match.get("teams") or {}; home=teams.get("home") or {}; away=teams.get("away") or {}
        try: time=datetime.fromtimestamp(fixture["timestamp"],TZ).strftime("%H:%M")
        except (KeyError,TypeError,ValueError,OverflowError): time="–"
        title=f'⚽ {time} Uhr · {home.get("name","?")} – {away.get("name","?")}'
        with st.expander(title,expanded=True):
            match_heading(home.get("name","?"),home.get("logo"),away.get("name","?"),away.get("logo"))
            st.caption("1. Halbzeit: angenommene 45 % der Torintensität. Statistische Schätzung.")
            key=secret("API_SPORTS_KEY")
            if not key: st.info("API_SPORTS_KEY in Streamlit Secrets eintragen."); continue
            with st.spinner("Spielerstatistiken laden …"):
                hp=football_players(LEAGUES[league],year,home.get("id"),key)
                ap=football_players(LEAGUES[league],year,away.get("id"),key)
            if hp is None or ap is None: st.warning("Spielerstatistiken nicht vollständig verfügbar."); continue
            show_match_teams(home.get("name","Heim"),home.get("logo"),hp,away.get("name","Gast"),away.get("logo"),ap,"1. Halbzeit",f'football_{league}_{day}_{fixture.get("id",home.get("id"))}')


@st.cache_data(ttl=3600,show_spinner=False)
def nhl_skaters(abbrev):
    payload=nhl(f"club-stats/{abbrev}/now")
    if not isinstance(payload,dict): return None
    result=[]
    for item in payload.get("skaters") or []:
        games=item.get("gamesPlayed") or 0
        if not games: continue
        goals=item.get("goals") or 0; first=item.get("firstName") or {}; last=item.get("lastName") or {}
        if isinstance(first,dict): first=first.get("default","")
        if isinstance(last,dict): last=last.get("default","")
        result.append({"name":f"{first} {last}".strip() or "Unbekannt","team":abbrev,"goals":goals,"games":games,"shots":item.get("shots"),"minutes":None,"p":probability(goals,games,prior=0.18),"half":probability(goals,games,period=1/3,prior=0.18)})
    return result


def nhl_team_name(team):
    name=team.get("name") or team.get("commonName") or team.get("placeName")
    if isinstance(name,dict): name=name.get("default") or name.get("de")
    return str(name or team.get("abbrev") or "Team")


def nhl_view(day):
    schedule=fixtures_for("nhl",day)
    if schedule is None: schedule=nhl("score/"+day.isoformat())
    if not isinstance(schedule,dict): st.warning("NHL-Spielplan nicht verfügbar."); return
    games=schedule.get("games") or []
    if not games: st.info("Keine NHL-Spiele an diesem Tag."); return
    for game in games:
        home=game.get("homeTeam") or {}; away=game.get("awayTeam") or {}
        try: time=datetime.fromisoformat(game.get("startTimeUTC","").replace("Z","+00:00")).astimezone(TZ).strftime("%H:%M")
        except (ValueError,TypeError): time="–"
        home_name=nhl_team_name(home); away_name=nhl_team_name(away)
        with st.expander(f'🏒 {time} Uhr · {away_name} @ {home_name}',expanded=True):
            match_heading(home_name,home.get("logo"),away_name,away.get("logo"))
            st.caption("1. Drittel: angenommene gleichmäßige Torintensität über drei Drittel.")
            hp=nhl_skaters(home.get("abbrev")) if home.get("abbrev") else None
            ap=nhl_skaters(away.get("abbrev")) if away.get("abbrev") else None
            if hp is None or ap is None: st.warning("NHL-Spielerstatistiken nicht vollständig verfügbar."); continue
            show_match_teams(home_name,home.get("logo"),hp,away_name,away.get("logo"),ap,"1. Drittel",f'nhl_{day}_{game.get("id",str(home.get("abbrev"))+str(away.get("abbrev")))}')


def safe_int(value):
    try:
        number=int(value)
        return number if number>=0 else None
    except (TypeError,ValueError,OverflowError): return None


def normalize_team(value):
    text=str(value or "").casefold().replace("ä","ae").replace("ö","oe").replace("ü","ue").replace("ß","ss")
    text=unicodedata.normalize("NFKD",text)
    text="".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+","",text)


def del_team_mapping():
    names=daily_snapshot().get("del_team_names",{})
    if not isinstance(names,dict): names={}
    candidates={}
    for team_id,fallback in DEL_TEAMS.items():
        for name in [fallback,names.get(team_id,"")]+DEL_ALIASES.get(team_id,[]):
            norm=normalize_team(name)
            if norm: candidates.setdefault(norm,set()).add(team_id)
    return {name:next(iter(ids)) for name,ids in candidates.items() if len(ids)==1}


def del_player_estimates():
    snap=daily_snapshot(); raw=snap.get("del_player_stats",[]); names=snap.get("del_team_names",{})
    if not isinstance(raw,list): return []
    if not isinstance(names,dict): names={}
    players=[]
    for item in raw:
        if not isinstance(item,dict): continue
        name=str(item.get("name") or "").strip(); team_id=str(item.get("team_id") or "").strip()
        games=safe_int(item.get("games")); goals=safe_int(item.get("goals"))
        if not name or not team_id or not games or goals is None: continue
        team_name=names.get(team_id) or item.get("team") or DEL_TEAMS.get(team_id) or team_id
        players.append({"name":name,"team":team_name,"team_id":team_id,"games":games,"goals":goals,"shots":None,"minutes":None,"p":probability(goals,games,prior=0.18),"half":probability(goals,games,period=1/3,prior=0.18)})
    return sorted(players,key=lambda p:p.get("p") or 0,reverse=True)


def del_game_time(match):
    timestamp=match.get("timestamp")
    if isinstance(timestamp,(int,float)):
        try: return datetime.fromtimestamp(timestamp,TZ).strftime("%H:%M")
        except (ValueError,OverflowError,OSError): pass
    date_text=match.get("date")
    if isinstance(date_text,str):
        try: return datetime.fromisoformat(date_text.replace("Z","+00:00")).astimezone(TZ).strftime("%H:%M")
        except ValueError: pass
    return None


def del_view(day):
    rows=fixtures_for("del",day)
    if rows is None: rows=api("games",{"league":secret("DEL_LEAGUE_ID") or "19","season":season(day,"DEL"),"date":day.isoformat(),"timezone":"Europe/Berlin"},provider="hockey",key=secret("API_SPORTS_KEY"))
    if rows is None: st.warning("DEL-Spielplan derzeit nicht verfügbar."); return
    players=del_player_estimates(); mapping=del_team_mapping()
    if not players: st.warning("Keine DEL-Spielerstatistiken gefunden. GitHub-Tagesupdate prüfen."); return
    st.success(f"{len(players)} DEL-Spieler mit Saisonstatistiken verfügbar.")
    st.caption("Geschätzte Wahrscheinlichkeit für mindestens ein Tor. 1. Drittel: ein Drittel der geschätzten Torintensität.")
    if not rows: st.info("Keine DEL-Spiele an diesem Tag.")
    for match in rows:
        teams=match.get("teams") or {}; home=teams.get("home") or {}; away=teams.get("away") or {}
        home_name=str(home.get("name") or "Heimteam"); away_name=str(away.get("name") or "Auswärtsteam")
        home_id=mapping.get(normalize_team(home_name)); away_id=mapping.get(normalize_team(away_name))
        time=del_game_time(match); time_label=f"{time} Uhr · " if time else ""
        with st.expander(f"🏒 {time_label}{home_name} – {away_name}",expanded=True):
            match_heading(home_name,home.get("logo"),away_name,away.get("logo"))
            if not home_id or not away_id or home_id==away_id:
                st.warning("Mindestens eine Mannschaft konnte nicht eindeutig zugeordnet werden. Keine unsicheren Spielerzuordnungen.")
                st.caption(f"Heim: {home_name} → {home_id or 'unbekannt'} | Auswärts: {away_name} → {away_id or 'unbekannt'}")
                continue
            hp=[p for p in players if p["team_id"]==home_id]
            ap=[p for p in players if p["team_id"]==away_id]
            st.caption(f"{len(hp)+len(ap)} Spieler mit absolvierten Saisonspielen für diese Begegnung")
            show_match_teams(DEL_TEAMS.get(home_id,home_name),home.get("logo"),hp,DEL_TEAMS.get(away_id,away_name),away.get("logo"),ap,"1. Drittel",f'del_{day}_{match.get("id",home_id+"_"+away_id)}')
    st.divider()
    with st.expander("📊 Alle DEL-Spieler und Mannschaften"):
        choices={"Alle Spieler":None}
        for team_id in sorted({p["team_id"] for p in players}): choices[f"{DEL_TEAMS.get(team_id,team_id)} ({team_id})"]=team_id
        selected=st.selectbox("Mannschaft",list(choices)); chosen=choices[selected]
        filtered=players if chosen is None else [p for p in players if p["team_id"]==chosen]
        show_players(filtered[:30],"1. Drittel")
    with st.expander("🔎 DEL-Teamzuordnung prüfen"):
        st.dataframe(pd.DataFrame([{"Kennung":tid,"Mannschaft":name,"Spieler mit Saisonspielen":sum(p["team_id"]==tid for p in players)} for tid,name in DEL_TEAMS.items()]),hide_index=True,use_container_width=True)


st.title("🎯 SportRadar – Torschützen heute & morgen")
st.caption("Deutsche Zeit · Saison automatisch · Poisson-Modell mit Stichproben-Glättung")
sport=st.radio("Sportart",["🏒 Eishockey","⚽ Fußball"],horizontal=True)
leagues=["NHL","DEL"] if sport.startswith("🏒") else list(LEAGUES)
league=st.selectbox("Liga",leagues)
day_choice=st.radio("Spieltag",["Heute","Morgen"],horizontal=True)
day=datetime.now(TZ).date()+timedelta(days=int(day_choice=="Morgen"))
st.caption(day.strftime("%d.%m.%Y"))
snapshot=daily_snapshot()
if snapshot.get("updated_at"):
    try:
        updated=datetime.fromisoformat(snapshot["updated_at"]).astimezone(TZ)
        st.caption("🕗 Letzte gespeicherte Aktualisierung: "+updated.strftime("%d.%m.%Y %H:%M")+" Uhr")
    except ValueError: st.caption("🕗 Gespeicherter Datenstand vorhanden")
else: st.caption("🕗 Noch kein täglicher Snapshot vorhanden")
if st.button("🔄 Daten neu laden"):
    st.cache_data.clear(); st.rerun()
if sport.startswith("🏒"):
    if league=="NHL": nhl_view(day)
    else: del_view(day)
else: football_view(day,league)
st.divider()
st.caption("Alle Prozentwerte sind Modellschätzungen, keine Garantien oder Wettquoten. Aufstellung, Verletzungen, Gegnerstärke, Eiszeit und kleine Stichproben sind nicht vollständig berücksichtigt.")
