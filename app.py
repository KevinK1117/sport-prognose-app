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
st.markdown('<style>\n.sr-lineup-wrap{margin:12px 0 18px;border:1px solid #d9e5eb;border-radius:17px;padding:10px;background:white}\n.sr-lineup-title{text-align:center;font-size:.85rem;font-weight:750;color:#17324b;margin:4px 0 12px}\n.sr-lineup-field{position:relative;isolation:isolate;display:flex;flex-direction:column;justify-content:space-around;gap:14px;padding:18px 5px;min-height:480px;overflow:hidden;border:3px solid #fff;border-radius:12px}\n.sr-lineup-pitch{background:repeating-linear-gradient(0deg,#2c885d 0px,#2c885d 70px,#368e64 70px,#368e64 140px)}\n.sr-lineup-rink{background:linear-gradient(90deg,transparent 30%,#93c7e544 30%,#93c7e544 31%,transparent 31%,transparent 69%,#93c7e544 69%,#93c7e544 70%,transparent 70%),#f0f9ff;border-color:#7caac5}\n.sr-lineup-field:before{content:"";position:absolute;inset:12px;border:2px solid #ffffff88;border-radius:3px;pointer-events:none;z-index:-1}\n.sr-lineup-field:after{content:"";position:absolute;top:50%;left:0;right:0;border-top:2px solid #ffffff77;pointer-events:none;z-index:-1}\n.sr-lineup-row{display:flex;justify-content:space-around;align-items:center;gap:2px;width:100%}\n.sr-lineup-person{display:flex;flex:1;min-width:0;flex-direction:column;align-items:center;text-align:center;gap:3px}\n.sr-lineup-avatar{background:#ffffffed;border-radius:50%;width:31px;height:31px;display:flex;align-items:center;justify-content:center;font-size:19px;box-shadow:0 2px 5px #0002}\n.sr-lineup-name{font-size:clamp(.60rem,2.3vw,.82rem);line-height:1.15;font-weight:750;background:#fffffff2;color:#17324b;border-radius:6px;padding:4px 3px;max-width:100%;overflow-wrap:anywhere;box-shadow:0 2px 5px #0002}\n.sr-lineup-pos{font-size:.65rem;font-weight:650;color:#17324b;background:#ffffffb9;border-radius:5px;padding:1px 5px}\n.sr-lineup-bench{padding:10px 2px}.sr-lineup-bench-list{display:flex;flex-wrap:wrap;gap:12px;margin-top:8px}.sr-lineup-bench-list .sr-lineup-person{flex:0 1 100px}\n@media(max-width:480px){.sr-lineup-field{min-height:410px}.sr-lineup-avatar{width:27px;height:27px;font-size:16px}.sr-lineup-name{font-size:.61rem}}\n</style>',unsafe_allow_html=True)
st.markdown("<style>"+'\n/* SportRadar 2026: vivid, compact mobile-first dashboard */\n[data-testid="stAppViewContainer"]{background:linear-gradient(160deg,#07192c 0%,#0d2b45 260px,#f2f7fb 600px,#f2f7fb 100%)!important}\n.block-container{max-width:1080px;padding-top:1rem!important}\nh1{color:#fff!important;font-weight:850!important;letter-spacing:-.04em!important;text-shadow:0 2px 8px #06152455}\nh1+p, h1~[data-testid="stCaptionContainer"]{color:#c9e8f5!important}\n[data-testid="stRadio"] label,[data-testid="stSelectbox"] label,[data-testid="stMultiSelect"] label{font-weight:700}\n[data-testid="stRadio"] [role="radiogroup"]{gap:.35rem;flex-wrap:wrap}\n[data-testid="stRadio"] [role="radio"]{accent-color:#fa315d}\n[data-testid="stExpander"]{border:1px solid #d5e4f0!important;border-radius:19px!important;background:#fff!important;box-shadow:0 8px 25px #102b4410!important;margin-bottom:12px}\n[data-testid="stExpander"] summary{background:linear-gradient(90deg,#e9f5fc,#f5faff)!important;color:#15334d!important;font-weight:750!important;padding:12px!important}\n.stButton>button{background:linear-gradient(110deg,#e8faff,#fff)!important;border:1px solid #61b8ca!important;color:#076478!important;border-radius:13px!important}\n.stButton>button[kind="primary"]{background:linear-gradient(105deg,#fc315b,#ee5c49)!important;color:#fff!important;border:0!important}\n.player{background:linear-gradient(135deg,#fff,#f2f9ff)!important;box-shadow:0 6px 18px #1839570d!important}\n.sr-live-card{background:#fff;border:1px solid #dbe8f1;border-radius:15px;margin:9px 0;padding:12px 13px;box-shadow:0 3px 12px #112b4110}\n.sr-live-card.is-running{border-left:5px solid #fb2b58;background:linear-gradient(100deg,#fff,#fff5f7)}\n.sr-live-card.is-finished{border-left:5px solid #16a878}\n.sr-live-card.is-upcoming{border-left:5px solid #8fa6b8}\n.sr-live-row{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:8px;align-items:center}\n.sr-live-team{font-weight:750;font-size:.9rem;color:#16334e;overflow-wrap:anywhere}\n.sr-live-team:last-child{text-align:right}\n.sr-live-score{background:#09283e;color:#fff;border-radius:11px;padding:7px 10px;font-weight:850;font-size:1.24rem;white-space:nowrap;font-variant-numeric:tabular-nums}\n.sr-live-state{margin-top:6px;color:#52667a;font-size:.8rem;font-weight:650}\n.sr-live-scorer{margin-top:7px;padding:6px 9px;border-radius:9px;background:#f0f7fb;font-size:.82rem;color:#24506a}\n.sr-hero{padding:15px 18px;border-radius:19px;background:linear-gradient(110deg,#fa2458,#b91664 55%,#093a6d);color:white;box-shadow:0 8px 22px #152a4933;margin:10px 0 16px}\n.sr-hero strong{font-size:1.25rem}.sr-hero small{display:block;color:#ffe3ec;margin-top:4px}\n.sr-combo-profile{border:1px solid #cbe4f0;border-radius:15px;padding:12px;background:#f4fbff;margin:9px 0 14px}\n@media(max-width:550px){.sr-live-card{padding:10px}.sr-live-team{font-size:.81rem}.sr-live-score{font-size:1.05rem;padding:6px}.block-container{padding-left:.75rem!important;padding-right:.75rem!important}}\n'+"</style>",unsafe_allow_html=True)
st.markdown('\n<style>\n[data-testid="stAppViewContainer"]{background:#061528!important;color:#e9f4ff!important}\n[data-testid="stHeader"]{background:#061528!important}\n.block-container{max-width:1000px!important}\nh1,h2,h3,p,li,[data-testid="stMarkdownContainer"]{color:#e9f4ff}\n[data-testid="stCaptionContainer"],.stCaption{color:#93b3cd!important}\n[data-testid="stExpander"]{background:#0c233b!important;border:1px solid #1c4264!important;box-shadow:none!important}\n[data-testid="stExpander"] summary{background:#102a45!important;color:#fff!important}\n[data-testid="stExpander"] summary p{color:#fff!important}\n[data-testid="stTabs"] button{color:#a9c7de!important}\n[data-testid="stTabs"] button[aria-selected="true"]{color:#ff3866!important}\n[data-testid="stTabs"] [data-baseweb="tab-highlight"]{background:#ff3866!important}\n.sr-hero{background:linear-gradient(110deg,#a90039,#e91653 50%,#103a7d)!important;border:1px solid #fc386b!important}\n.sr-game{border-radius:15px;background:linear-gradient(150deg,#103c46,#062a34);border:1px solid #167e68;padding:12px;margin:6px 0 12px}\n.sr-game-running{border-color:#ff315c}.sr-game-finished{border-color:#0dbd86}.sr-game-upcoming{border-color:#315877}\n.sr-game-head{display:flex;justify-content:space-between;gap:12px;font-size:.75rem;color:#a4c8d7;font-weight:750;margin-bottom:12px}\n.sr-game-running .sr-game-head span:first-child{color:#ff416a}\n.sr-game-main{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:center;gap:9px}\n.sr-game-team{display:flex;flex-direction:column;align-items:center;gap:7px;text-align:center;font-size:.81rem;font-weight:750;min-width:0;overflow-wrap:anywhere;color:#fff}\n.sr-game-team img{width:43px!important;height:43px!important;object-fit:contain}\n.sr-game-result{font-size:clamp(1.3rem,6vw,2.15rem);font-weight:900;color:white;background:#031524;border-radius:10px;padding:8px 12px;white-space:nowrap}\n.sr-ticker-item{padding:12px 13px;margin:6px 0;border-radius:12px;background:#0d2c46;color:#e8f7ff;border-left:3px solid #fa335d;font-size:.88rem}\n.sr-stat{padding:9px 0}.sr-stat>div:first-child{display:flex;justify-content:space-between;gap:10px;color:#e6f4ff;font-size:.86rem}\n.sr-stat>div:first-child span{color:#a7c8df}.sr-stat-track{height:9px;background:#284b74;border-radius:9px;overflow:hidden;margin-top:8px}\n.sr-stat-track i{display:block;height:100%;background:#ff3565;border-radius:9px}\n.player{background:#0e2944!important;border-color:#235477!important;color:#f2f8ff!important}\n.player-head,.muted,.sr-team-heading{color:#f2f8ff!important}\n.prob{background:#123d50!important}.prob small{color:#c0d7e8!important}.prob strong{color:#64f2c5!important}\n.sr-form{background:#123d4b!important;color:#d8f0fa!important}.sr-form small{color:#bfd3e1!important}\n.pill{background:#1b4260!important;color:#eaf4fb!important}\n.sr-match{background:#0d2b46!important}.sr-match-name{color:#f5fbff!important}\n.sr-combo-profile{background:#102d47!important;border-color:#285e7b!important}\n.sr-lineup-wrap{background:#0d2a43!important;border-color:#265478!important}.sr-lineup-title{color:#fff!important}\n@media(max-width:480px){.sr-game{padding:10px}.sr-game-team{font-size:.72rem}.sr-game-result{padding:7px 8px}}\n</style>\n',unsafe_allow_html=True)
st.markdown("<style>" + '\n/* SportRadar neon dashboard – accessible contrast, mobile-first */\n[data-testid="stAppViewContainer"]{background:radial-gradient(ellipse at 50% 0%,#104775 0,#071a31 360px,#061427 850px)!important;color:#f4faff!important}\n[data-testid="stHeader"]{background:#061427!important}\n.block-container{max-width:1050px!important;padding:1rem .85rem 3rem!important}\nh1{font-size:clamp(1.85rem,6vw,2.6rem)!important;color:#fff!important;text-shadow:0 0 22px #148fff66!important}\nh2,h3{color:#fff!important}\n[data-testid="stMarkdownContainer"] p,[data-testid="stMarkdownContainer"] li{color:#e4f2ff}\n[data-testid="stCaptionContainer"]{color:#b8d3e9!important}\n[data-testid="stRadio"] label,[data-testid="stSelectbox"] label,[data-testid="stMultiSelect"] label{color:#f3faff!important;font-weight:750!important}\n[data-testid="stRadio"] [role="radiogroup"]{gap:.4rem;flex-wrap:wrap}\n[data-testid="stRadio"] [role="radio"]{accent-color:#ff2c65!important}\n[data-testid="stSelectbox"] [data-baseweb="select"]>div,[data-testid="stMultiSelect"] [data-baseweb="select"]>div{background:#eaf5ff!important;color:#0c2c48!important;border-radius:12px!important}\n[data-testid="stSelectbox"] [data-baseweb="select"] *,[data-testid="stMultiSelect"] [data-baseweb="select"] *{color:#0c2c48!important}\n[data-testid="stExpander"]{background:linear-gradient(155deg,#102e4d,#0b223e)!important;border:1px solid #255e86!important;border-radius:19px!important;overflow:hidden}\n[data-testid="stExpander"] summary{background:#143453!important;color:#fff!important}\n[data-testid="stExpander"] summary p{color:#fff!important;font-weight:750}\n[data-testid="stTabs"] button{color:#c4e1f5!important;font-weight:700}\n[data-testid="stTabs"] button[aria-selected="true"]{color:#ff527a!important}\n.stButton>button{border:1px solid #21a7e8!important;background:linear-gradient(110deg,#103d71,#0759b0)!important;color:#fff!important;font-weight:750!important;box-shadow:0 3px 14px #0077ff22!important}\n.stButton>button:hover{border-color:#60eddf!important;background:#1164b5!important}\n.player{background:linear-gradient(145deg,#103457,#0d2946)!important;border:1px solid #28628c!important;border-left:5px solid #15b68e!important;color:#fff!important;border-radius:19px!important;padding:15px!important;box-shadow:0 7px 24px #0003!important}\n.player.sr-mid{border-left-color:#ffb13d!important}.player.sr-low{border-left-color:#779ab7!important}\n.player-head{color:#fff!important;font-size:1.15rem!important}.muted{color:#bdd8ec!important}\n.player .prob{background:linear-gradient(135deg,#0b4c5d,#0b675e)!important;border:1px solid #149c89!important;border-radius:14px!important;padding:14px 8px!important}\n.player.sr-mid .prob{background:#60441e!important;border-color:#a77a2e!important}\n.player.sr-low .prob{background:#203d57!important;border-color:#345a78!important}\n.player .prob small{color:#e1f4ff!important;font-size:.84rem!important}\n.player .prob strong{color:#7bffda!important;font-size:clamp(1.45rem,5vw,1.95rem)!important}\n.player.sr-mid .prob strong{color:#ffe09b!important}.player.sr-low .prob strong{color:#d8e8f6!important}\n.pill{background:#214b70!important;color:#f4faff!important;border:1px solid #356486!important}\n.sr-form{background:#124254!important;color:#e9faff!important;border:1px solid #226e79!important}\n.sr-form b{color:#7bffda!important}.sr-form small{color:#d5e6f2!important}\n.sr-grade{box-shadow:0 3px 12px #0015!important}.sr-grade-high{background:#dff8eb!important;color:#08613f!important}.sr-grade-mid{background:#fff0d5!important;color:#855009!important}.sr-grade-low{background:#ffe4e5!important;color:#932a36!important}\n.sr-grade-label{font-size:.88rem!important}.sr-grade-score{font-size:2rem!important}\n.sr-match{background:linear-gradient(100deg,#113d5b,#10344f)!important;border:1px solid #255a79!important}\n.sr-match-name,.sr-team-heading{color:#fff!important}\n.sr-game{background:linear-gradient(145deg,#0e3d4b,#0b2442)!important;border:1px solid #139d90!important;box-shadow:0 4px 20px #0017!important}\n.sr-game-running{border-color:#ff315e!important}.sr-game-result{background:#031326!important;color:#fff!important}\n.sr-live-card{background:#12334f!important;color:#fff!important;border-color:#286188!important}\n.sr-live-team{color:#fff!important}.sr-live-state{color:#bcd9ea!important}.sr-live-scorer{background:#19415d!important;color:#e9faff!important}\n.sr-hero{background:linear-gradient(110deg,#c00042,#ed1757 50%,#123d8b)!important;border:1px solid #ff3972!important;box-shadow:0 6px 28px #e3004b40!important;padding:19px!important}\n.sr-hero strong{color:#fff!important;font-size:1.55rem!important}.sr-hero small{color:#fff!important}\n.sr-combo-profile{background:#123653!important;border-color:#2b729a!important;color:#fff!important}\n.sr-lineup-wrap{background:#102f4c!important;border-color:#2c7096!important}.sr-lineup-title{color:#fff!important}\n.sr-ticker-item{background:#153c58!important;color:#fff!important}\n.sr-stat>div:first-child{color:#fff!important}\n[data-testid="stMetric"]{background:#103c59;border:1px solid #176e86;border-radius:14px;padding:12px}\n[data-testid="stMetric"] *{color:#f4ffff!important}\n[data-testid="stDataFrame"]{border-radius:12px;overflow:hidden}\n@media(max-width:500px){.block-container{padding-left:.65rem!important;padding-right:.65rem!important}.player{padding:12px!important}.sr-grade{gap:6px!important}.sr-grade-label{max-width:60%!important}.sr-game-team img{width:36px!important;height:36px!important}}\n' + "</style>", unsafe_allow_html=True)
TZ = ZoneInfo("Europe/Berlin")
LEAGUES = {"Bundesliga":78,"2. Bundesliga":79,"La Liga":140,"Serie A":135,"Premier League":39,"Ligue 1":61,"MLS":253,"Champions League":2,"Europa League":3,"Saudi Pro League":307}
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
    recent=[g for g in info.get('games',[]) if g.get('date','')<day.isoformat()][:20]
    if len(recent)<3: return None
    return {'played':len(recent),'goals':sum(g['goals'] for g in recent),
            'shots':sum(g['shots'] for g in recent),
            'minutes':sum(g['minutes'] for g in recent),
            'assists':sum(g.get('assists') or 0 for g in recent)}


