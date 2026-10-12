"""SportRadar v2: normalized SQLite statistics and honest model comparisons."""
import csv
import io
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).resolve().parent / 'data' / 'sportradar_v2.sqlite3'

SCHEMA = '''
CREATE TABLE IF NOT EXISTS players (player_id TEXT PRIMARY KEY, name TEXT NOT NULL, sport TEXT NOT NULL CHECK(sport IN ('Fußball','NHL','DEL')), team TEXT NOT NULL, position TEXT, image_url TEXT);
CREATE TABLE IF NOT EXISTS games (game_id TEXT PRIMARY KEY, sport TEXT NOT NULL, start_utc TEXT NOT NULL, home_team TEXT, away_team TEXT, status TEXT);
CREATE TABLE IF NOT EXISTS player_games (player_id TEXT NOT NULL, game_id TEXT NOT NULL, minutes REAL, goals INTEGER, shots INTEGER, shots_on_target INTEGER, shots_in_box INTEGER, xg REAL, npxg REAL, ixg REAL, shot_attempts INTEGER, pp_minutes REAL, high_danger INTEGER, PRIMARY KEY(player_id,game_id));
CREATE TABLE IF NOT EXISTS player_metrics (player_id TEXT NOT NULL, as_of TEXT NOT NULL, sample TEXT NOT NULL CHECK(sample IN ('season','last20','last5','next')), npxg90 REAL, xg90 REAL, ixg60 REAL, shots90 REAL, shots_on_target90 REAL, shots_in_box90 REAL, shots_on_target_game REAL, attempts_game REAL, expected_minutes REAL, toi_game REAL, pp_toi_game REAL, high_danger_game REAL, team_xg REAL, penalty_taker INTEGER, pp1 INTEGER, opponent_factor REAL, source TEXT NOT NULL, PRIMARY KEY(player_id,as_of,sample));
CREATE TABLE IF NOT EXISTS odds (player_id TEXT NOT NULL, game_id TEXT NOT NULL, decimal_odds REAL NOT NULL, bookmaker TEXT, as_of TEXT NOT NULL, PRIMARY KEY(player_id,game_id,bookmaker));
CREATE TABLE IF NOT EXISTS import_log (imported_at TEXT NOT NULL, filename TEXT NOT NULL, row_count INTEGER NOT NULL);
'''
FIELDS = ['player_id','name','sport','team','position','image_url','as_of','sample','npxg90','xg90','ixg60','shots90','shots_on_target90','shots_in_box90','shots_on_target_game','attempts_game','expected_minutes','toi_game','pp_toi_game','high_danger_game','team_xg','penalty_taker','pp1','opponent_factor','source']
NUMERIC = set(FIELDS) - {'player_id','name','sport','team','position','image_url','as_of','sample','source'}


def connect():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.executescript(SCHEMA)
    return conn


def import_csv(contents, filename='statistik.csv'):
    reader=csv.DictReader(io.StringIO(contents.decode('utf-8-sig')))
    if not reader.fieldnames: raise ValueError('CSV hat keine Kopfzeile.')
    required={'player_id','name','sport','team','as_of','sample','source'}
    missing=required-set(reader.fieldnames)
    if missing: raise ValueError('Fehlende Spalten: '+', '.join(sorted(missing)))
    records=list(reader)
    for r in records:
        if r['sport'] not in ('Fußball','NHL','DEL'): raise ValueError('Ungültige Sportart: '+str(r['sport']))
        if r['sample'] not in ('season','last20','last5','next'): raise ValueError('Ungültiger Zeitraum: '+str(r['sample']))
        if not r['source'].strip(): raise ValueError('Datenquelle ist Pflicht.')
        datetime.fromisoformat(r['as_of'])
        for k in NUMERIC:
            if r.get(k) not in (None,''): r[k]=float(r[k].replace(',','.'))
    with connect() as conn:
        for r in records:
            conn.execute('INSERT INTO players(player_id,name,sport,team,position,image_url) VALUES(?,?,?,?,?,?) ON CONFLICT(player_id) DO UPDATE SET name=excluded.name,sport=excluded.sport,team=excluded.team,position=excluded.position,image_url=excluded.image_url', tuple(r.get(k) or None for k in ('player_id','name','sport','team','position','image_url')))
            cols=['player_id','as_of','sample']+[k for k in FIELDS if k not in ('player_id','name','sport','team','position','image_url','as_of','sample')]
            conn.execute('INSERT OR REPLACE INTO player_metrics ('+','.join(cols)+') VALUES ('+','.join('?' for _ in cols)+')',tuple(r.get(k) or None for k in cols))
        conn.execute('INSERT INTO import_log VALUES(?,?,?)',(datetime.now(timezone.utc).isoformat(),filename,len(records)))
    return len(records)


