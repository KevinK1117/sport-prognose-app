


"""SportRadar – football, NHL and DEL goalscorer estimates."""
import html
import base64
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
/* SportRadar: subtle, mobile-friendly color accents */
:root{--sr-navy:#17324b;--sr-teal:#087e80;--sr-coral:#e56854;--sr-pale:#eaf5f4}
[data-testid="stAppViewContainer"]{background:linear-gradient(180deg,#f0f7fa 0px,#ffffff 320px)}
.block-container>div:first-child h1{color:var(--sr-navy);letter-spacing:-.025em}
[data-testid="stExpander"]{border:1px solid #d9e6ec!important;border-radius:17px!important;background:#fff;overflow:hidden;box-shadow:0 3px 12px rgba(23,50,75,.045)}
[data-testid="stExpander"] summary{background:#f2f7fa}
[data-testid="stExpander"] summary:hover{background:#e9f3f7}
.stButton>button{border-radius:11px;border-color:#9bc8c9;color:#075c62;font-weight:600}
.stButton>button:hover{border-color:var(--sr-teal);color:var(--sr-teal)}
[data-testid="stAlert"]{border-radius:13px}
[data-testid="stTabs"] [data-baseweb="tab-highlight"]{background-color:var(--sr-teal)}
[data-testid="stTabs"] button[aria-selected="true"]{color:var(--sr-teal)}
.block-container{max-width:1050px;padding-top:1.2rem}
.player{background:linear-gradient(135deg,#fff 0%,#f6fafc 100%);border:1px solid #d8e6ed;border-left:4px solid #087e80;border-radius:18px;padding:15px;margin:10px 0;color:#263747;box-shadow:0 2px 8px rgba(23,50,75,.035)}
.player.sr-high{border-left-color:#18855b}
.player.sr-mid{border-left-color:#e69a36}
.player.sr-low{border-left-color:#98a4b1}
.player.sr-high .prob{background:#e5f5eb}
.player.sr-high .prob strong{color:#146b49}
.player.sr-mid .prob{background:#fff1dc}
.player.sr-mid .prob strong{color:#9a5b10}
.player.sr-low .prob{background:#edf1f5}
.player.sr-low .prob strong{color:#536274}
.sr-risk-key{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 14px}
.sr-risk-key span{font-size:.8rem;border-radius:999px;padding:5px 9px;background:#f3f5f7;color:#344357}
.sr-risk-key .sr-dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px}
.player-head{font-weight:700;font-size:1.08rem;color:#17324b}.muted{color:#777b85;font-size:.88rem}
.pair{display:flex;gap:10px;margin-top:12px}.prob{flex:1;background:#eaf5f4;border-radius:12px;padding:12px 9px;text-align:center}
.prob strong{display:block;font-size:1.4rem;color:#075f66}.prob small{color:#646a77}
.pill{display:inline-block;background:#e9f0f5;border-radius:10px;padding:5px 9px;margin:9px 5px 0 0;font-size:.83rem}
.sr-match{display:grid;grid-template-columns:minmax(0,1fr) 20px minmax(0,1fr);align-items:center;gap:6px;margin:5px 0 15px;padding:14px 7px;border-radius:14px;background:linear-gradient(100deg,#edf6fa,#f5faf9)}
.sr-match-team{display:flex;flex-direction:column;align-items:center;justify-content:center;min-width:0;gap:8px;text-align:center}
.sr-match-logo{width:58px;height:58px;display:flex;align-items:center;justify-content:center}
.sr-match-name{font-size:clamp(.83rem,2.8vw,1.04rem);color:#17324b;font-weight:700;line-height:1.3;overflow-wrap:anywhere}
.sr-versus{text-align:center;font-size:1.3rem;font-weight:700;color:#e56854}
.sr-team-heading{display:flex;align-items:center;gap:10px;margin:20px 0 9px;font-size:1.15rem;font-weight:700;line-height:1.3;color:#17324b}
.sr-small-logo{width:36px;height:36px;flex:none;display:flex;align-items:center;justify-content:center}
.team-logo-fallback{font-size:1.7rem}
@media(max-width:480px){.sr-match-logo{width:49px;height:49px}.sr-match{gap:4px;padding:7px 0}.sr-team-heading{font-size:1.02rem}}
</style>""", unsafe_allow_html=True)
TZ = ZoneInfo("Europe/Berlin")
LEAGUES = {"Bundesliga":78,"2. Bundesliga":79,"La Liga":140,"Serie A":135,"Premier League":39,"Ligue 1":61,"MLS":253}
DEL_TEAMS = {"team_1":"ERC Ingolstadt","team_2":"Adler Mannheim","team_3":"Eisbären Berlin","team_5":"Krefeld Pinguine","team_6":"Straubing Tigers","team_7":"Iserlohn Roosters","team_8":"Grizzlys Wolfsburg","team_9":"Pinguins Bremerhaven","team_11":"Kölner Haie","team_12":"EHC Red Bull München","team_13":"Augsburger Panther","team_14":"Nürnberg Ice Tigers","team_15":"Schwenninger Wild Wings","team_44":"Löwen Frankfurt"}
DEL_ALIASES = {"team_1":["Ingolstadt"],"team_2":["Mannheim"],"team_3":["Berlin","Eisbaeren Berlin"],"team_5":["Krefeld"],"team_6":["Straubing"],"team_7":["Iserlohn"],"team_8":["Wolfsburg"],"team_9":["Bremerhaven","Fischtown Pinguins","Fischtown Pinguins Bremerhaven"],"team_11":["Köln","Koeln","Kolner Haie"],"team_12":["München","Muenchen","Red Bull München","EHC München"],"team_13":["Augsburg"],"team_14":["Nürnberg","Nuernberg","Nuremberg Ice Tigers"],"team_15":["Schwenningen"],"team_44":["Frankfurt","Loewen Frankfurt","Frankfurt Lowen","Frankfurt Loewen","Frankfurt Löwen"]}


st.markdown("""<style>.sr-form{margin-top:12px;padding:11px 13px;border-radius:12px;background:rgba(18,120,120,.075);font-size:.89rem;line-height:1.7}.sr-form b{color:#147f7f}.sr-form small{color:#64748b}.sr-grade{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;border-radius:14px;padding:13px 15px;margin-top:10px;font-weight:700;border:1px solid rgba(0,0,0,.035)}.sr-grade-label{font-size:.78rem;line-height:1.35;max-width:60%}.sr-grade-score{font-size:clamp(1.8rem,6vw,2.35rem);font-weight:850;line-height:1;letter-spacing:-.035em;font-variant-numeric:tabular-nums}.sr-grade-denom{font-size:.85rem;font-weight:600;opacity:.7}.sr-grade-meta{font-size:.77rem;opacity:.85;font-weight:600;width:100%}.sr-grade-high{background:#e5f5eb;color:#146b49}.sr-grade-mid{background:#fff1dc;color:#9a5b10}.sr-grade-low{background:#fce8e8;color:#a13a3a}.sr-grade-none{background:#edf1f5;color:#536274}</style>""",unsafe_allow_html=True)

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


def probability_tier(value, sport):
    """Presentation-only tiers, based on the full-game estimate."""
    if value is None:
        return "low"
    high, medium = (30, 15) if sport == "football" else (25, 10)
    if value >= high:
        return "high"
    if value >= medium:
        return "mid"
    return "low"


def show_probability_legend(sport):
    high, medium = (30, 15) if sport == "football" else (25, 10)
    st.markdown(
        '<div class="sr-risk-key">'
        f'<span><i class="sr-dot" style="background:#98a4b1"></i>Unter {medium} %</span>'
        f'<span><i class="sr-dot" style="background:#e69a36"></i>{medium}–{high-0.1:.1f} %</span>'
        f'<span><i class="sr-dot" style="background:#18855b"></i>Ab {high} %</span>'
        '</div>', unsafe_allow_html=True
    )


@st.cache_data(ttl=300,show_spinner=False)
def del_form_snapshot():
    path=Path(__file__).resolve().parent/'data'/'del_form_stats.json'
    try:
        obj=json.loads(path.read_text(encoding='utf-8'))
        return obj.get('players',{}) if isinstance(obj,dict) else {}
    except (OSError,ValueError): return {}


def del_recent_form(player,day):
    key=normalize_team(player.get('name',''))
    info=del_form_snapshot().get(key,{})
    recent=[g for g in info.get('games',[]) if g.get('date','')<day.isoformat()][:5]
    if len(recent)<3: return None
    return {'played':len(recent),'goals':sum(g['goals'] for g in recent),
            'shots':sum(g['shots'] for g in recent),
            'minutes':sum(g['minutes'] for g in recent),
            'assists':sum(g.get('assists') or 0 for g in recent)}


def player_form_details(player, sport, day):
    """Verified last-five-game form; return None if unsupported/unavailable."""
    if sport == "football":
        key = secret("API_SPORTS_KEY")
        if not key or not player.get("team_id") or not player.get("player_id"):
            return None
        records = football_recent_form(player["team_id"], day, key)
        return records.get(player["player_id"]) if isinstance(records, dict) else None
    if sport == "nhl":
        return nhl_recent_form(player.get("player_id"), day)
    if sport == "del":
        return del_recent_form(player,day)
    return None


def grade_badge(label, value, sample, *, official=False):
    """Prominent, accessible form rating; separate from goal probabilities."""
    safe_label = html.escape(str(label))
    if value is None:
        return f'<div class="sr-grade sr-grade-none"><span class="sr-grade-label">{safe_label}</span><span>Keine Bewertung verfügbar</span></div>'
    if official:
        tier = "high" if value >= 7.5 else "mid" if value >= 6.5 else "low"
        status = "Starke Form" if tier == "high" else "Solide Form" if tier == "mid" else "Schwächere Form"
    else:
        tier = "high" if value >= 8.5 else "mid" if value >= 7.0 else "low"
        status = "Topform" if tier == "high" else "Gute Form" if tier == "mid" else "Schwächere Form"
    score = f"{value:.1f}".replace(".", ",")
    return (f'<div class="sr-grade sr-grade-{tier}">'
            f'<span class="sr-grade-label">🔥 {safe_label}</span>'
            f'<span class="sr-grade-score">{score}<span class="sr-grade-denom"> / 10</span></span>'
            f'<span class="sr-grade-meta">{status} · {sample} bewertete Einsätze</span>'
            '</div>')


def nhl_own_form_grade(stats):
    """Own descriptive 0–10 index, NOT an NHL/Flashscore/Sofascore match rating."""
    if not stats or stats.get("played",0)<3: return None
    n=stats["played"]
    avg_toi=stats.get("minutes",0)/n
    if avg_toi <= 0: return None
    goals=stats.get("goals",0)/n
    shots=stats.get("shots",0)/n
    # Bounded, heuristic display index, explicitly not a bookmaker probability.
    return round(min(10.0,max(0.0, 2.0+goals*4.0+shots*.55+min(avg_toi,25)*.12)),1)


def show_player(player,period_label,sport="hockey",form_stats=None,show_form=False):
    tier=probability_tier(player.get("p"),sport)
    name=html.escape(str(player["name"])); team=html.escape(str(player["team"]))
    pills=[f'Position: {player.get("position") or "Unbekannt"}',f'{player["goals"]} Tore',f'{player["games"]} Spiele']
    if player.get("shots") is not None: pills.append(f'{player["shots"]} Schüsse')
    if player.get("minutes") is not None: pills.append(f'{player["minutes"]:.0f} Min Ø')
    chips="".join('<span class="pill">'+html.escape(str(item))+"</span>" for item in pills)
    if show_form:
        if form_stats and form_stats.get("played",0)>=3:
            n=form_stats["played"]
            avg=form_stats.get("minutes",0)/n
            time_label="Ø Eiszeit" if sport=="nhl" else "Ø Spielzeit"
            detail=(f'Letzte {n} Einsätze · {form_stats.get("goals",0)} Tore · '
                    f'{form_stats.get("shots",0)} Schüsse · {time_label} {avg:.1f} Min')
            score=form_score(form_stats,"football" if sport=="football" else "nhl")
            if sport=="football":
                count=form_stats.get("rating_count",0)
                rating=(form_stats.get("rating_sum",0)/count) if count else None
                grade=grade_badge("API-Football Ø-Bewertung",rating,count,official=True)
            elif sport in ("nhl","del"):
                grade=grade_badge("SportRadar-Formindex (eigene Berechnung)",nhl_own_form_grade(form_stats),n)
            else:
                grade=grade_badge("Formbewertung",None,0)
            form_html=f'<div class="sr-form"><b>🔥 Aktuelle Form</b><div>{html.escape(detail)}</div>{grade}<div><small>Formwert: {score:.2f} (kein Prozentwert) · Nur vorhandene Spiele zählen</small></div></div>' 
        else:
            form_html='<div class="sr-form"><b>🔥 Aktuelle Form</b><div>Letzte 5 Einsätze: verlässliche Einzelspieldaten nicht verfügbar</div></div>'
    else:
        form_html=''
    st.markdown(f'''<div class="player sr-{tier}"><div class="player-head">{name}</div><div class="muted">{team}</div><div class="pair"><div class="prob"><small>{html.escape(period_label)}</small><strong>{pct(player.get("half"))}</strong></div><div class="prob"><small>Gesamtspiel</small><strong>{pct(player.get("p"))}</strong></div></div><div>{chips}</div>{form_html}</div>''',unsafe_allow_html=True)


def show_players(players,period_label,sport="hockey"):
    if not players:
        st.info("Keine verlässlichen Spielerstatistiken verfügbar."); return
    tab1,tab2=st.tabs(["🎯 Spielerprognosen","📊 Tabelle"])
    with tab1:
        for p in players:
            stats=player_form_details(p,sport,day)
            show_player(p,period_label,sport,stats,True)
            favorite_button(p,f"card_{sport}_{p.get('team')}_{p.get('name')}")
    with tab2:
        table=[]
        for p in players:
            minutes=p.get("minutes")
            table.append({"Spieler":p["name"],"Team":p["team"],"Position":p.get("position"),period_label:pct(p.get("half")),"Gesamtspiel":pct(p.get("p")),"Tore":p["goals"],"Spiele":p["games"],"Schüsse":p.get("shots"),"Min Ø":round(minutes,1) if minutes is not None else None})
        st.dataframe(pd.DataFrame(table),hide_index=True,use_container_width=True)


def selection_limit(key):
    choice=st.radio("Spieler pro Mannschaft anzeigen",["Top 5","Top 10","Alle"],horizontal=True,key=key)
    return {"Top 5":5,"Top 10":10,"Alle":None}[choice]


def show_match_teams(home_name,home_logo,home_players,away_name,away_logo,away_players,period_label,widget_key,sport="hockey"):
    """Same layout across all sports; top N for EACH team."""
    limit=selection_limit(widget_key)
    show_probability_legend(sport)
    home_players=sorted(home_players,key=lambda p:p.get("p") or 0,reverse=True)
    away_players=sorted(away_players,key=lambda p:p.get("p") or 0,reverse=True)
    team_heading(home_name,home_logo)
    show_players(home_players[:limit],period_label,sport)
    team_heading(away_name,away_logo,away=True)
    show_players(away_players[:limit],period_label,sport)


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
                result[ident]={"name":player.get("name") or "Unbekannt","player_id":player.get("id"),"team_id":team_id,"team":team.get("name") or "","position":games.get("position") or "Unbekannt","goals":total_goals,"games":apps,"shots":shots.get("total"),"minutes":avg_minutes,"p":probability(total_goals,apps,avg_minutes),"half":probability(total_goals,apps,avg_minutes,period=0.45)}
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
            display_football_lineup(fixture.get("id"),home.get("name"),away.get("name"),key,home.get("id"),away.get("id"),day)
            show_match_teams(home.get("name","Heim"),home.get("logo"),hp,away.get("name","Gast"),away.get("logo"),ap,"1. Halbzeit",f'football_{league}_{day}_{fixture.get("id",home.get("id"))}',sport="football")


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
        result.append({"name":f"{first} {last}".strip() or "Unbekannt","player_id":item.get("playerId") or item.get("id"),"team":abbrev,"position":item.get("positionCode") or item.get("position") or "Unbekannt","goals":goals,"games":games,"shots":item.get("shots"),"minutes":None,"p":probability(goals,games,prior=0.18),"half":probability(goals,games,period=1/3,prior=0.18)})
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
        with st.expander(f'🏒 {time} Uhr · {home_name} – {away_name}',expanded=True):
            match_heading(home_name,home.get("logo"),away_name,away.get("logo"))
            st.caption("1. Drittel: angenommene gleichmäßige Torintensität über drei Drittel.")
            hp=nhl_skaters(home.get("abbrev")) if home.get("abbrev") else None
            ap=nhl_skaters(away.get("abbrev")) if away.get("abbrev") else None
            if hp is None or ap is None: st.warning("NHL-Spielerstatistiken nicht vollständig verfügbar."); continue
            show_match_teams(home_name,home.get("logo"),hp,away_name,away.get("logo"),ap,"1. Drittel",f'nhl_{day}_{game.get("id",str(home.get("abbrev"))+str(away.get("abbrev")))}',sport="nhl")


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
        players.append({"name":name,"team":team_name,"team_id":team_id,"position":item.get("position") or "Unbekannt","games":games,"goals":goals,"shots":None,"minutes":None,"p":probability(goals,games,prior=0.18),"half":probability(goals,games,period=1/3,prior=0.18)})
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
            show_match_teams(DEL_TEAMS.get(home_id,home_name),home.get("logo"),hp,DEL_TEAMS.get(away_id,away_name),away.get("logo"),ap,"1. Drittel",f'del_{day}_{match.get("id",home_id+"_"+away_id)}',sport="del")
    st.divider()
    with st.expander("📊 Alle DEL-Spieler und Mannschaften"):
        choices={"Alle Spieler":None}
        for team_id in sorted({p["team_id"] for p in players}): choices[f"{DEL_TEAMS.get(team_id,team_id)} ({team_id})"]=team_id
        selected=st.selectbox("Mannschaft",list(choices)); chosen=choices[selected]
        filtered=players if chosen is None else [p for p in players if p["team_id"]==chosen]
        show_players(filtered[:30],"1. Drittel",sport="del")
    with st.expander("🔎 DEL-Teamzuordnung prüfen"):
        st.dataframe(pd.DataFrame([{"Kennung":tid,"Mannschaft":name,"Spieler mit Saisonspielen":sum(p["team_id"]==tid for p in players)} for tid,name in DEL_TEAMS.items()]),hide_index=True,use_container_width=True)


def kickoff_info(game, league):
    """Return Berlin-local future kickoff or None if started, final, or unknown."""
    now=datetime.now(TZ)
    try:
        if league=="NHL":
            status=str(game.get("gameState") or "").upper()
            if status in ("LIVE","CRIT","FINAL","OFF"): return None
            raw=game.get("startTimeUTC")
            kickoff=datetime.fromisoformat(raw.replace("Z","+00:00")).astimezone(TZ)
        elif league=="DEL":
            status=str((game.get("status") or {}).get("short") if isinstance(game.get("status"),dict) else game.get("status") or "").upper()
            if status in ("LIVE","FT","AOT","AP","FINISHED","FINAL","1P","2P","3P","OT","PEN"): return None
            raw=game.get("date")
            if isinstance(game.get("timestamp"),(int,float)):
                kickoff=datetime.fromtimestamp(game["timestamp"],TZ)
            else:
                kickoff=datetime.fromisoformat(raw.replace("Z","+00:00")).astimezone(TZ)
        else:
            fixture=game.get("fixture") or {}
            status=str((fixture.get("status") or {}).get("short") or "").upper()
            if status not in ("NS","TBD"): return None
            if fixture.get("timestamp"):
                kickoff=datetime.fromtimestamp(fixture["timestamp"],TZ)
            else:
                kickoff=datetime.fromisoformat(fixture["date"].replace("Z","+00:00")).astimezone(TZ)
        if kickoff<=now: return None
        return kickoff
    except (ValueError,TypeError,KeyError,OverflowError,AttributeError,OSError):
        return None


def github_favorites_config():
    token=secret("GH_FAVORITES_TOKEN")
    repo=secret("GH_FAVORITES_REPO") or "KevinK1117/sport-prognose-app"
    return token,repo


def load_persistent_favorites():
    token,repo=github_favorites_config()
    if not token: return None
    try:
        response=requests.get(f"https://api.github.com/repos/{repo}/contents/data/favorites.json",
            headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json"},timeout=15)
        if response.status_code==404: return {},None
        response.raise_for_status()
        data=response.json()
        content=json.loads(base64.b64decode(data["content"]).decode("utf-8"))
        return (content if isinstance(content,dict) else {}),data.get("sha")
    except (requests.RequestException,ValueError,KeyError,UnicodeDecodeError):
        return None


def save_persistent_favorites(favorites,sha):
    token,repo=github_favorites_config()
    if not token: return False
    body={"message":"Update SportRadar favorites","content":base64.b64encode(
        json.dumps(favorites,ensure_ascii=False,indent=2).encode("utf-8")).decode("ascii")}
    if sha: body["sha"]=sha
    try:
        response=requests.put(f"https://api.github.com/repos/{repo}/contents/data/favorites.json",
            headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json"},json=body,timeout=20)
        response.raise_for_status()
        return True
    except requests.RequestException: return False


def current_favorites():
    if "sr_favorites" not in st.session_state:
        stored=load_persistent_favorites()
        st.session_state["sr_favorites"]=stored[0] if stored is not None else {}
        st.session_state["sr_favorites_sha"]=stored[1] if stored is not None else None
    return st.session_state["sr_favorites"]


def update_favorites(favorites):
    if secret("GH_FAVORITES_TOKEN"):
        # Reload SHA to avoid overwriting a stale revision.
        stored=load_persistent_favorites()
        if stored is None or not save_persistent_favorites(favorites,stored[1]):
            st.error("Favorit konnte nicht dauerhaft auf GitHub gespeichert werden. Token und Berechtigungen prüfen.")
            return False
    st.session_state["sr_favorites"]=favorites
    return True


def favorite_key(player):
    league=player.get("league") or player.get("sport","")
    return f"{league}:{player.get('player_id') or player.get('team','')}:{player.get('name','')}"


def favorite_button(player, prefix):
    favorites=current_favorites()
    key=favorite_key(player)
    label="⭐ Favorisiert" if key in favorites else "☆ Favorisieren"
    if st.button(label,key=f"fav_{prefix}_{abs(hash(key))}"):
        new=dict(favorites)
        if key in new: del new[key]
        else:
            league=player.get("league") or player.get("sport")
            if league in ("hockey", "nhl") and player.get("player_id"): league="NHL"
            new[key]={"name":player.get("name"),"team":player.get("team"),
                      "league":league,"player_id":player.get("player_id"),"team_id":player.get("team_id")}
        if update_favorites(new): st.rerun()


@st.cache_data(ttl=300,show_spinner=False)
def football_confirmed_lineup(fixture_id,key):
    if not fixture_id or not key: return None
    rows=api("fixtures/lineups",{"fixture":fixture_id},key=key)
    return rows if isinstance(rows,list) and rows else None


@st.cache_data(ttl=7200,show_spinner=False)
def football_expected_lineup(team_id,day,key):
    """Estimate an XI from real recent confirmed lineups; not a confirmed lineup."""
    if not team_id or not key: return None
    ids=football_recent_fixture_ids(team_id,day,key)
    appearances={}; samples=0; formations={}
    for fixture_id in ids:
        rows=football_confirmed_lineup(fixture_id,key)
        if not rows: continue
        team=next((r for r in rows if (r.get("team") or {}).get("id")==team_id),None)
        if not team or not team.get("startXI"): continue
        samples+=1
        formation=team.get("formation")
        if formation: formations[formation]=formations.get(formation,0)+1
        for item in team["startXI"]:
            player=item.get("player") or {}
            ident=player.get("id") or player.get("name")
            if not ident: continue
            entry=appearances.setdefault(str(ident),{"name":player.get("name") or "?","pos":player.get("pos") or "?","starts":0})
            entry["starts"]+=1
    if samples<2: return None
    positions={"G":0,"D":1,"M":2,"F":3}
    # One goalkeeper and ten outfield players, selected by recent starting frequency.
    ranked=sorted(appearances.values(),key=lambda x:(-x["starts"],x["name"]))
    keepers=[p for p in ranked if p["pos"]=="G"]
    others=[p for p in ranked if p["pos"]!="G"]
    chosen=(keepers[:1]+others[:10]) if keepers else ranked[:11]
    chosen.sort(key=lambda x:(positions.get(x["pos"],4),-x["starts"],x["name"]))
    formation=max(formations,key=formations.get) if formations else None
    return {"players":chosen,"samples":samples,"formation":formation}


def display_football_lineup(fixture_id,home_name,away_name,key,home_id=None,away_id=None,day=None):
    with st.expander("👥 Voraussichtliche / bestätigte Aufstellung",expanded=False):
        rows=football_confirmed_lineup(fixture_id,key)
        confirmed={str((r.get("team") or {}).get("id")):r for r in (rows or [])}
        for team_name,team_id in ((home_name,home_id),(away_name,away_id)):
            st.markdown(f"**{team_name}**")
            team=confirmed.get(str(team_id))
            if team and team.get("startXI"):
                st.success("✅ Bestätigte Startelf vom Datenanbieter")
                st.caption("Formation: "+str(team.get("formation") or "unbekannt"))
                for section,label in (("startXI","Startelf"),("substitutes","Ersatzbank")):
                    names=[f"{(x.get('player') or {}).get('name','?')} ({(x.get('player') or {}).get('pos') or '?'})" for x in team.get(section) or []]
                    st.write(f"{label}: "+(", ".join(names) if names else "Keine Angaben"))
            else:
                st.info("⏳ Noch keine bestätigte Aufstellung. Voraussichtliche Startelf aus den letzten verfügbaren bestätigten Aufstellungen:")
                if not team_id or day is None:
                    st.caption("Keine Teamkennung verfügbar.")
                    continue
                # Lazy fetch: prevent many extra API requests on every page load.
                if st.button(f"🔎 Voraussichtliche Elf für {team_name} anzeigen",key=f"expected_{fixture_id}_{team_id}"):
                    st.session_state[f"expected_show_{fixture_id}_{team_id}"]=True
                if st.session_state.get(f"expected_show_{fixture_id}_{team_id}"):
                    with st.spinner("Letzte bestätigte Startelf-Einsätze auswerten …"):
                        expected=football_expected_lineup(team_id,day,key)
                    if not expected:
                        st.warning("Zu wenige bestätigte frühere Aufstellungen für eine belastbare Prognose.")
                    else:
                        st.caption(f"Prognose aus {expected['samples']} vergangenen Startaufstellungen · Häufigste Formation: {expected['formation'] or 'unbekannt'}")
                        for player in expected["players"]:
                            st.write(f"{player['name']} · {player['pos']} · {player['starts']}/{expected['samples']} zuletzt in der Startelf")
                        st.caption("⚠️ Statistische Erwartung, keine offizielle oder journalistisch bestätigte Prognose. Verletzungen, Sperren und Rotation sind nicht berücksichtigt.")


def combo_candidates(day, sport, league):
    """Use only players from fixtures scheduled for the selected date."""
    candidates=[]
    if sport.startswith("⚽"):
        year=season(day,league)
        games=fixtures_for("football",day,league)
        if games is None:
            games=api("fixtures",{"league":LEAGUES[league],"season":year,"date":day.isoformat(),"timezone":"Europe/Berlin"},key=secret("API_SPORTS_KEY"))
        for game in (games or []):
            kickoff=kickoff_info(game,league)
            if kickoff is None: continue
            teams=game.get("teams") or {}
            home=teams.get("home") or {}; away=teams.get("away") or {}
            fixture_id=(game.get("fixture") or {}).get("id")
            for team in (home,away):
                players=football_players(LEAGUES[league],year,team.get("id"),secret("API_SPORTS_KEY")) if secret("API_SPORTS_KEY") else []
                for player in (players or []):
                    if player.get("games",0)>=3 and player.get("p") is not None:
                        candidates.append({**player,"sport":"football","league":league,"kickoff":kickoff.isoformat(),"match":f'{home.get("name","?")} – {away.get("name","?")}',"fixture":str(fixture_id or f'{home.get("id")}-{away.get("id")}')})
    elif league=="NHL":
        games=fixtures_for("nhl",day)
        if games is None: games=nhl("score/"+day.isoformat())
        for game in (games or {}).get("games",[]):
            kickoff=kickoff_info(game,"NHL")
            if kickoff is None: continue
            home=game.get("homeTeam") or {}; away=game.get("awayTeam") or {}
            for team in (home,away):
                players=nhl_skaters(team.get("abbrev")) if team.get("abbrev") else []
                for player in (players or []):
                    if player.get("games",0)>=3 and player.get("p") is not None:
                        candidates.append({**player,"sport":"hockey","league":"NHL","kickoff":kickoff.isoformat(),"match":f'{nhl_team_name(home)} – {nhl_team_name(away)}',"fixture":str(game.get("id") or f'{home.get("abbrev")}-{away.get("abbrev")}')})
    else:
        games=fixtures_for("del",day)
        if games is None: games=api("games",{"league":secret("DEL_LEAGUE_ID") or "19","season":season(day,"DEL"),"date":day.isoformat(),"timezone":"Europe/Berlin"},provider="hockey",key=secret("API_SPORTS_KEY"))
        mapping=del_team_mapping()
        players=del_player_estimates()
        for game in (games or []):
            kickoff=kickoff_info(game,"DEL")
            if kickoff is None: continue
            teams=game.get("teams") or {}
            home=teams.get("home") or {}; away=teams.get("away") or {}
            home_id=mapping.get(normalize_team(home.get("name")))
            away_id=mapping.get(normalize_team(away.get("name")))
            for player in players:
                if player.get("team_id") in (home_id,away_id) and player.get("games",0)>=3:
                    candidates.append({**player,"sport":"hockey","league":"DEL","kickoff":kickoff.isoformat(),"match":f'{home.get("name","?")} – {away.get("name","?")}',"fixture":str(game.get("id") or f'{home_id}-{away_id}')})
    return sorted(candidates,key=lambda x:x.get("p") or 0,reverse=True)


@st.cache_data(ttl=7200,show_spinner=False)
def football_recent_fixture_ids(team_id, day, key):
    """Last five completed fixtures before the chosen day, all competitions."""
    rows=api("fixtures",{"team":team_id,"last":12,"status":"FT","timezone":"Europe/Berlin"},key=key)
    if not isinstance(rows,list): return []
    found=[]
    for row in rows:
        fixture=row.get("fixture") or {}
        try:
            played=datetime.fromisoformat(str(fixture.get("date","")).replace("Z","+00:00")).date()
        except ValueError: continue
        if played<day and fixture.get("id"):
            found.append((played,fixture["id"]))
    return [fid for _,fid in sorted(found,reverse=True)[:5]]


@st.cache_data(ttl=7200,show_spinner=False)
def football_fixture_player_stats(fixture_id,key):
    return api("fixtures/players",{"fixture":fixture_id},key=key)


@st.cache_data(ttl=7200,show_spinner=False)
def football_recent_form(team_id,day,key):
    """Actual per-game goals/shots/minutes; no form if fewer than 3 game reports."""
    fixture_ids=football_recent_fixture_ids(team_id,day,key)
    if len(fixture_ids)<3: return {}
    records={}
    for fid in fixture_ids:
        data=football_fixture_player_stats(fid,key)
        if not isinstance(data,list): continue
        for team in data:
            if (team.get("team") or {}).get("id")!=team_id: continue
            for row in team.get("players") or []:
                ident=(row.get("player") or {}).get("id")
                if not ident: continue
                stats=(row.get("statistics") or [{}])[0]
                games=stats.get("games") or {}
                mins=games.get("minutes")
                if mins is None or mins<=0: continue
                goals=(stats.get("goals") or {}).get("total") or 0
                shots=(stats.get("shots") or {}).get("total") or 0
                rec=records.setdefault(ident,{"played":0,"goals":0,"shots":0,"minutes":0,"rating_sum":0.0,"rating_count":0})
                rec["played"]+=1; rec["goals"]+=goals; rec["shots"]+=shots; rec["minutes"]+=mins
                rating=games.get("rating")
                try:
                    numeric=float(rating)
                    if 0 <= numeric <= 10:
                        rec["rating_sum"]+=numeric
                        rec["rating_count"]+=1
                except (ValueError,TypeError):
                    pass
    return records


def parse_toi(value):
    """Convert NHL game-log TOI (MM:SS) into decimal minutes."""
    if isinstance(value,(int,float)):
        return float(value) if 0 <= value <= 65 else 0.0
    if isinstance(value,str):
        parts=value.split(":")
        try:
            if len(parts)==2:
                minutes=int(parts[0])+int(parts[1])/60
                return minutes if 0 <= minutes <= 65 else 0.0
        except ValueError:
            pass
    return 0.0


@st.cache_data(ttl=7200,show_spinner=False)
def nhl_recent_form(player_id,day):
    """NHL official game log; exclude games on/after the prediction day."""
    if not player_id: return None
    season_year=day.year if day.month>=7 else day.year-1
    season_code=f"{season_year}{season_year+1}"
    payload=nhl(f"player/{player_id}/game-log/{season_code}/2")
    if not isinstance(payload,dict): return None
    games=payload.get("gameLog") or []
    recent=[]
    for game in games:
        try: played=datetime.fromisoformat(str(game.get("gameDate",""))[:10]).date()
        except ValueError: continue
        if played<day: recent.append(game)
    recent=sorted(recent,key=lambda row:row.get("gameDate", ""),reverse=True)[:5]
    if len(recent)<3: return None
    return {"played":len(recent),"goals":sum(int(g.get("goals") or 0) for g in recent),"shots":sum(int(g.get("shots") or 0) for g in recent),"minutes":sum(parse_toi(g.get("toi") or g.get("timeOnIce")) for g in recent)}


def form_score(stats,sport):
    """Rank verified recent performance; scoring is not a betting probability."""
    n=stats["played"]
    if n<3: return None
    goals=stats["goals"]/n
    shots=stats["shots"]/n
    if sport=="football":
        mins=stats.get("minutes") or 0
        playing=min(1.0,mins/(n*75))
        return round((goals*5 + shots*.18)*(.6+.4*playing),3)
    return round(goals*5 + shots*.15,3)


def adjusted_goal_probability(player, stats):
    """Conservative form/minutes adjustment of the existing season model.

    This is a heuristic ranking estimate, NOT a calibrated betting probability.
    """
    base=player.get("p")
    if base is None or not stats or stats.get("played",0)<3:
        return None
    n=stats["played"]
    season_rate=player.get("goals",0)/max(1,player.get("games",1))
    recent_rate=stats.get("goals",0)/n
    # Shrink noisy five-game goal trends toward the season rate.
    goal_factor=max(.75,min(1.25,(recent_rate+.25)/(season_rate+.25)))
    minutes=stats.get("minutes") or 0
    if player["sport"]=="football":
        avg=minutes/n if minutes else 0
        if avg<30: return None
        baseline=player.get("minutes") or 75
        time_factor=max(.75,min(1.2,avg/max(30,baseline)))
    else:
        avg=minutes/n if minutes else 0
        # Hockey ice time is required; missing TOI must not look like verified form.
        if avg<6: return None
        time_factor=max(.75,min(1.2,avg/16.0))
    return min(99.0,round(base*goal_factor*time_factor,2))


def rank_candidates_by_verified_form(pool,day):
    """Choose up to two highest adjusted green scorers per fixture from each team's top five."""
    teams={}
    for player in pool:
        try:
            if datetime.fromisoformat(player["kickoff"])<=datetime.now(TZ): continue
        except (KeyError,ValueError,TypeError): continue
        team_key=(player["league"],player["fixture"],str(player.get("team_id") or player["team"]))
        teams.setdefault(team_key,[]).append(player)
    football_forms={}
    evaluated=[]
    for team_key,players in teams.items():
        for player in sorted(players,key=lambda p:p.get("p") or 0,reverse=True)[:5]:
            if player["sport"]=="football":
                team_id=player.get("team_id")
                if not team_id or not player.get("player_id"): continue
                if team_id not in football_forms:
                    football_forms[team_id]=football_recent_form(team_id,day,secret("API_SPORTS_KEY"))
                stats=football_forms[team_id].get(player["player_id"])
            elif player["league"]=="DEL":
                stats=del_recent_form(player,day)
            else:
                stats=nhl_recent_form(player.get("player_id"),day)
            if not stats: continue
            adjusted=adjusted_goal_probability(player,stats)
            if adjusted is None or probability_tier(adjusted,player["sport"])!="high":
                continue
            score=form_score(stats,player["sport"])
            evaluated.append({**player,"form":stats,"form_score":score,"adjusted_p":adjusted})
    evaluated.sort(key=lambda p:(p["adjusted_p"],p["form_score"]),reverse=True)
    picks=[]; per_match={}
    for player in evaluated:
        key=(player["league"],player["fixture"])
        if per_match.get(key,0)>=2: continue
        picks.append(player)
        per_match[key]=per_match.get(key,0)+1
    return picks


def multi_league_form_combo(day, mode="mixed"):
    """Evaluate all scheduled fixtures for the chosen sport group."""
    pool = []
    if mode in ("football", "mixed"):
        for competition in LEAGUES:
            pool.extend(combo_candidates(day, "⚽ Fußball", competition))
    if mode in ("hockey", "mixed"):
        for competition in ("NHL", "DEL"):
            pool.extend(combo_candidates(day, "🏒 Eishockey", competition))
    return rank_candidates_by_verified_form(pool, day)


def all_leagues_form_combo(day):
    return multi_league_form_combo(day, "mixed")


def render_form_combo(picks):
    if not picks:
        st.info("Keine grünen Torschützen-Kandidaten mit verifizierter Form und Spielzeit gefunden. Es werden keine Tipps ergänzt.")
        return
    st.success(f"{len(picks)} grüne Torschützen-Tipps mit überprüfbarer aktueller Form aus {len({(p['league'],p['fixture']) for p in picks})} Begegnungen.")
    for index,p in enumerate(picks,1):
        form=p["form"]
        avg_minutes=(form.get("minutes") or 0)/form["played"]
        unit="Eiszeit" if p["sport"]=="hockey" else "Spielzeit"
        st.markdown(f'**{index}. 🟢 {html.escape(p["name"])}** · {html.escape(p["team"])} · {p["league"]}')
        st.caption(f'🕒 Spielbeginn {datetime.fromisoformat(p["kickoff"]).strftime("%H:%M")} Uhr · {p["match"]} · Angepasste Torprognose: {pct(p["adjusted_p"])} · Saisonmodell: {pct(p["p"])} · Letzte {form["played"]} Einsätze: {form["goals"]} Tore, {form["shots"]} Schüsse, Ø {avg_minutes:.1f} Min. {unit}')
        if p["sport"]=="football":
            rating_count=form.get("rating_count",0)
            rating=form.get("rating_sum",0)/rating_count if rating_count else None
            label="API-Football Ø-Bewertung"
            official=True
        else:
            rating=nhl_own_form_grade(form)
            rating_count=form["played"]
            label="SportRadar-Formindex (eigene Berechnung)"
            official=False
        st.markdown(grade_badge(label,rating,rating_count,official=official),unsafe_allow_html=True)
        st.caption(f'🔥 Formwert: {form_score(form,p["sport"]):.2f} · Letzte {form["played"]} Einsätze · Position: {p.get("position") or "Unbekannt"}')
        favorite_button(p,f"combo_{index}_{p.get('league')}")
    st.metric("Ausgewählte Tipps",len(picks))
    if len(picks)>1:
        chance=100*math.prod(p["adjusted_p"]/100 for p in picks)
        st.metric("Rechnerische Kombi-Chance (heuristisch)",pct(chance))
    st.warning("Grün bedeutet nur mindestens 30 % im Fußball bzw. 25 % im Eishockey nach einer heuristischen Form-/Spielzeit-Anpassung – nicht sicher. Die Kombi-Chance unterstellt vereinfachend unabhängige Tipps; die Schätzungen sind nicht kalibriert.")


def render_combo_picks(picks,requested):
    if not picks:
        st.info("Keine geeigneten Begegnungen mit ausreichenden Spielerdaten gefunden.")
        return
    if len(picks)<requested:
        st.warning(f"Nur {len(picks)} unterschiedliche geeignete Spiele gefunden. Es werden keine Tipps erfunden.")
    for i,player in enumerate(picks,1):
        tier=probability_tier(player["p"],player["sport"])
        symbol={"high":"🟢","mid":"🟠","low":"⚪"}[tier]
        st.markdown(f'**{i}. {symbol} {player["name"]}** · {player["team"]} · {player["league"]}')
        st.caption(f'{player["match"]} · Tor im Gesamtspiel: {pct(player["p"])} · {player["goals"]} Tore in {player["games"]} Spielen')
    product=math.prod(p["p"]/100 for p in picks)
    st.metric("Rechnerische Kombi-Chance (vereinfachte Unabhängigkeitsannahme)",pct(product*100))
    st.warning("Die Gesamtchance ist nur eine Modellschätzung. Die Tipps sind nicht sicher; Form, Aufstellung, Gegner und Abhängigkeiten zwischen Ereignissen können die Prognose verändern.")


def combo_view(day,sport,league):
    st.subheader("🎟️ Kombi & Wettschein-Prüfung")
    st.caption("Modellbasierte Torschützen-Kandidaten. Keine sicheren Tipps oder bestätigten Buchmacherquoten.")
    tab_daily,tab_all,tab_mixed,tab_check=st.tabs([
        "📅 Grüne Tages-Kombi", "🔥 Große Grün-Kombi",
        "⚽🏒 Mixed Tages-Kombi", "🔎 Wettschein prüfen"
    ])
    with tab_daily:
        sport_mode=st.radio(
            "Alle Ligen dieser Sportart durchsuchen",
            ["⚽ Fußball – alle 7 Ligen", "🏒 Eishockey – NHL + DEL"],
            index=0 if sport.startswith("⚽") else 1,
            key="daily_all_leagues_sport",
        )
        mode="football" if sport_mode.startswith("⚽") else "hockey"
        amount=st.select_slider("Gewünschte Anzahl Tipps",options=[6,7,8,9,10],value=7,key="daily_all_leagues_amount")
        st.caption(f"{day.strftime('%d.%m.%Y')} · Alle Ligen der gewählten Sportart · Torschütze im Gesamtspiel")
        st.caption("Nur grüne Kandidaten mit überprüfbarer Form aus bis zu fünf Einsätzen; maximal zwei Tipps pro Begegnung.")
        request=(str(day),mode)
        if st.button("📅 Form-Tages-Kombi berechnen",key=f"daily_all_{day}"):
            st.session_state["daily_all_request"]=request
        if st.session_state.get("daily_all_request")==request:
            with st.spinner("Alle Ligen und aktuelle Spielerform auswerten …"):
                ranked=multi_league_form_combo(day,mode)
            if len(ranked)<amount:
                st.warning(f"Nur {len(ranked)} geeignete grüne Tipps gefunden; keine Tipps werden erfunden.")
            render_form_combo(ranked[:amount])
    with tab_all:
        st.caption(f"{day.strftime('%d.%m.%Y')} · Alle geeigneten Begegnungen · Höchste grüne Torprognose aus den Top 5 jeder Mannschaft")
        st.caption("Bewertet werden echte letzte fünf Einsätze inklusive Tore, Schüsse und Spielzeit/Eiszeit. Nur grüne Tipps; maximal zwei je Begegnung.")
        st.caption("DEL wird berücksichtigt, sobald der tägliche DEL-Formdaten-Abruf erfolgreich war.")
        if st.button("🔥 Große Form-Kombi für diesen Tag berechnen",key=f"form_{day}"):
            st.session_state["form_day"]=str(day)
        if st.session_state.get("form_day")==str(day):
            with st.spinner("Echte Einzelspiel-Statistiken abrufen und Form bewerten … Dies kann mehrere Minuten dauern und API-Kontingent verbrauchen."):
                picks=all_leagues_form_combo(day)
            render_form_combo(picks)
    with tab_mixed:
        st.markdown("**⚽🏒 Mixed Tages-Kombi: Fußball + Eishockey aus allen 9 Ligen**")
        mixed_amount=st.select_slider(
            "Anzahl Mixed-Tipps",options=[6,7,8,9,10],value=7,key="mixed_daily_amount"
        )
        st.caption(f"{day.strftime('%d.%m.%Y')} · 7 Fußballligen + NHL + DEL · Nur Spiele an diesem Tag")
        st.caption("Nur grüne Torschützen mit überprüfbarer Form, maximal zwei je Begegnung. Fußball und Eishockey werden gemeinsam nach angepasster Torprognose sortiert.")
        if st.button("⚽🏒 Mixed Tages-Kombi berechnen",key=f"mixed_day_{day}"):
            st.session_state["mixed_form_day"]=str(day)
        if st.session_state.get("mixed_form_day")==str(day):
            with st.spinner("Alle 9 Ligen und die letzten fünf Einsätze prüfen …"):
                ranked=multi_league_form_combo(day,"mixed")
            if len(ranked)<mixed_amount:
                st.warning(f"Nur {len(ranked)} geeignete grüne Tipps verfügbar; keine Tipps werden ergänzt.")
            render_form_combo(ranked[:mixed_amount])
    with tab_check:
        st.write("Prüfe einen fremden oder eigenen Tipp anhand der SportRadar-Statistik. Anbieterquoten werden **nicht automatisch abgerufen**.")
        provider=st.selectbox("Buchmacher",["Tipico","bet365","Winamax","Pinnacle","Andere"])
        st.caption("Anbieterwahl dient nur der Zuordnung; kein Zugriff auf fremde Konten oder Wettscheine.")
        with st.form("check_ticket"):
            name=st.text_input("Spielername (Tor im Gesamtspiel)",placeholder="z. B. David Pastrnak")
            quote=st.number_input("Dezimalquote",min_value=1.01,max_value=1000.0,value=2.00,step=0.05)
            submitted=st.form_submit_button("🔎 Tipp prüfen")
        if submitted:
            if not name.strip():
                st.error("Bitte einen Spielernamen eingeben.")
            else:
                with st.spinner("Spieler in den heutigen Begegnungen suchen …"):
                    pool=combo_candidates(day,sport,league)
                matches=[p for p in pool if name.casefold().strip() in p["name"].casefold()]
                if not matches:
                    st.info("Spieler in den heutigen Begegnungen dieser Liga nicht gefunden. Bitte Liga, Datum und Schreibweise prüfen.")
                else:
                    chosen=matches[0]
                    implied=100/quote
                    st.markdown(f'**{chosen["name"]} · {chosen["match"]}**')
                    col1,col2=st.columns(2)
                    col1.metric("SportRadar-Schätzung",pct(chosen["p"]))
                    col2.metric("Quote impliziert ca.",pct(implied))
                    st.caption(f'{provider}: manuell eingegebene Quote {quote:.2f} · Differenz: {chosen["p"]-implied:+.1f} Prozentpunkte')
                    st.info("Eine positive Differenz beweist keinen Vorteil: Modellfehler, Marge, Aufstellung und Spielbedingungen können das Ergebnis verändern.")
        st.caption("Screenshot-Erkennung und Live-Quotenvergleich sind in dieser Version nicht enthalten.")


st.title("🎯 SportRadar – Torschützen heute & morgen")
st.caption("Deutsche Zeit · Saison automatisch · Poisson-Modell mit Stichproben-Glättung")
page=st.radio("Bereich",["🎯 Torprognosen","🎟️ Kombi & Prüfung","⭐ Favoriten"],horizontal=True)
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
if page.startswith("🎯"):
    st.caption("🔥 Aktuelle Form automatisch: Fußball mit API-Football-Bewertungen; NHL und DEL mit eigenem SportRadar-Formindex, soweit Einzelspieldaten vorhanden sind.")
if page.startswith("⭐"):
    st.subheader("⭐ Meine Favoriten")
    st.caption("Favoriten werden mit GitHub synchronisiert, sobald GH_FAVORITES_TOKEN als Streamlit Secret hinterlegt ist. Toralarm benötigt zusätzlich den GitHub-Actions-Workflow.")
    if not secret("GH_FAVORITES_TOKEN"): st.warning("GH_FAVORITES_TOKEN fehlt: Favoriten sind nur während dieser Sitzung gespeichert und können keine Toralarme auslösen.")
    favorites=current_favorites()
    if not favorites: st.info("Noch keine Spieler favorisiert. In den Spielerkarten auf ☆ Favorisieren tippen.")
    for key,entry in list(favorites.items()):
        st.markdown(f"**⭐ {entry.get('name')}** · {entry.get('team')} · {entry.get('league')}")
        if st.button("Entfernen",key=f"remove_{abs(hash(key))}"):
            new=dict(favorites); del new[key]
            if update_favorites(new): st.rerun()
elif page.startswith("🎟️"):
    combo_view(day,sport,league)
elif sport.startswith("🏒"):
    if league=="NHL": nhl_view(day)
    else: del_view(day)
else: football_view(day,league)
st.divider()
st.caption("Alle Prozentwerte sind Modellschätzungen, keine Garantien oder Wettquoten. Aufstellung, Verletzungen, Gegnerstärke, Eiszeit und kleine Stichproben sind nicht vollständig berücksichtigt.")