def player_form_details(player, sport, day):
    """Verified form from up to 20 recent appearances; no fabricated matches."""
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


st.markdown("<style>.sr-data-note{font-size:.74rem;color:#acc5d8;margin-top:8px;line-height:1.45}.sr-pred-chips{display:flex;flex-wrap:wrap;gap:3px}</style>",unsafe_allow_html=True)

st.markdown("""<style>
.sr-metric-highlights{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 12px}
.sr-metric-highlight{background:#e7f3ff;color:#092e58;border:2px solid #42b9ff;border-radius:12px;padding:8px 12px;flex:1 1 130px;min-width:0}
.sr-metric-highlight.ice{background:#dcfff3;border-color:#29d3a1;color:#075443}
.sr-metric-highlight.missing{background:#e9eef5;border-color:#8193aa;color:#304259}
.sr-metric-highlight small{display:block;font-size:.76rem;font-weight:750;letter-spacing:.02em}
.sr-metric-highlight strong{display:block;font-size:1.12rem;font-weight:900;margin-top:3px}
</style>""",unsafe_allow_html=True)

def spotlight_metrics(player, sport, form=None):
    """Emphasize only real supplied metrics; never substitute invented xG or ice time."""
    def tile(label,value,kind='',missing=False):
        cls='sr-metric-highlight '+('missing' if missing else kind)
        return f'<div class="{cls}"><small>{html.escape(label)}</small><strong>{html.escape(value)}</strong></div>'
    blocks=[]
    if sport=='football':
        xg=player.get('xg')
        blocks.append(tile('⚽ Expected Goals (xG)',f'{xg:.2f}'.replace('.',',') if isinstance(xg,(int,float)) else 'Nicht verfügbar',missing=not isinstance(xg,(int,float))))
    else:
        minutes=None
        if form and form.get('played') and isinstance(form.get('minutes'),(int,float)):
            minutes=form['minutes']/form['played']
        elif isinstance(player.get('minutes'),(int,float)):
            minutes=player['minutes']
        blocks.append(tile('🏒 Ø Eiszeit / Spiel',f'{minutes:.1f} Min.'.replace('.',',') if minutes is not None else 'Nicht verfügbar','ice',minutes is None))
        pp=player.get('powerplay_minutes')
        blocks.append(tile('⚡ Ø Powerplay-Eiszeit',f'{pp:.1f} Min.'.replace('.',',') if isinstance(pp,(int,float)) else 'Nicht verfügbar','ice',not isinstance(pp,(int,float))))
    if player.get('v2_model'):
        v2=player.get('v2_metrics') or {}
        if sport=='football':
            for field,label in [('npxg90','Non-Penalty xG / 90'),('shots90','Schüsse / 90'),('shots_in_box90','Strafraum-Schüsse / 90'),('shots_on_target90','Schüsse aufs Tor / 90'),('expected_minutes','Erwartete Spielminuten'),('team_xg','Team-xG (Prognose)')]:
                if v2.get(field) is not None: blocks.append(tile(label,f"{v2[field]:.2f}".replace('.',',')))
            if v2.get('penalty_taker')==1: blocks.append(tile('🎯 Elfmeter','Bestätigt'))
        else:
            for field,label in [('ixg60','Expected Goals / 60'),('shots_on_target_game','Schüsse aufs Tor / Spiel'),('attempts_game','Schussversuche / Spiel'),('pp_toi_game','Powerplay-Eiszeit / Spiel'),('high_danger_game','High-Danger-Chancen / Spiel')]:
                if v2.get(field) is not None: blocks.append(tile(label,f"{v2[field]:.2f}".replace('.',','),'ice'))
            if v2.get('pp1')==1: blocks.append(tile('⚡ Powerplay','PP1 bestätigt','ice'))
    if player.get('v2_model'):
        opponent=(player.get('v2_metrics') or {}).get('opponent_factor')
        if isinstance(opponent,(int,float)):blocks.append(tile('Gegnerfaktor',f'{opponent:.2f}'.replace('.',',')))
    return '<div class="sr-metric-highlights">'+''.join(blocks)+'</div>'

@st.cache_data(ttl=120,show_spinner=False)
def daily_player_stats():
    path=Path(__file__).resolve().parent/'data'/'daily_player_stats.json'
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}


def daily_player_evidence(player):
    pid=player.get('player_id')
    if not pid:return None
    entry=daily_player_stats().get('nhl',{}).get(str(pid))
    if not entry:return None
    if normalize_team(entry.get('team'))!=normalize_team(player.get('team')):return None
    return entry

@st.cache_data(ttl=300, show_spinner=False)
def _football_advanced_rows(csv_mtime):
    """Read the GitHub-persisted Understat feed, not the ephemeral SQLite import."""
    import csv
    path=Path(__file__).resolve().parent/'data'/'advanced_player_metrics.csv'
    try:
        with path.open(encoding='utf-8-sig',newline='') as fh:
            return [r for r in csv.DictReader(fh) if r.get('sport')=='Fußball' and r.get('sample')=='season']
    except (OSError, UnicodeError, csv.Error):
        return []


def _football_csv_prediction(player):
    """Overlay only unambiguous same-team Understat players with genuine xG and minutes."""
    import math
    import unicodedata
    def norm(v):
        return ''.join(c for c in unicodedata.normalize('NFKD',str(v or '').casefold()) if c.isalnum())
    def val(v):
        try:
            x=float(v)
            return x if math.isfinite(x) else None
        except (ValueError,TypeError):
            return None
    path=Path(__file__).resolve().parent/'data'/'advanced_player_metrics.csv'
    try: rows=_football_advanced_rows(path.stat().st_mtime_ns)
    except OSError: return player
    team=norm(player.get('team'))
    name=norm(player.get('name'))
    # Explicit, team-scoped alias. Do not fuzzy-match unrelated footballers.
    aliases={('levante','brugui'):'rogerbrugue',('levante','brugi'):'rogerbrugue'}
    name=aliases.get((team,name),name)
    matches=[r for r in rows if norm(r.get('team'))==team and norm(r.get('name'))==name]
    if len(matches)!=1:return player
    r=matches[0]
    xg=val(r.get('xg90')); mins=val(r.get('expected_minutes'))
    if xg is None or mins is None or not (0<=xg<=5 and 0<mins<=120):return player
    # Do not use data from after the scheduled match.
    fixture=str(player.get('kickoff') or '')[:10]
    if fixture and str(r.get('as_of') or '')[:10]>fixture:return player
    lam=xg*mins/90
    output=dict(player)
    output['p']=round(100*(-math.expm1(-lam)),2)
    output['half']=round(100*(-math.expm1(-lam*.45)),2)
    output['xg']=round(lam,4)
    output['v2_model']='Understat xG/Spielzeit-Modell (Poisson; Halbzeit angenähert)'
    output['v2_source']=r.get('source') or 'Understat'
    output['v2_metrics']={k:val(r.get(k)) for k in ('npxg90','xg90','shots90','shots_on_target90','shots_in_box90','expected_minutes','team_xg','opponent_factor')}
    return output


def enriched_player(player):
    """Use verified SportRadar v2 next/season metrics when available; otherwise retain legacy model."""
    if player.get('sport')=='football' or (player.get('sport') is None and player.get('team_id') is not None):
        enriched=_football_csv_prediction(player)
        if enriched is not player:
            return enriched
    try:
        from sport_database import match_prediction
        return match_prediction(player)
    except (ImportError, OSError, ValueError):
        return player