def sync_provider_csv():
    """Rehydrate SQLite from committed provider CSV after Streamlit Cloud restarts."""
    source=DB_PATH.parent/'advanced_player_metrics.csv'
    if not source.exists():return
    try:
        if DB_PATH.exists() and DB_PATH.stat().st_mtime_ns>=source.stat().st_mtime_ns:return
        import_csv(source.read_bytes(),source.name)
    except (OSError,ValueError,sqlite3.Error) as exc:
        print('Provider CSV import failed:',type(exc).__name__)


def load():
    sync_provider_csv()
    with connect() as conn:
        return pd.read_sql_query('''SELECT p.name,p.sport,p.team,p.position,p.image_url,m.* FROM player_metrics m JOIN players p USING(player_id) WHERE m.as_of=(SELECT MAX(x.as_of) FROM player_metrics x WHERE x.player_id=m.player_id AND x.sample=m.sample)''',conn)


def level(row):
    sport=row['sport']
    def get(k):
        v=row.get(k)
        return float(v) if pd.notna(v) else None
    if sport=='Fußball':
        x,shots,mins=get('npxg90'),get('shots90'),get('expected_minutes')
        if x is None: return ('Keine xG-Daten','#8593a7')
        if x>=.55 and (shots is None or shots>=3.5) and (mins is None or mins>=85): return ('Sehr stark','#17c784')
        if x>=.35 and (shots is None or shots>=2.5) and (mins is None or mins>=70): return ('Interessant','#f4bd49')
    else:
        x,shots,toi=get('ixg60'),get('shots_on_target_game'),get('toi_game')
        if x is None: return ('Keine ixG-Daten','#8593a7')
        if sport=='DEL': return ('DEL: separat bewerten','#94a3b8')
        if x>=1.2 and (shots is None or shots>=3.8) and (toi is None or toi>=20): return ('Sehr stark','#17c784')
        if x>=.8 and (shots is None or shots>=2.8) and (toi is None or toi>=17): return ('Interessant','#f4bd49')
    return ('Unter Richtwert','#ff7b7b')


def prediction(row):
    """Poisson baseline; do not silently impute missing xG or TOI."""
    def val(k):
        v=row.get(k)
        return float(v) if pd.notna(v) else None
    factor=val('opponent_factor')
    if factor is None: factor=1.0
    if not 0.5<=factor<=1.7: return None
    if row['sport']=='Fußball':
        xg=val('xg90')
        mins=val('expected_minutes')
        if xg is None or mins is None: return None
        lam=xg*mins/90*factor
    else:
        xg=val('ixg60')
        mins=val('toi_game')
        if xg is None or mins is None: return None
        lam=xg*mins/60*factor
    if not 0<=lam<=5: return None
    return 100*(-math.expm1(-lam)),lam


def fmt(v,unit='',digits=2):
    if v is None or pd.isna(v): return '—'
    return f'{float(v):.{digits}f}'.replace('.',',')+unit