def show_player(player,period_label,sport="hockey",form_stats=None,show_form=False):
    player=enriched_player(player)
    tier=probability_tier(player.get("p"),sport)
    name=html.escape(str(player["name"])); team=html.escape(str(player["team"]))
    pills=[f'Position: {player.get("position") or "Unbekannt"}',f'{player["goals"]} Tore',f'{player["games"]} Spiele']
    if player.get("shots") is not None: pills.append(f'{player["shots"]} Schüsse')
    if player.get("minutes") is not None: pills.append(f'{player["minutes"]:.0f} Min Ø')
    # Only display per-match rates supported by real provider values.
    games_count=player.get("games") or 0
    if games_count and isinstance(player.get("shots"),(int,float)):
        pills.append(f'{player["shots"]/games_count:.1f} Schüsse/Spiel')
    if sport=="football" and games_count and isinstance(player.get("shots_on"),(int,float)):
        pills.append(f'{player["shots_on"]/games_count:.1f} aufs Tor/Spiel')
    if sport=="football" and isinstance(player.get("xg"),(int,float)):
        pills.append(f'xG {player["xg"]:.2f}')
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
            form_html=f'<div class="sr-form sr-form-minimal">🔥 {html.escape(detail)}</div>' 
        else:
            form_html=''
    else:
        form_html=''
    # Transparent data provenance: unavailable metrics are not fabricated.
    data_notes=[]
    if sport=="football":
        if player.get("xg") is None: data_notes.append("xG nicht verfügbar")
        data_notes.append("Startelf/Verletzungen nur bei bestätigter Datenlage")
    else:
        data_notes.append("PP1/Powerplay-Eiszeit nur bei vorhandenen Daten")
    notes_html='<div class="sr-data-note">'+' · '.join(html.escape(x) for x in data_notes)+'</div>'
    highlights_html=spotlight_metrics(player,sport,form_stats)
    if sport=='nhl':
        evidence=daily_player_evidence(player)
        if evidence:
            sample=evidence.get('last20') or evidence.get('last10') or evidence.get('last5') or {}
            if sample.get('games'):
                shots=sample.get('shots_on_target_game')
                ice=sample.get('toi_game')
                parts=[f"Letzte {sample['games']} Spiele: {sample.get('goals',0)} Tore"]
                if shots is not None:parts.append(f"{shots:.1f} Schüsse aufs Tor/Spiel")
                if ice is not None:parts.append(f"Ø Eiszeit {ice:.1f} Min")
                highlights_html+='<div class="sr-daily-evidence">📅 <b>Täglich aktualisierte NHL-Statistik</b><br>'+html.escape(' · '.join(parts))+'</div>'

    portrait=safe_logo(player.get("photo"))
    if not portrait and sport=="football" and player.get("player_id"):
        portrait=f'https://media.api-sports.io/football/players/{player["player_id"]}.png'
    avatar=f'<img src="{html.escape(portrait,quote=True)}" alt="Spielerfoto" loading="lazy">' if portrait else '👤'
    grade_value=None
    if form_stats and form_stats.get("played",0)>=3:
        if sport=="football":
            cnt=form_stats.get("rating_count",0)
            grade_value=form_stats.get("rating_sum",0)/cnt if cnt else None
        else: grade_value=nhl_own_form_grade(form_stats)
    grade_text=f'{grade_value:.1f}'.replace('.',',') if grade_value is not None else '–'
    grade_color=("green" if grade_value is not None and grade_value>=8 else "yellow" if grade_value is not None and grade_value>=6 else "red" if grade_value is not None else "unknown")
    league_text=html.escape(str(player.get("league") or ("NHL" if sport=="nhl" else "DEL" if sport=="del" else "Fußball")))
    st.markdown(f'''<div class="player sr-{tier} sr-pred-compact"><div class="sr-pred-head"><div class="sr-pred-photo">{avatar}</div><div class="sr-pred-identity"><div class="player-head">{name}</div><div class="sr-pred-league">{league_text} · {team}</div></div><div class="sr-pred-grade sr-grade-{grade_color}"><small>{"API-Football Ø-Note" if sport=="football" else "🔥 Formindex"}</small><strong>{grade_text}<em>/10</em></strong></div></div><div class="pair"><div class="prob"><small>{html.escape(period_label)}</small><strong>{pct(player.get("half"))}</strong></div><div class="prob"><small>Gesamtspiel</small><strong>{pct(player.get("p"))}</strong></div></div><div class="sr-pred-chips">{chips}</div><div class="sr-pred-details sr-pred-always-visible"><div class="sr-pred-detail-body">{highlights_html}{form_html}{notes_html}</div></div></div>''',unsafe_allow_html=True)


def show_players(players,period_label,sport="hockey"):
    if not players:
        st.info("Keine verlässlichen Spielerstatistiken verfügbar."); return
    tab1,tab2=st.tabs(["🎯 Spielerprognosen","📊 Tabelle"])
    with tab1:
        for p in players:
            p=enriched_player({**p, 'sport':'football'} if sport=='football' else p)
            stats=player_form_details(p,sport,day)
            show_player(p,period_label,sport,stats,True)
            favorite_button({**p, "league": p.get("league") or ("NHL" if sport == "nhl" else "DEL" if sport == "del" else "")},f"card_{sport}_{p.get('team')}_{p.get('name')}")
    with tab2:
        table=[]
        for p in players:
            p=enriched_player({**p, 'sport':'football'} if sport=='football' else p)
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
                result[ident]={"name":player.get("name") or "Unbekannt","player_id":player.get("id"),"team_id":team_id,"team":team.get("name") or "","position":games.get("position") or "Unbekannt","goals":total_goals,"games":apps,"shots":shots.get("total"),"shots_on":shots.get("on"),"xg":None,"minutes":avg_minutes,"p":probability(total_goals,apps,avg_minutes),"half":probability(total_goals,apps,avg_minutes,period=0.45)}
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
        result.append({"name":f"{first} {last}".strip() or "Unbekannt","player_id":item.get("playerId") or item.get("id"),"photo":(f"https://assets.nhle.com/mugs/nhl/{datetime.now(TZ).year if datetime.now(TZ).month>=7 else datetime.now(TZ).year-1}{datetime.now(TZ).year+1 if datetime.now(TZ).month>=7 else datetime.now(TZ).year}/{abbrev}/{item.get('playerId') or item.get('id')}.png" if (item.get("playerId") or item.get("id")) else None),"team":abbrev,"position":item.get("positionCode") or item.get("position") or "Unbekannt","goals":goals,"games":games,"shots":item.get("shots"),"minutes":None,"p":probability(goals,games,prior=0.18),"half":probability(goals,games,period=1/3,prior=0.18)})
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
            hockey_lineup_panel(home_name,hp,away_name,ap,f"nhl_{day}")
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
            hockey_lineup_panel(home_name,hp,away_name,ap,f"del_{day}")
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


def github_favorites_headers(token):
    return {"Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def favorites_error(response):
    """Show actionable GitHub errors without ever exposing credentials."""
    status=response.status_code
    if status==401:
        return "GitHub HTTP 401: Token ungültig oder abgelaufen. GH_FAVORITES_TOKEN in Streamlit Secrets erneuern."
    if status==403:
        return "GitHub HTTP 403: Schreibzugriff verweigert. Token-Berechtigung 'Contents: Read and write' prüfen."
    if status==404:
        return "GitHub HTTP 404: Repository oder Datei nicht erreichbar. GH_FAVORITES_REPO und Repository-Zugriff des Tokens prüfen."
    if status==409:
        return "GitHub HTTP 409: Gleichzeitige Änderung. Bitte erneut auf Favorisieren tippen."
    if status==422:
        return "GitHub HTTP 422: GitHub hat die Änderung abgelehnt. Token-Berechtigung und Branch-Schutz prüfen."
    return f"GitHub HTTP {status}: Speichern nicht möglich. Repository und Token-Berechtigungen prüfen."


def load_persistent_favorites():
    token,repo=github_favorites_config()
    if not token: return None
    try:
        response=requests.get(f"https://api.github.com/repos/{repo}/contents/data/favorites.json",
            headers=github_favorites_headers(token),params={"ref":"main"},timeout=15)
        if response.status_code==404:
            # A missing file and a token without repository access both produce 404.
            # Do not mistake an inaccessible repository for an empty favorites file.
            repo_check=requests.get(f"https://api.github.com/repos/{repo}",
                headers=github_favorites_headers(token),timeout=15)
            if repo_check.ok: return {},None
            st.session_state["sr_favorites_error"]=favorites_error(repo_check)
            return None
        if not response.ok:
            st.session_state["sr_favorites_error"]=favorites_error(response)
            return None
        data=response.json()
        content=json.loads(base64.b64decode(data["content"]).decode("utf-8"))
        if not isinstance(content,dict):
            st.session_state["sr_favorites_error"]="GitHub: data/favorites.json enthält kein gültiges JSON-Objekt."
            return None
        st.session_state.pop("sr_favorites_error",None)
        return content,data.get("sha")
    except (requests.RequestException,ValueError,KeyError,UnicodeDecodeError) as exc:
        st.session_state["sr_favorites_error"]=f"GitHub konnte nicht gelesen werden ({type(exc).__name__})."
        return None


def save_persistent_favorites(favorites,sha):
    token,repo=github_favorites_config()
    if not token: return False
    body={"message":"Update SportRadar favorites","branch":"main","content":base64.b64encode(
        json.dumps(favorites,ensure_ascii=False,indent=2).encode("utf-8")).decode("ascii")}
    if sha: body["sha"]=sha
    try:
        response=requests.put(f"https://api.github.com/repos/{repo}/contents/data/favorites.json",
            headers=github_favorites_headers(token),json=body,timeout=20)
        if not response.ok:
            st.session_state["sr_favorites_error"]=favorites_error(response)
            return False
        st.session_state.pop("sr_favorites_error",None)
        return True
    except requests.RequestException as exc:
        st.session_state["sr_favorites_error"]=f"GitHub-Verbindung fehlgeschlagen ({type(exc).__name__})."
        return False


def current_favorites():
    if "sr_favorites" not in st.session_state:
        stored=load_persistent_favorites()
        st.session_state["sr_favorites"]=stored[0] if stored is not None else {}
        st.session_state["sr_favorites_sha"]=stored[1] if stored is not None else None
    return st.session_state["sr_favorites"]


def update_favorites(favorites):
    if secret("GH_FAVORITES_TOKEN"):
        stored=load_persistent_favorites()
        if stored is None or not save_persistent_favorites(favorites,stored[1]):
            st.error(st.session_state.get("sr_favorites_error") or
                     "Favorit konnte nicht dauerhaft auf GitHub gespeichert werden.")
            return False
    st.session_state["sr_favorites"]=favorites
    return True


def favorite_league(player):
    """Normalize the league for both player cards and combo picks."""
    league = str(player.get("league") or "").strip()
    if league in ("NHL", "DEL") or league in LEAGUES:
        return league
    sport = str(player.get("sport") or "").lower()
    if sport == "nhl":
        return "NHL"
    if sport == "del":
        return "DEL"
    if sport == "hockey" and player.get("player_id"):
        return "NHL"
    return league or ("NHL" if player.get("player_id") and not player.get("team_id") else "")


def favorite_key(player):
    league = favorite_league(player)
    return f"{league}:{player.get('player_id') or player.get('team','')}:{player.get('name','')}"


def matching_favorite_keys(favorites, player):
    """Recognize older keys with missing league without creating duplicates."""
    expected_league = favorite_league(player)
    expected_id = str(player.get("player_id") or "")
    expected_name = normalize_team(player.get("name"))
    expected_team = normalize_team(player.get("team"))
    matches = []
    for key, entry in favorites.items():
        if not isinstance(entry, dict):
            continue
        saved_league = str(entry.get("league") or "").strip()
        if saved_league and saved_league != expected_league:
            continue
        saved_id = str(entry.get("player_id") or "")
        if expected_id and saved_id:
            same_player = expected_id == saved_id
        else:
            same_player = (normalize_team(entry.get("name")) == expected_name
                           and normalize_team(entry.get("team")) == expected_team)
        if same_player:
            matches.append(key)
    return matches


def favorite_button(player, prefix):
    favorites = current_favorites()
    league = favorite_league(player)
    player = {**player, "league": league}
    key = favorite_key(player)
    old_keys = matching_favorite_keys(favorites, player)
    is_favorite = key in favorites or bool(old_keys)
    label = "⭐ Favorisiert" if is_favorite else "☆ Favorisieren"
    if st.button(label, key=f"fav_{prefix}_{abs(hash(key))}"):
        new = dict(favorites)
        if is_favorite:
            for old_key in set(old_keys + [key]):
                new.pop(old_key, None)
        else:
            new[key] = {"name": player.get("name"), "team": player.get("team"),
                        "league": league, "player_id": player.get("player_id"),
                        "team_id": player.get("team_id")}
        if update_favorites(new):
            st.rerun()


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
            entry=appearances.setdefault(str(ident),{"id":player.get("id"),"name":player.get("name") or "?","pos":player.get("pos") or "?","starts":0,"number":player.get("number")})
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
    return {"players":chosen,"ranked":ranked,"samples":samples,"formation":formation}


st.markdown('<style>\n/* Improved tactical rows: balanced spacing and readable labels on phones. */\n.sr-lineup-field{min-height:530px;gap:7px;padding:14px 7px;justify-content:space-around}\n.sr-lineup-section{width:100%;min-width:0;display:flex;flex-direction:column;align-items:center;gap:3px}\n.sr-lineup-section-label{font-size:.66rem;font-weight:800;color:#17324b;background:#ffffffcf;padding:2px 9px;border-radius:999px}\n.sr-lineup-row{justify-content:center;gap:clamp(3px,2vw,15px)}\n.sr-lineup-person{flex:0 1 23%;max-width:23%;min-width:0}\n.sr-lineup-name{font-size:clamp(.63rem,2.2vw,.84rem);width:100%;box-sizing:border-box;min-height:27px;display:flex;align-items:center;justify-content:center;overflow-wrap:anywhere;hyphens:auto}\n.sr-lineup-avatar{flex:none}\n.sr-lineup-bench-list .sr-lineup-person{flex:0 1 95px;max-width:95px}\n.sr-lineup-rink .sr-lineup-person{flex-basis:29%;max-width:29%}\n@media(max-width:480px){.sr-lineup-field{min-height:510px;padding:13px 5px}.sr-lineup-row{gap:5px}.sr-lineup-person{flex-basis:24%;max-width:24%}.sr-lineup-name{font-size:.63rem;padding:4px 2px}.sr-lineup-rink .sr-lineup-person{flex-basis:31%;max-width:31%}}\n</style>',unsafe_allow_html=True)

@st.cache_data(ttl=3600,show_spinner=False)
def football_squad_photos(team_id,key):
    """Photos from API-Football squad profiles when available."""
    rows=api("players/squads",{"team":team_id},key=key)
    photos={}
    for team in rows or []:
        for player in team.get("players") or []:
            if player.get("id") and safe_logo(player.get("photo")):
                photos[str(player["id"])]=player["photo"]
    return photos


@st.cache_data(ttl=1800,show_spinner=False)
def football_fixture_absences(fixture_id,key):
    """Only fixture-specific reported absences; empty data is not proof of fitness."""
    if not fixture_id or not key: return {}
    rows=api("injuries",{"fixture":fixture_id},key=key)
    if not isinstance(rows,list): return {}
    result={}
    for item in rows:
        team=(item.get("team") or {}).get("id")
        player=item.get("player") or {}
        if team is None or not player.get("id"): continue
        result.setdefault(str(team),{})[str(player["id"])]={
            "name":player.get("name") or "Unbekannt",
            "reason":str(player.get("reason") or item.get("type") or "Gemeldeter Ausfall"),
            "type":str(player.get("type") or item.get("type") or "")}
    return result


def lineup_board(team_name, players, sport="football", formation=None, confirmed=False, bench=None, absences=None):
    """Responsive field with actual formation rows; no invented player photos or ratings."""
    def tile(p):
        full=str(p.get("name") or "?").strip()
        bits=full.split()
        # Shorten only long labels; retain the full name as an accessible tooltip.
        display=full if len(full)<=15 else ((bits[0][0]+". "+" ".join(bits[1:])) if len(bits)>1 else full)
        number=p.get("number")
        prefix=f"{html.escape(str(number))} " if number is not None else ""
        position=html.escape(str(p.get("pos") or ""))
        photo=safe_logo(p.get("photo"))
        avatar=(f'<img src="{html.escape(photo,quote=True)}" alt="" loading="lazy" '
                'style="width:100%;height:100%;object-fit:cover;border-radius:50%" '
                'onerror="this.style.display=\'none\';this.parentElement.textContent=\'👤\'">') if photo else '👤'
        return (f'<div class="sr-lineup-person" title="{html.escape(full,quote=True)}">'
                f'<span class="sr-lineup-avatar">{avatar}</span>'
                f'<span class="sr-lineup-name">{prefix}{html.escape(display)}</span>'
                f'<span class="sr-lineup-pos">{position}</span></div>')

    groups={"G":[],"D":[],"M":[],"F":[]}
    for player in players:
        pos=str(player.get("pos") or "M").upper()[:1]
        groups[pos if pos in groups else "M"].append(player)
    sections=[]
    if sport=="football":
        # Formation describes outfield lines from forwards to defence (e.g. 4-2-3-1).
        try:
            counts=[int(v) for v in str(formation).split("-")]
            valid=sum(counts)==10 and len(counts) in (3,4,5) and all(1<=v<=5 for v in counts)
        except (ValueError,TypeError): valid=False
        if valid:
            # Assign position groups to the tactical lines; preserve forward/midfield/defender priority.
            defenders=groups["D"][:]
            forwards=groups["F"][:]
            midfield=groups["M"][:]
            ordered=(defenders+midfield+forwards)
            if len(ordered)<10: ordered += [x for x in players if x not in ordered and str(x.get("pos") or "").upper()[:1]!="G"]
            # Fill defensive and offensive lines from their natural groups, then the rest.
            remaining=ordered[:]
            lineups=[]
            for i,n in enumerate(counts):
                preferred=defenders if i==0 else forwards if i==len(counts)-1 else midfield
                row=[]
                for candidate in preferred:
                    if candidate in remaining and len(row)<n:
                        row.append(candidate); remaining.remove(candidate)
                while len(row)<n and remaining: row.append(remaining.pop(0))
                lineups.append(row)
            sections=[("",row) for row in reversed(lineups) if row]
        else:
            # Avoid six across a phone screen even when the formation is unknown.
            for key in ("F","M","D"):
                group=groups[key]
                chunks=[group[i:i+4] for i in range(0,len(group),4)]
                sections.extend(("",chunk) for chunk in chunks)
        if groups["G"]: sections.append(("",groups["G"][:1]))
        field="pitch"
    else:
        forwards=groups["F"]+groups["M"]
        defenders=groups["D"]
        for i in range(0,min(len(forwards),12),3):
            sections.append((f"Sturm · Reihe {i//3+1}",forwards[i:i+3]))
        for i in range(0,min(len(defenders),6),2):
            sections.append((f"Verteidigung · Paar {i//2+1}",defenders[i:i+2]))
        if groups["G"]: sections.append(("Torhüter",groups["G"][:1]))
        field="rink"
    if not sections:
        st.info("Keine Spieler für eine Aufstellung verfügbar."); return
    status="Bestätigte Aufstellung" if confirmed else "Voraussichtliche / statistische Darstellung"
    detail=f" · {html.escape(str(formation))}" if formation else ""
    markup=(f'<div class="sr-lineup-wrap"><div class="sr-lineup-title">{html.escape(team_name)} · {status}{detail}</div>'
            f'<div class="sr-lineup-field sr-lineup-{field}">')
    for label,row in sections:
        markup+=(f'<div class="sr-lineup-section">'
                 +(f'<div class="sr-lineup-section-label">{html.escape(label)}</div>' if label else '')
                 +'<div class="sr-lineup-row">'+''.join(tile(x) for x in row)+'</div></div>')
    markup+='</div>'
    if bench:
        markup+='<div class="sr-lineup-bench"><b>🪑 Ersatzbank</b><div class="sr-lineup-bench-list">'+''.join(tile(x) for x in bench)+'</div></div>'
    markup+='</div>'
    st.markdown(markup,unsafe_allow_html=True)
    if absences:
        st.markdown("**🚑 Gemeldete Ausfälle / fragliche Einsätze**")
        for entry in absences:
            st.caption(f"• {entry['name']}: {entry['reason']} ({entry['type'] or 'Status nicht näher angegeben'})")


def hockey_lineup_panel(home_name,home_players,away_name,away_players,identifier):
    with st.expander("👥 Mannschaftsaufstellung auf dem Eis (statistisch)",expanded=False):
        st.caption("Keine bestätigten Reihen: Spieler werden nach Saison-Torstatistik und Position angeordnet. Verletzungen und tatsächliche Einsatzreihen sind nicht verifiziert.")
        tab_home,tab_away=st.tabs([f"🏠 {home_name}",f"✈️ {away_name}"])
        for tab,name,players in ((tab_home,home_name,home_players),(tab_away,away_name,away_players)):
            with tab:
                skaters=sorted(players,key=lambda x:x.get("p") or 0,reverse=True)
                arranged=[{"name":p.get("name"),"pos":p.get("position"),"number":p.get("number"),
                           "photo":p.get("photo")} for p in skaters]
                lineup_board(name,arranged,"hockey")


def display_football_lineup(fixture_id,home_name,away_name,key,home_id=None,away_id=None,day=None):
    with st.expander("👥 Voraussichtliche / bestätigte Aufstellung auf dem Spielfeld",expanded=False):
        rows=football_confirmed_lineup(fixture_id,key)
        absences_by_team=football_fixture_absences(fixture_id,key)
        confirmed={str((r.get("team") or {}).get("id")):r for r in (rows or [])}
        tab_home,tab_away=st.tabs([f"🏠 {home_name}",f"✈️ {away_name}"])
        for tab,team_name,team_id in ((tab_home,home_name,home_id),(tab_away,away_name,away_id)):
            with tab:
                team=confirmed.get(str(team_id))
                reported=absences_by_team.get(str(team_id),{})
                photos=football_squad_photos(team_id,key) if team_id else {}
                if team and team.get("startXI"):
                    st.success("✅ Bestätigte Startelf vom Datenanbieter")
                    starters=[(x.get("player") or {}) for x in team.get("startXI") or []]
                    bench=[(x.get("player") or {}) for x in team.get("substitutes") or []]
                    for player in starters+bench:
                        player["photo"]=photos.get(str(player.get("id")))
                    lineup_board(team_name,starters,formation=team.get("formation"),confirmed=True,bench=bench,
                                 absences=list(reported.values()))
                else:
                    st.info("⏳ Noch keine bestätigte Startelf. Prognose aus früheren Startaufstellungen möglich.")
                    if not team_id or day is None:
                        st.caption("Keine Teamkennung verfügbar."); continue
                    flag=f"expected_show_{fixture_id}_{team_id}"
                    if st.button(f"🔎 Voraussichtliche Elf für {team_name} anzeigen",key=f"expected_{fixture_id}_{team_id}"):
                        st.session_state[flag]=True
                    if st.session_state.get(flag):
                        with st.spinner("Frühere Startelf-Einsätze auswerten …"):
                            expected=football_expected_lineup(team_id,day,key)
                        if not expected:
                            st.warning("Zu wenige frühere bestätigte Aufstellungen für eine belastbare Prognose.")
                        else:
                            eligible=[]; missing=[]
                            for player in expected["players"]:
                                player["photo"]=photos.get(str(player.get("id")))
                                if str(player.get("id")) in reported:
                                    missing.append(reported[str(player["id"])])
                                else:
                                    eligible.append(player)
                            # Replace reported absentees from historical starter frequency,
                            # preserving their broad position when a substitute is available.
                            used={str(x.get("id")) for x in eligible}
                            for candidate in expected.get("ranked",[]):
                                ident=str(candidate.get("id"))
                                if len(eligible)>=11: break
                                if ident in used or ident in reported: continue
                                candidate={**candidate,"photo":photos.get(ident)}
                                eligible.append(candidate); used.add(ident)
                            eligible.sort(key=lambda x:({"G":0,"D":1,"M":2,"F":3}.get(x.get("pos"),4),-x.get("starts",0)))
                            lineup_board(team_name,eligible,formation=expected["formation"],
                                         absences=list(reported.values()))
                            st.caption(f"Statistische Prognose aus {expected['samples']} früheren Aufstellungen. Gemeldete Ausfälle werden ausgeschlossen; Rotation wird anhand der Startelf-Häufigkeit berücksichtigt. Fehlende Meldungen bedeuten nicht, dass ein Spieler fit ist. Keine bestätigte Elf.")


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
    """Up to 20 completed fixtures before the chosen day, all competitions."""
    rows=api("fixtures",{"team":team_id,"last":35,"status":"FT","timezone":"Europe/Berlin"},key=key)
    if not isinstance(rows,list): return []
    found=[]
    for row in rows:
        fixture=row.get("fixture") or {}
        try:
            played=datetime.fromisoformat(str(fixture.get("date","")).replace("Z","+00:00")).date()
        except ValueError: continue
        if played<day and fixture.get("id"):
            found.append((played,fixture["id"]))
    return [fid for _,fid in sorted(found,reverse=True)[:20]]


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
    recent=sorted(recent,key=lambda row:row.get("gameDate", ""),reverse=True)[:20]
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
    # Shrink noisy recent-game goal trends toward the season rate.
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


def combo_evidence_score(player, stats):
    """Evidence-based ranking score, not a calibrated probability.

    Uses available xG/ixG, verified recent shots and deployment. Opponent
    adjustment is applied only when a source actually provides the factor.
    """
    n=max(1,int(stats.get("played") or 1))
    shots=max(0.0,float(stats.get("shots") or 0)/n)
    minutes=max(0.0,float(stats.get("minutes") or 0)/n)
    metrics=player.get("v2_metrics") or {}
    score=0.0
    if player.get("sport")=="football":
        xg90=metrics.get("npxg90")
        if not isinstance(xg90,(int,float)): xg90=metrics.get("xg90")
        if isinstance(xg90,(int,float)) and math.isfinite(xg90) and xg90>=0:
            score+=min(1.5,xg90)*18.0
        shots90=metrics.get("shots90")
        if isinstance(shots90,(int,float)) and math.isfinite(shots90) and shots90>=0:
            score+=min(6.0,shots90)*2.0
        else:
            score+=min(5.0,shots)*2.0
        score+=min(90.0,minutes)/90.0*9.0
        expected=metrics.get("expected_minutes")
        if isinstance(expected,(int,float)) and math.isfinite(expected) and expected>=0:
            score+=min(90.0,expected)/90.0*5.0
    else:
        ixg=metrics.get("ixg60")
        if isinstance(ixg,(int,float)) and math.isfinite(ixg) and ixg>=0:
            score+=min(3.0,ixg)*9.0
        score+=min(7.0,shots)*2.5
        score+=min(25.0,minutes)/25.0*9.0
        pp=player.get("powerplay_minutes")
        if isinstance(pp,(int,float)) and pp>=0: score+=min(6.0,pp)*1.5
        if player.get("pp1") is True: score+=3.0
    # Modest recent-goal signal, so small samples do not dominate xG/shots.
    score+=min(1.0,max(0.0,float(stats.get("goals") or 0)/n))*5.0
    opponent=metrics.get("opponent_factor")
    if isinstance(opponent,(int,float)) and math.isfinite(opponent) and opponent>0:
        score*=max(.8,min(1.2,opponent))
    return round(score,3)


def combo_evidence_caption(player, form):
    n=max(1,int(form.get("played") or 1))
    games=max(1,int(player.get("games") or 1))
    labels=[f"Ø {(form.get('shots') or 0)/n:.1f} Schüsse (letzte {n})"]
    labels.append(f"Ø {(form.get('minutes') or 0)/n:.1f} Min. {'Eiszeit' if player.get('sport')=='hockey' else 'Spielzeit'}")
    if player.get("sport")=="football":
        if isinstance(player.get("shots_on"),(int,float)):
            labels.append(f"Ø {player['shots_on']/games:.1f} Schüsse aufs Tor (Saison)")
        if isinstance(player.get("xg"),(int,float)):
            labels.append(f"xG {player['xg']:.2f} (Saison)")
        else:
            labels.append("xG: keine Daten")
        labels.append("Elfmeter: bestätigt" if player.get("penalty_taker") is True else "Elfmeterschütze: nicht verifiziert")
    else:
        if isinstance(player.get("powerplay_minutes"),(int,float)):
            labels.append(f"Ø {player['powerplay_minutes']:.1f} Min. Powerplay")
        else:
            labels.append("Powerplay-Eiszeit: keine Daten")
        if player.get("pp1") is True:
            labels.append("PP1: bestätigt")
    metrics=player.get("v2_metrics") or {}
    xg=metrics.get("npxg90") if player.get("sport")=="football" else metrics.get("ixg60")
    if not isinstance(xg,(int,float)):
        xg=metrics.get("xg90") if player.get("sport")=="football" else None
    if isinstance(xg,(int,float)):
        labels.append(f"{"xG/90" if player.get('sport')=='football' else 'ixG/60'} {xg:.2f}")
    opponent=metrics.get("opponent_factor")
    if isinstance(opponent,(int,float)) and opponent>0:
        labels.append(f"Gegnerfaktor {opponent:.2f}")
    return " · ".join(labels)


def combo_preselection_bonus(player):
    """Allow strong verified chance creators into each team's player shortlist."""
    m=player.get("v2_metrics") or {}
    key="xg90" if player.get("sport")=="football" else "ixg60"
    x=m.get(key)
    return min(15.0,max(0.0,float(x))*10.0) if isinstance(x,(int,float)) and math.isfinite(x) else 0.0


def rank_candidates_by_verified_form(pool,day):
    """Select evidence-ranked green scorers, max two per fixture."""
    teams={}
    for original in pool:
        player=enriched_player(original)
        try:
            if datetime.fromisoformat(player["kickoff"])<=datetime.now(TZ): continue
        except (KeyError,ValueError,TypeError): continue
        team_key=(player["league"],player["fixture"],str(player.get("team_id") or player["team"]))
        teams.setdefault(team_key,[]).append(player)
    football_forms={}
    evaluated=[]
    for team_key,players in teams.items():
        for player in sorted(players,key=lambda p:(p.get("p") or 0) + combo_preselection_bonus(p),reverse=True)[:12]:
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
            adjusted=(player.get("p") if player.get("v2_model") else adjusted_goal_probability(player,stats))
            if adjusted is None or probability_tier(adjusted,player["sport"])!="high":
                continue
            score=form_score(stats,player["sport"])
            evaluated.append({**player,"form":stats,"form_score":score,"adjusted_p":adjusted,"evidence_score":combo_evidence_score(player,stats)})
    evaluated.sort(key=lambda p:(p["adjusted_p"] * 0.55 + p["evidence_score"] * 0.85,p["adjusted_p"],p["form_score"]),reverse=True)
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


def combo_player_details(player,day,uid):
    """Inline player drill-down without navigating away from the coupon."""
    if st.button("📊 Spielerhistorie & Aufstellung öffnen",key=f"profile_{uid}"):
        state=f"sr_profile_{uid}"
        st.session_state[state]=not st.session_state.get(state,False)
    if not st.session_state.get(f"sr_profile_{uid}"):
        return
    st.markdown('<div class="sr-combo-profile"><b>📊 Spielerprofil · Form & Mannschaft</b></div>',unsafe_allow_html=True)
    stats=player.get("form") or player_form_details(player,"football" if player.get("sport")=="football" else ("del" if player.get("league")=="DEL" else "nhl"),day)
    show_player(player,"1. Halbzeit" if player.get("sport")=="football" else "1. Drittel", "football" if player.get("sport")=="football" else ("del" if player.get("league")=="DEL" else "nhl"),stats,True)
    st.caption(f"Saisonhistorie: {player.get('games',0)} Spiele · {player.get('goals',0)} Tore · {player.get('shots') if player.get('shots') is not None else '–'} Schüsse")
    if player.get("sport")=="football":
        fid=player.get("fixture")
        try: fid=int(fid)
        except (TypeError,ValueError): fid=None
        if fid:
            st.markdown("**👥 Aufstellungen der Begegnung**")
            st.caption("Bestätigte Elf, falls vom Anbieter verfügbar; andernfalls statistische Erwartung aus früheren Aufstellungen.")
            key=secret("API_SPORTS_KEY")
            if key:
                rows=football_confirmed_lineup(fid,key)
                if rows:
                    for team in rows:
                        team_name=(team.get("team") or {}).get("name") or "Mannschaft"
                        st.success(f"Bestätigt: {team_name} · {team.get('formation') or 'Formation unbekannt'}")
                        st.write(", ".join((item.get("player") or {}).get("name","?") for item in team.get("startXI") or []))
                elif player.get("team_id"):
                    if st.button("🔎 Voraussichtliche Elf berechnen",key=f"expected_combo_{uid}"):
                        expected=football_expected_lineup(player["team_id"],day,key)
                        if expected:
                            st.info(f"Statistische Startelf aus {expected['samples']} früheren Aufstellungen · Formation {expected.get('formation') or 'unbekannt'}")
                            st.write(", ".join(p["name"] for p in expected["players"]))
                            st.caption("Verletzungen, Sperren und Rotation können die Erwartung verändern.")
                        else: st.warning("Zu wenige Aufstellungsdaten verfügbar.")
    else:
        st.caption("Für NHL/DEL stehen hier Spielerhistorie und Form zur Verfügung. Verifizierte Spielaufstellungen sind nicht für jede Begegnung abrufbar.")


def combo_portrait(player):
    url=safe_logo(player.get("photo"))
    if not url and player.get("sport")=="football" and player.get("player_id"):
        try:
            pid=int(player["player_id"])
            if pid>0: url=f"https://media.api-sports.io/football/players/{pid}.png"
        except (TypeError,ValueError): pass
    return url


def render_form_combo(picks, view_key="default"):
    if not picks:
        st.info("Keine grünen Torschützen-Kandidaten mit verifizierter Form und Spielzeit gefunden. Es werden keine Tipps ergänzt.")
        return
    st.success(f"{len(picks)} grüne Torschützen-Tipps mit überprüfbarer aktueller Form aus {len({(p['league'],p['fixture']) for p in picks})} Begegnungen.")
    for index,original in enumerate(picks,1):
        p=enriched_player(original)
        form=p["form"]
        avg_minutes=(form.get("minutes") or 0)/form["played"]
        unit="Eiszeit" if p["sport"]=="hockey" else "Spielzeit"
        if p["sport"]=="football":
            count=form.get("rating_count",0)
            rating=form.get("rating_sum",0)/count if count else None
            label="API-Football Ø-Note"
        else:
            rating=nhl_own_form_grade(form)
            count=form["played"]
            label="SportRadar-Formindex"
        grade_color=("green" if rating is not None and rating>=8 else "yellow" if rating is not None and rating>=6 else "red" if rating is not None else "unknown")
        rating_text=f"{rating:.1f}".replace(".",",") if rating is not None else "–"
        photo=combo_portrait(p)
        avatar=(f'<img src="{html.escape(photo,quote=True)}" alt="Spielerfoto" loading="lazy" onerror="this.style.display=\'none\';this.parentElement.innerHTML=\'👤\'">' if photo else '👤')
        name=html.escape(str(p.get("name") or "Unbekannt"))
        team=html.escape(str(p.get("team") or "–"))
        league=html.escape(str(p.get("league") or "–"))
        st.markdown(f'''<div class="sr-combo-spotlight">
          <div class="sr-combo-avatar">{avatar}</div>
          <div class="sr-combo-identity"><div class="sr-combo-name"><span class="sr-combo-rank">{index}</span> {name}</div>
          <div class="sr-combo-league">{league} <span>·</span> {team}</div></div>
          <div class="sr-combo-mini-grade sr-grade-{grade_color}"><small>🔥 {label}</small><strong>{rating_text}<em>/10</em></strong><small>{count} bewertete Einsätze</small></div>
        </div>''',unsafe_allow_html=True)
        period_name="1. Halbzeit" if p["sport"]=="football" else "1. Drittel"
        period_value=p.get("half")
        period_detail=f" · {period_name}: {pct(period_value)}" if period_value is not None else ""
        st.markdown(f'<div class="sr-combo-probs"><div><small>{period_name}</small><strong>{pct(period_value)}</strong></div><div><small>Gesamtspiel</small><strong>{pct(p["adjusted_p"])}</strong></div></div>',unsafe_allow_html=True)
        st.caption(f'🕒 Spielbeginn {datetime.fromisoformat(p["kickoff"]).strftime("%H:%M")} Uhr · {p["match"]} · Gesamtspiel (formangepasst): {pct(p["adjusted_p"])} · Saisonmodell: {pct(p["p"])}{period_detail}')
        st.caption(f'🏒 Letzte {form["played"]} Einsätze: {form["goals"]} Tore · {form["shots"]} Schüsse · Ø {avg_minutes:.1f} Min. {unit} · Position: {p.get("position") or "Unbekannt"}')
        st.markdown(spotlight_metrics(p, p["sport"], form), unsafe_allow_html=True)
        if p.get("v2_model"): st.caption("📊 Datenbank 2.0 · " + p["v2_model"] + " · Quelle: " + p.get("v2_source", "unbekannt"))
        if p.get("v2_as_of"): st.caption("🗓️ Statistikstand: " + p["v2_as_of"])
        st.caption("📊 Auswahlfaktoren: " + combo_evidence_caption(p,form))
        favorite_button(p,f"combo_{view_key}_{index}_{p.get('league')}")
        combo_player_details(p,datetime.fromisoformat(p["kickoff"]).date(),f"{view_key}_{index}_{p.get('league')}_{p.get('player_id') or normalize_team(p['name'])}")
    st.metric("Ausgewählte Tipps",len(picks))
    if len(picks)>1:
        chance=100*math.prod(p["adjusted_p"]/100 for p in picks)
        st.metric("Rechnerische Kombi-Chance (heuristisch)",pct(chance))
    st.warning("Auswahl nach Tor-Modell, xG/ixG (falls vorhanden), Schüssen, aktueller Form und Einsatzzeit; Gegnerfaktor nur bei vorhandenen Daten. Grün ist keine Wettempfehlung. Die rechnerische Kombi-Chance nimmt Unabhängigkeit an und ist nicht kalibriert.")


def render_combo_picks(picks,requested):
    if not picks:
        st.info("Keine geeigneten Begegnungen mit ausreichenden Spielerdaten gefunden.")
        return
    if len(picks)<requested:
        st.warning(f"Nur {len(picks)} unterschiedliche geeignete Spiele gefunden. Es werden keine Tipps erfunden.")
    for i,original in enumerate(picks,1):
        player=enriched_player(original)
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
            ["⚽ Fußball – alle 10 Ligen", "🏒 Eishockey – NHL + DEL"],
            index=0 if sport.startswith("⚽") else 1,
            key="daily_all_leagues_sport",
        )
        mode="football" if sport_mode.startswith("⚽") else "hockey"
        amount=st.select_slider("Gewünschte Anzahl Tipps",options=[6,7,8,9,10],value=7,key="daily_all_leagues_amount")
        st.caption(f"{day.strftime('%d.%m.%Y')} · Alle Ligen der gewählten Sportart · Torschütze im Gesamtspiel")
        st.caption("Nur grüne Kandidaten mit überprüfbarer Form aus bis zu 20 Einsätzen; maximal zwei Tipps pro Begegnung.")
        request=(str(day),mode)
        if st.button("📅 Form-Tages-Kombi berechnen",key=f"daily_all_{day}"):
            st.session_state["daily_all_request"]=request
        if st.session_state.get("daily_all_request")==request:
            with st.spinner("Alle Ligen und aktuelle Spielerform auswerten …"):
                ranked=multi_league_form_combo(day,mode)
            if len(ranked)<amount:
                st.warning(f"Nur {len(ranked)} geeignete grüne Tipps gefunden; keine Tipps werden erfunden.")
            render_form_combo(ranked[:amount], "daily")
    with tab_all:
        st.caption(f"{day.strftime('%d.%m.%Y')} · Alle geeigneten Begegnungen · Höchste grüne Torprognose aus den Top 12 jeder Mannschaft")
        st.caption("Bewertet werden echte letzte bis zu 20 Einsätze inklusive Tore, Schüsse und Spielzeit/Eiszeit. Nur grüne Tipps; maximal zwei je Begegnung.")
        st.caption("DEL wird berücksichtigt, sobald der tägliche DEL-Formdaten-Abruf erfolgreich war.")
        if st.button("🔥 Große Form-Kombi für diesen Tag berechnen",key=f"form_{day}"):
            st.session_state["form_day"]=str(day)
        if st.session_state.get("form_day")==str(day):
            with st.spinner("Echte Einzelspiel-Statistiken abrufen und Form bewerten … Dies kann mehrere Minuten dauern und API-Kontingent verbrauchen."):
                picks=all_leagues_form_combo(day)
            render_form_combo(picks, "all")
    with tab_mixed:
        st.markdown("**⚽🏒 Mixed Tages-Kombi: Fußball + Eishockey aus allen 12 Wettbewerben**")
        mixed_amount=st.select_slider(
            "Anzahl Mixed-Tipps",options=[6,7,8,9,10],value=7,key="mixed_daily_amount"
        )
        st.caption(f"{day.strftime('%d.%m.%Y')} · 10 Fußballwettbewerbe + NHL + DEL · Nur Spiele an diesem Tag")
        st.caption("Nur grüne Torschützen mit überprüfbarer Form, maximal zwei je Begegnung. Fußball und Eishockey werden gemeinsam nach angepasster Torprognose sortiert.")
        if st.button("⚽🏒 Mixed Tages-Kombi berechnen",key=f"mixed_day_{day}"):
            st.session_state["mixed_form_day"]=str(day)
        if st.session_state.get("mixed_form_day")==str(day):
            with st.spinner("Alle 12 Wettbewerbe und die letzten bis zu 20 Einsätze prüfen …"):
                ranked=multi_league_form_combo(day,"mixed")
            if len(ranked)<mixed_amount:
                st.warning(f"Nur {len(ranked)} geeignete grüne Tipps verfügbar; keine Tipps werden ergänzt.")
            render_form_combo(ranked[:mixed_amount], "mixed")
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