def dashboard():
    st.subheader('📊 SportRadar Datenbank 2.0')
    st.caption('Echte Daten mit Quellenangabe · Saison / letzte 20 / letzte 5 Spiele · fehlende Werte bleiben leer')
    with st.expander('📥 Neue Statistikdaten importieren (CSV)',expanded=False):
        st.caption('CSV mit player_id, name, sport, team, as_of, sample und source. Weitere Statistikfelder sind optional. Importierte Daten liegen in einer lokalen SQLite-Datenbank; auf Streamlit Cloud sind sie ohne externe Speicherung nicht dauerhaft gesichert.')
        up=st.file_uploader('Statistik-CSV',type=['csv'],key='sr_v2_import')
        if up is not None and st.button('Daten importieren',key='sr_v2_do_import'):
            try:
                count=import_csv(up.getvalue(),up.name)
                st.success(f'{count} Datensätze importiert.');st.rerun()
            except Exception as exc: st.error(str(exc))
        st.download_button('📄 Leere CSV-Vorlage',(','.join(FIELDS)+'\n').encode(),file_name='sportradar_import_vorlage.csv',mime='text/csv')
    # Daily provider evidence is available even when premium xG is not licensed.
    daily_path=Path(__file__).resolve().parent/'data'/'daily_player_stats.json'
    if daily_path.exists():
        import json
        try: daily=json.loads(daily_path.read_text(encoding='utf-8'))
        except (ValueError,OSError): daily={}
        nhl_rows=[]
        for pid,entry in daily.get('nhl',{}).items():
            recent=entry.get('last5') or {}
            if not recent.get('games'):continue
            nhl_rows.append({'Spieler':entry.get('name'),'Team':entry.get('team'),'Letzte Spiele':recent.get('games'),'Tore':recent.get('goals'),'Schüsse':recent.get('shots'),'Schüsse/Spiel':recent.get('shots_on_target_game'),'Ø Eiszeit':recent.get('toi_game')})
        if nhl_rows:
            st.subheader('🏒 Täglich aktualisierte NHL-Spielerdaten')
            st.caption('Offizielle NHL-Spielprotokolle · '+str(daily.get('updated_at',''))[:16]+' UTC · Keine erfundenen ixG- oder Powerplay-Werte')
            st.dataframe(pd.DataFrame(nhl_rows).sort_values(['Tore','Schüsse'],ascending=False),hide_index=True,use_container_width=True)
    df=load()
    if df.empty:
        st.info('Die neue Datenbank ist angelegt, enthält aber noch keine verifizierten Spielerstatistiken. Importiere echte Daten per CSV. Es werden keine Beispielspieler als echte Prognosen angezeigt.')
        return
    a,b,c=st.columns(3)
    a.metric('Spieler',df.player_id.nunique());b.metric('Datensätze',len(df));c.metric('Ligen',df.sport.nunique())
    sport=st.selectbox('Sport / Liga',['Alle','Fußball','NHL','DEL'],key='sr_v2_sport')
    period=st.selectbox('Zeitraum',['season','last20','last5','next'],format_func=lambda v:{'season':'Ganze Saison','last20':'Letzte 20 Spiele','last5':'Letzte 5 Spiele','next':'Nächstes Spiel (Prognose)'}[v],key='sr_v2_period')
    filtered=df[df['sample']==period].copy()
    if sport!='Alle':filtered=filtered[filtered.sport==sport]
    if filtered.empty: st.info('Für diese Auswahl liegen noch keine Daten vor.');return
    filtered['rating']=filtered.apply(lambda r:level(r)[0],axis=1)
    filtered['chance']=filtered.apply(lambda r: prediction(r)[0] if prediction(r) else float('nan'),axis=1)
    filtered=filtered.sort_values('chance',ascending=False,na_position='last')
    st.caption('Farben = heuristische Vorfilter, keine kalibrierten Trefferwahrscheinlichkeiten. DEL braucht eigene Schwellenwerte.')
    for _,r in filtered.iterrows():
        label,color=level(r);prob=prediction(r)
        with st.container(border=True):
            x,y=st.columns([3,1]);x.markdown(f"**{r['name']}**  ");x.caption(f"{r['sport']} · {r['team']} · {r['position'] or 'Position unbekannt'}")
            y.markdown(f'<div style="background:{color};color:#061b2d;border-radius:10px;padding:7px;text-align:center;font-weight:800;font-size:12px">{label}</div>',unsafe_allow_html=True)
            if prob:st.metric('Geschätzte Chance auf mindestens 1 Tor',fmt(prob[0],'% ',1))
            else:st.caption('Torwahrscheinlichkeit: nicht berechenbar (xG/ixG oder erwartete Spielzeit fehlt)')
            if r['sport']=='Fußball':
                vals=[('Non-Penalty xG/90',r['npxg90']),('xG/90',r['xg90']),('Schüsse/90',r['shots90']),('Schüsse aufs Tor/90',r['shots_on_target90']),('Strafraum-Schüsse/90',r['shots_in_box90']),('Minuten',r['expected_minutes'])]
            else:
                vals=[('ixG/60',r['ixg60']),('Schüsse aufs Tor',r['shots_on_target_game']),('Versuche',r['attempts_game']),('Ø Eiszeit',r['toi_game']),('Powerplay-Min.',r['pp_toi_game']),('High-Danger',r['high_danger_game'])]
            cols=st.columns(3)
            for i,(name,value) in enumerate(vals):cols[i%3].metric(name,fmt(value))
            st.caption('Quelle: '+str(r['source'])+' · Stand: '+str(r['as_of']))
    st.subheader('🎟️ Kandidaten für Kombiwetten')
    st.caption('Nur Spieler mit vorhandener Torprognose und mindestens gelbem Richtwert. Quoten und positive Erwartungswerte sind ohne aktuelle Buchmacherquoten nicht berechenbar.')
    combo=filtered[(filtered['chance'].notna()) & (filtered['rating'].isin(['Interessant','Sehr stark']))].head(10)
    if combo.empty:st.info('Keine ausreichend belegten Kandidaten für diese Auswahl.')
    else:st.dataframe(combo[['name','sport','team','rating','chance','source']].rename(columns={'name':'Spieler','sport':'Liga','team':'Team','rating':'Einstufung','chance':'Tor-Chance (%)','source':'Quelle'}),hide_index=True,use_container_width=True)