# Live scoreboard: fetch fresh results separately from the daily fixture snapshot.
@st.cache_data(ttl=45, show_spinner=False)
def live_football_fixtures(league_id, year, date, key):
    return api("fixtures", {"league": league_id, "season": year, "date": date,
                            "timezone": "Europe/Berlin"}, key=key)


@st.cache_data(ttl=60, show_spinner=False)
def live_football_scorers(fixture_id, key):
    rows=api("fixtures/events", {"fixture": fixture_id}, key=key)
    if not isinstance(rows,list): return None
    goals=[]
    for row in rows:
        if row.get("type")!="Goal": continue
        detail=str(row.get("detail") or "")
        if detail.lower() in ("missed penalty", "penalty missed"): continue
        person=(row.get("player") or {}).get("name") or "Unbekannt"
        team=(row.get("team") or {}).get("name") or ""
        minute=(row.get("time") or {}).get("elapsed")
        extra=(row.get("time") or {}).get("extra")
        clock=f"{minute}+{extra}'" if extra else f"{minute}'" if minute is not None else ""
        label=" (Eigentor)" if "own goal" in detail.lower() else " (Elfmeter)" if "penalty" in detail.lower() else ""
        goals.append(f"⚽ {clock} {person} · {team}{label}")
    return goals


@st.cache_data(ttl=45, show_spinner=False)
def live_nhl_scores(date):
    return nhl("score/"+date)


@st.cache_data(ttl=60, show_spinner=False)
def live_nhl_scorers(game_id):
    payload=nhl(f"gamecenter/{game_id}/landing")
    if not isinstance(payload,dict): return None
    scoring=((payload.get("summary") or {}).get("scoring") or [])
    out=[]
    for period in scoring:
        number=(period.get("periodDescriptor") or {}).get("number")
        for goal in period.get("goals") or []:
            scorer=goal.get("name") or goal.get("scorerName") or ""
            if isinstance(scorer,dict): scorer=scorer.get("default") or ""
            if not scorer:
                scorer=((goal.get("scorer") or {}).get("name") if isinstance(goal.get("scorer"),dict) else "") or "Unbekannt"
            time=goal.get("timeInPeriod") or ""
            team=goal.get("teamAbbrev") or ""
            out.append(f"🏒 {number or '?'}D {time} · {scorer} ({team})")
    return out


@st.cache_data(ttl=45, show_spinner=False)
def live_del_games(date, key, league_id):
    return api("games", {"league": league_id, "date": date,
                         "timezone": "Europe/Berlin"}, provider="hockey", key=key)


@st.cache_data(ttl=60,show_spinner=False)
def live_football_events(fixture_id,key):
    rows=api("fixtures/events",{"fixture":fixture_id},key=key)
    return rows if isinstance(rows,list) else None

@st.cache_data(ttl=90,show_spinner=False)
def live_football_statistics(fixture_id,key):
    rows=api("fixtures/statistics",{"fixture":fixture_id},key=key)
    return rows if isinstance(rows,list) else None


def sr_live_card(home,away,score,state,running=False,finished=False,home_logo=None,away_logo=None):
    kind="running" if running else "finished" if finished else "upcoming"
    st.markdown(f"""<div class='sr-game sr-game-{kind}'>
      <div class='sr-game-head'><span>{'🔴 LIVE' if running else '✅ ENDE' if finished else '🕒 GEPLANT'}</span><span>{html.escape(str(state))}</span></div>
      <div class='sr-game-main'><div class='sr-game-team'>{logo_html(home_logo,44)}<span>{html.escape(str(home))}</span></div>
      <div class='sr-game-result'>{html.escape(str(score))}</div>
      <div class='sr-game-team'>{logo_html(away_logo,44)}<span>{html.escape(str(away))}</span></div></div></div>""",unsafe_allow_html=True)


def sr_event_text(event):
    kind=str(event.get('type') or '')
    detail=str(event.get('detail') or '')
    clock=event.get('time') or {}
    minute=clock.get('elapsed'); extra=clock.get('extra')
    time=f"{minute}+{extra}'" if extra else f"{minute}'" if minute is not None else '–'
    player=(event.get('player') or {}).get('name') or 'Unbekannt'
    assistant=(event.get('assist') or {}).get('name')
    team=(event.get('team') or {}).get('name') or ''
    symbol={'Goal':'⚽','Card':'🟨','subst':'🔄','Var':'📺'}.get(kind,'•')
    if 'Red' in detail: symbol='🟥'
    if kind=='Goal' and 'Missed' in detail: symbol='❌'
    description=f'{symbol} {time}  {player} · {team}'
    if kind=='subst' and assistant: description+=f' → {assistant}'
    if detail and detail not in ('Normal Goal','Yellow Card','Substitution 1','Substitution 2','Substitution 3'): description+=f' · {detail}'
    return description


def sr_football_stats(fixture_id,key):
    rows=live_football_statistics(fixture_id,key)
    if not rows or len(rows)<2:
        st.info('Spielstatistiken vom Anbieter derzeit nicht verfügbar.'); return
    home={str(x.get('type')):x.get('value') for x in rows[0].get('statistics') or []}
    away={str(x.get('type')):x.get('value') for x in rows[1].get('statistics') or []}
    for label,source in [('Ballbesitz','Ball Possession'),('Schüsse','Total Shots'),('Schüsse aufs Tor','Shots on Goal'),('Ecken','Corner Kicks'),('Fouls','Fouls'),('Erwartete Tore (xG)','expected_goals')]:
        a=home.get(source); b=away.get(source)
        if a is None and b is None: continue
        try:
            va=float(str(a or 0).replace('%','')); vb=float(str(b or 0).replace('%',''))
        except (TypeError,ValueError): continue
        share=va/(va+vb) if va+vb>0 else .5
        st.markdown(f'<div class="sr-stat"><div><b>{html.escape(str(a if a is not None else "–"))}</b><span>{html.escape(label)}</span><b>{html.escape(str(b if b is not None else "–"))}</b></div><div class="sr-stat-track"><i style="width:{share*100:.1f}%"></i></div></div>',unsafe_allow_html=True)