# Shared prediction feed for existing goal cards and combo selection.
import unicodedata

def _norm(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',str(value or '').casefold()) if c.isalnum())

@st.cache_data(ttl=120,show_spinner=False)
def _prediction_rows(db_mtime):
    if not DB_PATH.exists():
        return []
    try:
        data=load()
        return data.to_dict('records')
    except (sqlite3.Error,ValueError):
        return []


def match_prediction(player):
    """Overlay a verified, matched, recent v2 Poisson estimate onto an existing candidate.

    A missing/ambiguous match or insufficient data leaves the original prediction intact.
    """
    sync_provider_csv()
    if not DB_PATH.exists():
        return player
    sport='Fußball' if player.get('sport')=='football' else ('DEL' if player.get('league')=='DEL' else 'NHL')
    try:
        rows=_prediction_rows(DB_PATH.stat().st_mtime_ns)
    except OSError:
        return player
    name=_norm(player.get('name'))
    team=_norm(player.get('team'))
    matched=[r for r in rows if r.get('sport')==sport and _norm(r.get('name'))==name and _norm(r.get('team'))==team and r.get('sample') in ('next','season')]
    if not matched:
        return player
    matched.sort(key=lambda r:(r.get('sample')=='next',str(r.get('as_of') or '')),reverse=True)
    best=matched[0]
    if len(matched)>1 and matched[0].get('sample')==matched[1].get('sample') and matched[0].get('as_of')==matched[1].get('as_of'):
        return player
    # Do not use a snapshot dated after the scheduled fixture.
    try:
        fixture=str(player.get('kickoff') or '')[:10]
        if fixture and str(best.get('as_of') or '')[:10]>fixture:
            return player
    except (TypeError,ValueError):
        return player
    result=prediction(best)
    if result is None:
        return player
    p,lam=result
    output=dict(player)
    output['p']=round(p,2)
    # The time split is a rough approximation, not an observed period xG model.
    share=0.45 if sport=='Fußball' else 1/3
    output['half']=round(100*(-math.expm1(-lam*share)),2)
    output['v2_model']='xG/Spielzeit-Modell (Poisson, Halbzeit/Drittel angenähert)'
    output['v2_source']=str(best.get('source') or '')
    output['v2_as_of']=str(best.get('as_of') or '')
    output['v2_metrics']={key:(None if pd.isna(best.get(key)) else best.get(key)) for key in ('npxg90','xg90','ixg60','shots90','shots_in_box90','shots_on_target90','shots_on_target_game','attempts_game','expected_minutes','toi_game','pp_toi_game','high_danger_game','team_xg','opponent_factor','penalty_taker','pp1')}
    if sport=='Fußball':
        output['xg']=float(best['xg90'])*float(best['expected_minutes'])/90
        if pd.notna(best.get('penalty_taker')):output['penalty_taker']=bool(best['penalty_taker'])
    else:
        output['minutes']=float(best['toi_game'])
        if pd.notna(best.get('pp_toi_game')):output['powerplay_minutes']=float(best['pp_toi_game'])
        if pd.notna(best.get('pp1')):output['pp1']=bool(best['pp1'])
    return output