def sr_football_detail(game,key,day):
    fixture=game.get('fixture') or {}; fixture_id=fixture.get('id')
    teams=game.get('teams') or {}; home=teams.get('home') or {}; away=teams.get('away') or {}
    goals=game.get('goals') or {}; status=fixture.get('status') or {}
    short=status.get('short') or 'NS'; running=short in ('1H','2H','HT','ET','BT','P','LIVE','INT')
    finished=short in ('FT','AET','PEN')
    score=f"{goals.get('home') if goals.get('home') is not None else '–'} : {goals.get('away') if goals.get('away') is not None else '–'}"
    state=f"{status.get('elapsed')}'" if running and status.get('elapsed') is not None else status.get('long') or short
    sr_live_card(home.get('name','Heim'),away.get('name','Gast'),score,state,running,finished,home.get('logo'),away.get('logo'))
    if not fixture_id: return
    tab1,tab2,tab3=st.tabs(['⚡ Live-Ticker','📊 Statistiken','👥 Aufstellungen'])
    with tab1:
        events=live_football_events(fixture_id,key) if running or finished else []
        if events is None: st.info('Live-Ereignisse nicht abrufbar.')
        elif not events: st.caption('Noch keine gemeldeten Spielereignisse.')
        else:
            for event in sorted(events,key=lambda x:((x.get('time') or {}).get('elapsed') or 0,(x.get('time') or {}).get('extra') or 0),reverse=True):
                st.markdown('<div class="sr-ticker-item">'+html.escape(sr_event_text(event))+'</div>',unsafe_allow_html=True)
    with tab2: sr_football_stats(fixture_id,key)
    with tab3:
        display_football_lineup(fixture_id,home.get('name','Heim'),away.get('name','Gast'),key,home.get('id'),away.get('id'),day)


def live_view(day):
    st.markdown('<div class="sr-hero"><strong>🔴 LIVE CENTER</strong><small>Spielstände · Ticker · Statistiken · Aufstellungen</small></div>',unsafe_allow_html=True)
    selected=st.multiselect('Ligen',list(LEAGUES)+['NHL','DEL'],default=list(LEAGUES)+['NHL','DEL'],key='live_leagues')
    filter_choice=st.segmented_control('Spielstatus',['Alle','Live','Beendet','Geplant'],default='Alle',key='live_status')
    if st.button('🔄 Live-Daten aktualisieren',key='live_refresh',type='primary'):
        live_football_fixtures.clear(); live_football_events.clear(); live_football_statistics.clear()
        live_nhl_scores.clear(); live_nhl_scorers.clear(); live_del_games.clear()
        st.rerun()
    st.caption('Live-Daten beim Öffnen und nach Aktualisierung · API-Verfügbarkeit abhängig vom Anbieter')
    date=day.isoformat(); key=secret('API_SPORTS_KEY'); found=0
    for league in selected:
        if league in LEAGUES:
            if not key: st.warning('API_SPORTS_KEY fehlt.'); break
            games=live_football_fixtures(LEAGUES[league],season(day,league),date,key)
            if games is None: st.warning(f'{league}: Daten nicht verfügbar.'); continue
            eligible=[]
            for g in games:
                status=((g.get('fixture') or {}).get('status') or {}).get('short')
                running=status in ('1H','2H','HT','ET','BT','P','LIVE','INT')
                finished=status in ('FT','AET','PEN')
                if filter_choice=='Live' and not running: continue
                if filter_choice=='Beendet' and not finished: continue
                if filter_choice=='Geplant' and (running or finished): continue
                eligible.append(g)
            if not eligible: continue
            with st.expander(f'⚽ {league}  ·  {len(eligible)} Spiele',expanded=True):
                for game in sorted(eligible,key=lambda x:(x.get('fixture') or {}).get('timestamp') or 0):
                    t=game.get('teams') or {}; home=(t.get('home') or {}).get('name','Heim'); away=(t.get('away') or {}).get('name','Gast')
                    with st.expander(f'🏟️ {home} – {away}',expanded=False):
                        sr_football_detail(game,key,day)
                    found+=1
        elif league=='NHL':
            payload=live_nhl_scores(date)
            if not isinstance(payload,dict): st.warning('NHL-Daten nicht verfügbar.'); continue
            games=[]
            for game in payload.get('games') or []:
                state=str(game.get('gameState') or '').upper(); running=state in ('LIVE','CRIT'); finished=state in ('FINAL','OFF')
                if filter_choice=='Live' and not running or filter_choice=='Beendet' and not finished or filter_choice=='Geplant' and (running or finished): continue
                games.append((game,running,finished))
            if not games: continue
            with st.expander(f'🏒 NHL  ·  {len(games)} Spiele',expanded=True):
                for game,running,finished in games:
                    home=game.get('homeTeam') or {}; away=game.get('awayTeam') or {}
                    with st.expander(f'{nhl_team_name(home)} – {nhl_team_name(away)}',expanded=False):
                        hs=home.get('score'); ass=away.get('score')
                        sr_live_card(nhl_team_name(home),nhl_team_name(away),f"{hs if hs is not None else '–'} : {ass if ass is not None else '–'}",'Live' if running else 'Ende' if finished else 'Geplant',running,finished,home.get('logo'),away.get('logo'))
                        t1,t2=st.tabs(['🏒 Tor-Ticker','📊 Spielinformationen'])
                        with t1:
                            goals=live_nhl_scorers(game['id']) if game.get('id') and (running or finished) else []
                            if goals:
                                for item in goals: st.markdown('<div class="sr-ticker-item">'+html.escape(item)+'</div>',unsafe_allow_html=True)
                            else: st.caption('Keine bestätigten Torschützen verfügbar.')
                        with t2:
                            st.caption('Detaillierte NHL-Spielstatistiken hängen von der Live-Datenquelle ab.')
                    found+=1
        else:
            if not key: st.warning('API_SPORTS_KEY fehlt.'); continue
            games=live_del_games(date,key,secret('DEL_LEAGUE_ID') or '19')
            if games is None: st.warning('DEL-Daten nicht verfügbar.'); continue
            valid=[]
            for g in games:
                raw=g.get('status') or {}; status=str(raw.get('short') or raw.get('long') or '') if isinstance(raw,dict) else str(raw)
                running=status.upper() in ('1P','2P','3P','OT','PEN','LIVE'); finished=status.upper() in ('FT','AOT','AP','FINAL','FINISHED')
                if filter_choice=='Live' and not running or filter_choice=='Beendet' and not finished or filter_choice=='Geplant' and (running or finished): continue
                valid.append((g,status,running,finished))
            if not valid: continue
            with st.expander(f'🏒 DEL  ·  {len(valid)} Spiele',expanded=True):
                for game,status,running,finished in valid:
                    teams=game.get('teams') or {}; home=teams.get('home') or {}; away=teams.get('away') or {}
                    scores=game.get('scores') or {}
                    hs=(scores.get('home') or {}).get('total') if isinstance(scores.get('home'),dict) else scores.get('home')
                    ass=(scores.get('away') or {}).get('total') if isinstance(scores.get('away'),dict) else scores.get('away')
                    with st.expander(f"{home.get('name','Heim')} – {away.get('name','Gast')}",expanded=False):
                        sr_live_card(home.get('name','Heim'),away.get('name','Gast'),f"{hs if hs is not None else '–'} : {ass if ass is not None else '–'}",status or 'Geplant',running,finished,home.get('logo'),away.get('logo'))
                        st.caption('DEL-Torschützen und Einzelspielstatistiken nur bei verlässlicher Verfügbarkeit.')
                    found+=1
    if not found: st.info('Keine passenden Spiele für den ausgewählten Filter.')

st.markdown("""<style>
/* Screenshot-inspired SportRadar stadium / neon interface */
[data-testid="stAppViewContainer"]{background:radial-gradient(ellipse 90% 230px at 50% 0%,#0870b8 0%,#073467 35%,#04162f 80%,#03122b 100%)!important;color:#f8fbff!important}
[data-testid="stHeader"]{background:#03132a88!important}
.block-container{max-width:1000px!important;padding-top:.6rem!important}
.sr-stadium-header{padding:24px 14px 20px;margin:-8px -6px 15px;border-radius:0 0 22px 22px;background:radial-gradient(ellipse at 52% 0%,#19b9ff88 0%,#0073c822 25%,transparent 70%),repeating-radial-gradient(ellipse at 50% -170px,transparent 0px,transparent 55px,#44cfff13 57px,#44cfff15 59px);border-bottom:1px solid #1682db66;box-shadow:0 10px 32px #00132866}
.sr-brand{font-size:clamp(2.1rem,7vw,3.1rem);font-weight:900;letter-spacing:-.04em;color:#fff;line-height:1.08;text-shadow:0 0 20px #0b92ff88}
.sr-subtitle{color:#9ad8ff;font-size:1rem;margin-top:4px}
.sr-header-icons{float:right;font-size:1.35rem;color:#d5edff;letter-spacing:.45rem;margin-top:8px}
.sr-hero{position:relative;background:linear-gradient(112deg,#bb003f 0%,#e90955 40%,#920e81 69%,#0757b5 100%)!important;border:2px solid #ff4885!important;border-right-color:#1cc8ff!important;border-radius:24px!important;box-shadow:0 0 18px #ff007a88,0 0 32px #057aff44!important;padding:25px 20px!important;margin:15px 0 22px!important}
.sr-hero strong{font-size:clamp(1.65rem,6vw,2.25rem)!important;letter-spacing:.015em}.sr-hero small{font-size:clamp(.84rem,3.3vw,1.05rem)!important;color:#fff!important;line-height:1.5}
[data-testid="stMultiSelect"] [data-baseweb="select"]>div{background:#e9f4ff!important;border:2px solid #1cbaff!important;border-radius:18px!important;padding:7px!important;box-shadow:0 0 16px #08b5ff55!important}
[data-testid="stMultiSelect"] [data-baseweb="tag"]{background:linear-gradient(120deg,#086ad0,#003c96)!important;border:1px solid #37bbff!important;border-radius:11px!important;min-height:35px!important;box-shadow:0 0 8px #057eff55}
[data-testid="stMultiSelect"] [data-baseweb="tag"] *{color:#fff!important;font-weight:700!important}
[data-testid="stMultiSelect"] label,[data-testid="stSegmentedControl"] label{font-size:1.02rem!important;color:#fff!important}
[data-testid="stSegmentedControl"]{border:1px solid #24b7ff;border-radius:14px;overflow:hidden;box-shadow:0 0 13px #008aff66}
[data-testid="stSegmentedControl"] button{background:#e8f5ff!important;color:#083365!important;font-weight:800!important;min-height:45px}
[data-testid="stSegmentedControl"] button[aria-checked="true"], [data-testid="stSegmentedControl"] button[aria-pressed="true"]{background:#092354!important;color:#fff!important;box-shadow:inset 0 -4px #ff1d72!important}
.stButton>button{border-radius:14px!important;background:linear-gradient(115deg,#006be6,#004aab)!important;border:2px solid #21c8ff!important;color:#fff!important;font-weight:800!important;box-shadow:0 0 13px #007bff66!important;min-height:43px}
.stButton>button[kind="primary"]{background:linear-gradient(110deg,#fa0878,#ff5261)!important;border:1px solid #ff5c9a!important;box-shadow:0 0 18px #ff157b66!important}
[data-testid="stExpander"]{border:1px solid #1174dc!important;background:#061f46!important;border-radius:20px!important;box-shadow:0 0 12px #006cff33!important}
[data-testid="stExpander"] summary{background:linear-gradient(95deg,#092b61,#083c80)!important;border-bottom:1px solid #125ba7!important;min-height:54px!important}
[data-testid="stExpander"] summary p{color:#fff!important;font-weight:800!important}
.sr-live-card,.sr-game{background:#092b5b!important;border:1px solid #168eff!important;border-radius:15px!important;color:#fff!important;box-shadow:0 0 9px #0077ff44!important}
.sr-game-result,.sr-live-score{background:#04162f!important;color:#fff!important;border:1px solid #2376b8!important}
.sr-live-team,.sr-live-state,.sr-live-scorer,.sr-game-team{color:#f5faff!important}
.sr-live-scorer,.sr-ticker-item{background:#0c3a71!important;color:#f3faff!important}
[data-testid="stRadio"] [role="radiogroup"]{gap:.45rem!important}
[data-testid="stRadio"] label:has(input:checked){background:linear-gradient(115deg,#e40065,#a4007a)!important;border-color:#ff4999!important;box-shadow:0 0 13px #ff147a66!important}
[data-testid="stRadio"] [role="radiogroup"] label{border:1px solid #247ad4;border-radius:13px;padding:7px 11px;background:#082b5b;color:#fff!important}
[data-testid="stRadio"] [role="radiogroup"] label p{color:#fff!important;font-weight:750!important}
[data-testid="stSelectbox"] [data-baseweb="select"]>div{background:#e9f4ff!important;border:1px solid #1aa8ff!important;color:#062c58!important}
[data-testid="stSelectbox"] [data-baseweb="select"] *{color:#062c58!important}
[data-testid="stCaptionContainer"]{color:#a8d9ff!important}
.player{background:linear-gradient(140deg,#0b336a,#08234b)!important;border:1px solid #1884d8!important;border-left:5px solid #10c59d!important}
.player .prob{background:#104e74!important;border:1px solid #2187af!important}.player .prob strong{color:#69fbd1!important}
.sr-combo-profile{background:#092b57!important;border-color:#1488d3!important}
@media(max-width:480px){.sr-header-icons{font-size:1rem;letter-spacing:.15rem}.sr-stadium-header{padding:17px 8px}.sr-hero{padding:21px 16px!important}.block-container{padding-left:.6rem!important;padding-right:.6rem!important}}
</style>""",unsafe_allow_html=True)
st.markdown('<div class="sr-stadium-header"><div class="sr-header-icons">⌕ ♧ ◉</div><div class="sr-brand">SportRadar 👑</div><div class="sr-subtitle">Deine Sport-Prognose App</div></div>',unsafe_allow_html=True)


st.caption("🇩🇪 Deutsche Zeit · Saison automatisch · Statistische Torprognosen")
page=st.radio("Bereich",["🔴 Live-Ergebnisse","🎯 Torprognosen","🎟️ Kombi & Prüfung","⭐ Favoriten","📊 Statistik-Datenbank"],horizontal=True)
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
if page.startswith("📊"):
    from sport_database import dashboard
    dashboard()
elif page.startswith("⭐"):
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
elif page.startswith("🔴"):
    live_view(day)
elif sport.startswith("🏒"):
    if league=="NHL": nhl_view(day)
    else: del_view(day)
else: football_view(day,league)
st.divider()
st.caption("Alle Prozentwerte sind Modellschätzungen, keine Garantien oder Wettquoten. Aufstellung, Verletzungen, Gegnerstärke, Eiszeit und kleine Stichproben sind nicht vollständig berücksichtigt.")

st.markdown("<style>"+'\n/* Kompakte Form-Kombi: Portrait und Spielername statt übergroßer Formbox */\n.sr-combo-spotlight{display:flex;align-items:center;gap:12px;padding:12px;margin:16px 0 8px;border:1px solid #1688d9;border-radius:17px;background:linear-gradient(115deg,#0b2b52,#071a35);box-shadow:0 4px 18px #001b}\n.sr-combo-avatar{width:78px;height:85px;flex:0 0 78px;border-radius:12px;display:flex;align-items:center;justify-content:center;background:#173f65;font-size:2rem;overflow:hidden;color:#b9eaff}\n.sr-combo-avatar img{width:100%;height:100%;object-fit:contain;object-position:center bottom}\n.sr-combo-identity{flex:1;min-width:0}\n.sr-combo-name{color:#fff;font-weight:900;font-size:clamp(1.22rem,4.8vw,1.9rem);line-height:1.15;overflow-wrap:anywhere}\n.sr-combo-rank{display:inline-flex;align-items:center;justify-content:center;background:#15b86c;color:#fff;border-radius:50%;font-size:.78rem;width:24px;height:24px;vertical-align:middle}\n.sr-combo-league{color:#64ffcd;font-weight:850;font-size:clamp(.98rem,3.6vw,1.25rem);margin-top:8px;overflow-wrap:anywhere}\n.sr-combo-league span{color:#9dbad6}\n.sr-combo-mini-grade{flex:0 0 115px;max-width:115px;padding:8px;border:1px solid #087b79;border-radius:12px;background:#073b46;text-align:center;color:#e7fffa}\n.sr-combo-mini-grade small{display:block;font-size:.67rem;line-height:1.25}\n.sr-combo-mini-grade strong{display:block;color:#65ffd0;font-size:1.65rem;line-height:1.2;margin:5px 0}\n.sr-combo-mini-grade em{font-size:.7rem;font-style:normal;color:#d0f4eb}\n@media(max-width:480px){.sr-combo-spotlight{gap:8px;padding:9px}.sr-combo-avatar{width:60px;height:75px;flex-basis:60px}.sr-combo-mini-grade{flex-basis:87px;max-width:87px;padding:6px 3px}.sr-combo-mini-grade strong{font-size:1.35rem}.sr-combo-mini-grade small{font-size:.58rem}}\n'+"</style>",unsafe_allow_html=True)

# Einheitliche kompakte Karten für Prognosen und Kombiwetten.
st.markdown("""<style>
.sr-pred-compact{padding:12px!important;margin:10px 0!important;border-radius:17px!important}
.sr-pred-head{display:flex;align-items:center;gap:10px;margin-bottom:9px}
.sr-pred-photo{width:68px;height:72px;flex:0 0 68px;border-radius:11px;background:#173f65;display:flex;align-items:center;justify-content:center;overflow:hidden}
.sr-pred-photo img{width:100%;height:100%;object-fit:contain}
.sr-pred-identity{flex:1;min-width:0}
.sr-pred-identity .player-head{font-size:clamp(1.12rem,4.3vw,1.55rem)!important;line-height:1.18!important;color:#fff!important;font-weight:900!important}
.sr-pred-league{font-size:clamp(.84rem,3.2vw,1.03rem);font-weight:850;color:#63fbd1;margin-top:5px;overflow-wrap:anywhere}
.sr-pred-grade{flex:0 0 87px;background:#073b46;border:1px solid #0b817f;border-radius:11px;padding:7px 4px;text-align:center}
.sr-pred-grade small{display:block;color:#d8fff4;font-size:.61rem;line-height:1.25}
.sr-pred-grade strong{display:block;color:#68ffd0;font-size:1.3rem;margin-top:4px}
.sr-pred-grade em{font-size:.62rem;font-style:normal;color:#d4eaf1}
.sr-pred-compact .pair{gap:8px!important;margin:7px 0!important}
.sr-pred-compact .prob{padding:8px 6px!important;border-radius:11px!important}
.sr-pred-compact .prob strong{font-size:clamp(1.16rem,4.7vw,1.55rem)!important}
.sr-pred-compact .prob small{font-size:.75rem!important;color:#d8f2ff!important}
.sr-pred-chips .pill{font-size:.75rem!important;padding:4px 7px!important;margin:3px!important}
.sr-pred-compact .sr-form{margin-top:7px!important;padding:9px!important;font-size:.82rem!important}
.sr-pred-compact .sr-grade{padding:7px!important;margin:5px 0!important}
.sr-pred-compact .sr-grade-score{font-size:1.25rem!important}
@media(max-width:480px){.sr-pred-photo{width:55px;height:62px;flex-basis:55px}.sr-pred-head{gap:7px}.sr-pred-grade{flex-basis:77px}}
</style>""",unsafe_allow_html=True)

# Kompakte Formdarstellung, farbcodierte Bewertung und gut lesbare Chancen.
st.markdown("""<style>
.sr-pred-compact .sr-form-minimal{padding:5px 8px!important;margin:4px 0!important;border:0!important;background:#10364a!important;color:#d9f8f4!important;font-size:.72rem!important;line-height:1.4!important}
.sr-pred-grade.sr-grade-green,.sr-combo-mini-grade.sr-grade-green{border-color:#19c77d!important;background:#063e37!important}
.sr-pred-grade.sr-grade-green strong,.sr-combo-mini-grade.sr-grade-green strong{color:#5fffc2!important}
.sr-pred-grade.sr-grade-yellow,.sr-combo-mini-grade.sr-grade-yellow{border-color:#e9b83c!important;background:#483817!important}
.sr-pred-grade.sr-grade-yellow strong,.sr-combo-mini-grade.sr-grade-yellow strong{color:#ffdb78!important}
.sr-pred-grade.sr-grade-red,.sr-combo-mini-grade.sr-grade-red{border-color:#f06a66!important;background:#491f2b!important}
.sr-pred-grade.sr-grade-red strong,.sr-combo-mini-grade.sr-grade-red strong{color:#ff8e89!important}
.sr-combo-probs{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin:5px 0 7px}
.sr-combo-probs>div{background:#4d391a;border:1px solid #e5b84a;border-radius:11px;padding:7px 5px;text-align:center}
.sr-combo-probs small{display:block;color:#fff3d8;font-size:.78rem}
.sr-combo-probs strong{display:block;color:#ffe39b;font-size:1.35rem;line-height:1.35}
.sr-combo-spotlight{margin-bottom:5px!important}
</style>""",unsafe_allow_html=True)

st.markdown("""<style>
/* SportRadar mockup-inspired compact desktop and mobile cards */
.sr-daily-evidence{background:#0b4052;color:#c8f9ed;border:1px solid #1b9b9b;border-radius:12px;padding:9px 12px;margin-top:10px;font-size:.85rem;line-height:1.5}
.sr-pred-compact{background:linear-gradient(145deg,#08284e,#061a36)!important;border:1px solid #168dff!important;box-shadow:0 0 15px #007dff1c!important}
.sr-pred-compact .pair .prob{background:#082d4c!important;border:1px solid #188fdf!important}
.sr-pred-compact .player-head{font-weight:900!important}
.sr-combo-spotlight{border-color:#168dff!important}
@media(min-width:900px){.block-container{max-width:1320px!important}}
</style>""",unsafe_allow_html=True)

# Mobile-first: significantly smaller player cards; extended statistics remain accessible.
st.markdown("""<style>
.sr-pred-compact{padding:9px!important;margin:6px 0 9px!important;border-radius:13px!important}
.sr-pred-compact .sr-pred-head{gap:7px!important;margin-bottom:5px!important}
.sr-pred-compact .sr-pred-photo{width:46px!important;height:50px!important;flex:0 0 46px!important;border-radius:8px!important}
.sr-pred-compact .sr-pred-identity .player-head{font-size:clamp(.96rem,3.7vw,1.18rem)!important;line-height:1.15!important}
.sr-pred-compact .sr-pred-league{font-size:.72rem!important;margin-top:2px!important}
.sr-pred-compact .sr-pred-grade{flex:0 0 70px!important;padding:4px 3px!important;border-radius:8px!important}
.sr-pred-compact .sr-pred-grade small{font-size:.52rem!important;line-height:1.12!important}
.sr-pred-compact .sr-pred-grade strong{font-size:1.04rem!important;margin-top:2px!important}
.sr-pred-compact .pair{gap:6px!important;margin:5px 0!important}
.sr-pred-compact .prob{padding:5px 3px!important;border-radius:8px!important}
.sr-pred-compact .prob small{font-size:.67rem!important}
.sr-pred-compact .prob strong{font-size:clamp(1rem,4vw,1.3rem)!important}
.sr-pred-compact .sr-pred-chips{gap:3px!important;margin-top:4px!important}
.sr-pred-compact .sr-pred-chips .pill{font-size:.65rem!important;padding:2px 5px!important;margin:1px!important;border-radius:6px!important}
.sr-pred-details{margin-top:4px;border-top:1px solid #1b567e;padding-top:4px}
.sr-pred-details summary{cursor:pointer;list-style:none;color:#7cebd4;font-size:.73rem;font-weight:750;padding:3px 1px;user-select:none}
.sr-pred-details summary::-webkit-details-marker{display:none}
.sr-pred-details summary::after{content:'  ▾';color:#8dc9eb}
.sr-pred-details[open] summary::after{content:'  ▴'}
.sr-pred-detail-body{padding-top:4px}
.sr-pred-details .sr-metric-highlights{gap:5px!important;margin:5px 0!important}
.sr-pred-details .sr-metric-highlight{padding:6px 8px!important;border-width:1px!important;border-radius:8px!important;flex:1 1 115px!important}
.sr-pred-details .sr-metric-highlight small{font-size:.68rem!important}
.sr-pred-details .sr-metric-highlight strong{font-size:.94rem!important;margin-top:2px!important}
.sr-pred-details .sr-daily-evidence{padding:6px 8px!important;margin-top:6px!important;font-size:.73rem!important}
@media(max-width:480px){.sr-pred-compact{padding:8px!important}.sr-pred-compact .sr-pred-grade{flex-basis:64px!important}.sr-pred-compact .sr-pred-photo{width:42px!important;height:47px!important;flex-basis:42px!important}}
</style>""",unsafe_allow_html=True)
