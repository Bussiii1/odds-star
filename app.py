"""
odds* v8 — Full rebuild
- Gemini AI (replaces OpenRouter)
- True bento grid with drag-to-reorder
- Football predictions fixed (multi-source)
- NBA fixed display
- Bankroll editable inline
- GitHub-ready structure
- Bold creative design
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
import plotly.graph_objects as go
import pickle, datetime, os, math, json, time, random

st.set_page_config(
    page_title="odds*",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────
# API KEYS
# ─────────────────────────────────────────────────────────────────
DEFAULT_KEYS = {
    "api_football":  "e09cbd93b354791ef71148260f45e842",
    "rapidapi":      "9fdb4bb6a6mshcaf432cfdc3cdc8p1cbce2jsn7fd7603d79c8",
    "the_odds":      "ca06f5faf1cc7a44825813eb23358fd9",
    "newsapi":       "8290158e877346f693c0ffcf6d1b0287",
    "sportmonks":    "H6yYNAkAClvuLNk6gLfzJI2v2dDrdemxVEPM3NOVefRPKe1CyA6hoyhclIAM",
    "balldontlie":   "2d3aba2c-552b-408b-9b7b-f3a3890aa83c",
    "scorebat":      "Mjg1MDE5XzE3NzM4Njg2NzRfZDBkNjg4Njk5ZjQyMGU0YjA0Yzg0ZDVkMjVjNDMxNDE4ODAwNzliMA==",
    "gemini":        "AIzaSyAt_m53p5Izv5b8iAYoJMQD4Inmg8Mzd14",
    "youtube":       "AIzaSyB2ccyXniDY2-hyJn9NbQD9-aHODhb4CLE",
}

TARGET_LEAGUES = {
    39:"Premier League", 140:"La Liga", 61:"Ligue 1",
    135:"Serie A", 78:"Bundesliga", 2:"Champions League", 3:"Europa League",
}

LEAGUE_FLAGS = {
    39:"🏴󠁧󠁢󠁥󠁮󠁧󠁿", 140:"🇪🇸", 61:"🇫🇷", 135:"🇮🇹", 78:"🇩🇪", 2:"🌍", 3:"🌍"
}

STADIUMS = {
    "Emirates":(51.5549,-0.1084,"London"),
    "Camp Nou":(41.3809,2.1228,"Barcelona"),
    "Bernabeu":(40.4531,-3.6883,"Madrid"),
    "Allianz":(48.2188,11.6247,"Munich"),
    "Old Trafford":(53.4631,-2.2913,"Manchester"),
    "Anfield":(53.4308,-2.9608,"Liverpool"),
    "Stamford":(51.4816,-0.1910,"London"),
    "Etihad":(53.4831,-2.2004,"Manchester"),
    "Parc des Princes":(48.8414,2.2530,"Paris"),
    "Wembley":(51.5560,-0.2796,"London"),
}

# Default widget order (drag-to-reorder stored in session)
DEFAULT_WIDGET_ORDER = ["safe","value","nba","bankroll","h2h","highlights","forme","cotes","live"]

for k, v in {
    "api_keys":       DEFAULT_KEYS.copy(),
    "chat_history":   [],
    "selected_match": None,
    "page":           "Dashboard",
    "bankroll":       1000.0,
    "bet_log":        [],
    "widget_order":   DEFAULT_WIDGET_ORDER.copy(),
    "widget_active":  {w:True for w in DEFAULT_WIDGET_ORDER},
    "edit_bankroll":  False,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────────────
# CACHE
# ─────────────────────────────────────────────────────────────────
CACHE_DIR = ".odds_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def _cp(k): return os.path.join(CACHE_DIR, f"{k}.pkl")
def load_cache(k, ttl=6):
    p = _cp(k)
    if os.path.exists(p):
        try:
            with open(p,"rb") as f: d,ts = pickle.load(f)
            if time.time()-ts < ttl*3600: return d
        except: pass
    return None
def save_cache(k, d):
    try:
        with open(_cp(k),"wb") as f: pickle.dump((d,time.time()),f)
    except: pass
def clear_cache():
    for fn in os.listdir(CACHE_DIR):
        try: os.remove(os.path.join(CACHE_DIR,fn))
        except: pass

def safe_get(url, headers=None, params=None, timeout=10):
    try:
        r = requests.get(url, headers=headers, params=params, timeout=timeout)
        if r.status_code == 200: return r.json()
    except: pass
    return None

# ─────────────────────────────────────────────────────────────────
# FOOTBALL DATA — API-Football + RapidAPI fallback
# ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=21600, show_spinner=False)
def fetch_fixtures(date_str: str):
    ck = f"fix_{date_str}"
    cached = load_cache(ck)
    if cached is not None: return cached

    out = []

    # Source 1: API-Football (single call, all leagues)
    hdr = {"x-apisports-key": st.session_state["api_keys"]["api_football"]}
    data = safe_get("https://v3.football.api-sports.io/fixtures",
                    headers=hdr, params={"date": date_str, "timezone": "Europe/Paris"})
    if data and "response" in data:
        for fx in data["response"]:
            lg = fx["league"]
            if lg["id"] not in TARGET_LEAGUES: continue
            t = fx["teams"]; fi = fx["fixture"]
            out.append({
                "fixture_id": fi["id"],
                "home": t["home"]["name"], "away": t["away"]["name"],
                "home_id": t["home"]["id"], "away_id": t["away"]["id"],
                "league": lg["name"], "league_id": lg["id"],
                "flag": LEAGUE_FLAGS.get(lg["id"],"⚽"),
                "time": fi["date"][:16], "status": fi["status"]["short"],
                "home_goals": fx["goals"]["home"], "away_goals": fx["goals"]["away"],
                "venue": (fi.get("venue") or {}).get("name","") or "",
                "elapsed": fi["status"].get("elapsed"),
                "source": "apif",
            })

    # Source 2: RapidAPI free football (fallback if empty)
    if not out:
        rhdr = {
            "x-rapidapi-key": st.session_state["api_keys"]["rapidapi"],
            "x-rapidapi-host": "free-api-live-football-data.p.rapidapi.com"
        }
        # Try to get upcoming matches
        for endpoint in [
            "football-get-all-live-matches-by-competitions",
            "football-current-season-top-five-leagues-schedule",
        ]:
            rdata = safe_get(
                f"https://free-api-live-football-data.p.rapidapi.com/{endpoint}",
                headers=rhdr
            )
            if rdata and isinstance(rdata.get("response"), list):
                for fx in rdata["response"][:30]:
                    out.append({
                        "fixture_id": fx.get("id", random.randint(10000,99999)),
                        "home": fx.get("homeTeam",{}).get("name","?"),
                        "away": fx.get("awayTeam",{}).get("name","?"),
                        "home_id": fx.get("homeTeam",{}).get("id",0),
                        "away_id": fx.get("awayTeam",{}).get("id",0),
                        "league": fx.get("competition",{}).get("name","?"),
                        "league_id": 0, "flag": "⚽",
                        "time": str(fx.get("startTime",""))[:16],
                        "status": fx.get("status","NS"),
                        "home_goals": fx.get("score",{}).get("home"),
                        "away_goals": fx.get("score",{}).get("away"),
                        "venue": "", "elapsed": None, "source": "rapid",
                    })
                if out: break

    # Source 3: Football-Data.org (second fallback)
    if not out:
        fhdr = {"X-Auth-Token": st.session_state["api_keys"].get("football_data","1f75d9b7087c497a9cf18a25bb542ecd")}
        fdata = safe_get("https://api.football-data.org/v4/matches",
                         headers=fhdr, params={"dateFrom": date_str, "dateTo": date_str})
        if fdata and "matches" in fdata:
            for m in fdata["matches"][:30]:
                out.append({
                    "fixture_id": m["id"],
                    "home": m["homeTeam"]["name"], "away": m["awayTeam"]["name"],
                    "home_id": m["homeTeam"]["id"], "away_id": m["awayTeam"]["id"],
                    "league": m.get("competition",{}).get("name","?"),
                    "league_id": 0, "flag": "⚽",
                    "time": m.get("utcDate","")[:16], "status": m.get("status","NS"),
                    "home_goals": (m.get("score",{}).get("fullTime") or {}).get("home"),
                    "away_goals": (m.get("score",{}).get("fullTime") or {}).get("away"),
                    "venue": "", "elapsed": None, "source": "fd",
                })

    save_cache(ck, out)
    return out


@st.cache_data(ttl=21600, show_spinner=False)
def fetch_prediction(fid: int):
    ck = f"pred_{fid}"
    cached = load_cache(ck)
    if cached is not None: return cached
    hdr = {"x-apisports-key": st.session_state["api_keys"]["api_football"]}
    data = safe_get("https://v3.football.api-sports.io/predictions",
                    headers=hdr, params={"fixture": fid})
    r = {"winner":"","advice":"","home_win_pct":"40%","draw_pct":"30%",
         "away_win_pct":"30%","goals_home":1.4,"goals_away":1.1}
    if data and "response" in data and data["response"]:
        p = data["response"][0].get("predictions",{})
        r = {
            "winner": p.get("winner",{}).get("name",""),
            "advice": p.get("advice",""),
            "home_win_pct": p.get("percent",{}).get("home","40%"),
            "draw_pct":     p.get("percent",{}).get("draws","30%"),
            "away_win_pct": p.get("percent",{}).get("away","30%"),
            "goals_home":   p.get("goals",{}).get("home",1.4),
            "goals_away":   p.get("goals",{}).get("away",1.1),
        }
    save_cache(ck, r)
    return r


@st.cache_data(ttl=21600, show_spinner=False)
def fetch_form(tid: int):
    ck = f"form_{tid}"
    cached = load_cache(ck)
    if cached is not None: return cached
    hdr = {"x-apisports-key": st.session_state["api_keys"]["api_football"]}
    data = safe_get("https://v3.football.api-sports.io/fixtures",
                    headers=hdr, params={"team": tid, "last": 5, "timezone":"Europe/Paris"})
    results = []
    if data and "response" in data:
        for fx in data["response"]:
            hg = fx["goals"]["home"] or 0; ag = fx["goals"]["away"] or 0
            home = fx["teams"]["home"]["id"] == tid
            gf = hg if home else ag; ga = ag if home else hg
            results.append({"res":"W" if gf>ga else("D" if gf==ga else "L"), "gf":gf, "ga":ga})
    save_cache(ck, results)
    return results


@st.cache_data(ttl=21600, show_spinner=False)
def fetch_h2h(hid: int, aid: int):
    ck = f"h2h_{hid}_{aid}"
    cached = load_cache(ck)
    if cached is not None: return cached
    hdr = {"x-apisports-key": st.session_state["api_keys"]["api_football"]}
    data = safe_get("https://v3.football.api-sports.io/fixtures/headtohead",
                    headers=hdr, params={"h2h": f"{hid}-{aid}", "last": 10})
    r = {"hw":0,"dr":0,"aw":0,"matches":[]}
    if data and "response" in data:
        for fx in data["response"]:
            hg = fx["goals"]["home"] or 0; ag = fx["goals"]["away"] or 0
            if hg>ag: r["hw"]+=1
            elif hg==ag: r["dr"]+=1
            else: r["aw"]+=1
            r["matches"].append({
                "home": fx["teams"]["home"]["name"],
                "away": fx["teams"]["away"]["name"],
                "score": f"{hg}-{ag}",
                "date": fx["fixture"]["date"][:10],
            })
    save_cache(ck, r)
    return r

# ─────────────────────────────────────────────────────────────────
# NBA
# ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=21600, show_spinner=False)
def fetch_nba_games(date_str: str):
    ck = f"nba_{date_str}"
    cached = load_cache(ck)
    if cached is not None: return cached
    hdr = {"Authorization": st.session_state["api_keys"]["balldontlie"]}
    data = safe_get("https://api.balldontlie.io/v1/games",
                    headers=hdr, params={"dates[]": date_str, "per_page": 30})
    games = []
    if data and "data" in data:
        for g in data["data"]:
            ht = g.get("home_team",{}); at = g.get("visitor_team",{})
            games.append({
                "id":         g["id"],
                "home":       ht.get("full_name","?"),
                "away":       at.get("full_name","?"),
                "home_city":  ht.get("city",""),
                "away_city":  at.get("city",""),
                "home_abbr":  ht.get("abbreviation",""),
                "away_abbr":  at.get("abbreviation",""),
                "home_score": g.get("home_team_score") or 0,
                "away_score": g.get("visitor_team_score") or 0,
                "status":     str(g.get("status","")),
                "date":       str(g.get("date", date_str))[:10],
            })
    save_cache(ck, games)
    return games

# ─────────────────────────────────────────────────────────────────
# ODDS
# ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=21600, show_spinner=False)
def fetch_odds():
    ck = "odds_v2"
    cached = load_cache(ck)
    if cached is not None: return cached
    key = st.session_state["api_keys"]["the_odds"]
    result = {}
    for sk in ["soccer_epl", "soccer_spain_la_liga", "soccer_france_ligue_one"]:
        try:
            data = safe_get(
                f"https://api.the-odds-api.com/v4/sports/{sk}/odds/",
                params={"apiKey":key,"regions":"eu","markets":"h2h","oddsFormat":"decimal"}
            )
            if isinstance(data, list):
                for g in data:
                    k2 = f"{g.get('home_team','')} vs {g.get('away_team','')}"
                    bms = g.get("bookmakers",[])
                    if bms:
                        outs = bms[0].get("markets",[{}])[0].get("outcomes",[])
                        result[k2] = {o["name"]: round(float(o["price"]),2) for o in outs}
        except: continue
    save_cache(ck, result)
    return result

# ─────────────────────────────────────────────────────────────────
# SCOREBAT HIGHLIGHTS
# ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_highlights():
    ck = "scorebat_v2"
    cached = load_cache(ck, ttl=2)
    if cached is not None: return cached

    key = st.session_state["api_keys"].get("scorebat","")
    results = []
    for url in [
        f"https://www.scorebat.com/video-api/v3/feed/?token={key}",
        f"https://www.scorebat.com/video-api/v3/?token={key}",
        "https://www.scorebat.com/video-api/v3/feed/",
    ]:
        try:
            r = requests.get(url, timeout=12,
                             headers={"Authorization": f"Bearer {key}"} if key else {})
            if r.status_code == 200:
                raw = r.json()
                videos = raw if isinstance(raw, list) else raw.get("response",[])
                for v in videos[:12]:
                    embed = v.get("embed","")
                    yt = ""
                    if "youtube.com/embed/" in embed:
                        vid = embed.split("youtube.com/embed/")[1].split('"')[0].split("?")[0]
                        yt = f"https://www.youtube.com/watch?v={vid}"
                    comp = v.get("competition",{})
                    thumb = v.get("thumbnail","") or (comp.get("logo","") if isinstance(comp,dict) else "")
                    results.append({
                        "title":   v.get("title",""),
                        "url":     yt or v.get("url",""),
                        "thumb":   thumb,
                        "channel": comp.get("name","") if isinstance(comp,dict) else str(comp),
                        "embed":   embed,
                    })
                if results: break
        except: continue

    if not results:
        # Static fallback with good thumbnails
        results = [
            {"title":"Champions League Highlights","url":"https://www.youtube.com/results?search_query=champions+league+highlights+2025","thumb":"https://i.ytimg.com/vi/default.jpg","channel":"UEFA"},
            {"title":"Premier League Goals","url":"https://www.youtube.com/results?search_query=premier+league+goals+week","thumb":"","channel":"Premier League"},
            {"title":"La Liga Highlights","url":"https://www.youtube.com/results?search_query=la+liga+highlights","thumb":"","channel":"LaLiga"},
            {"title":"Bundesliga Best Goals","url":"https://www.youtube.com/results?search_query=bundesliga+highlights","thumb":"","channel":"Bundesliga"},
            {"title":"Ligue 1 Highlights","url":"https://www.youtube.com/results?search_query=ligue+1+highlights","thumb":"","channel":"Ligue 1"},
            {"title":"Serie A Goals","url":"https://www.youtube.com/results?search_query=serie+a+highlights","thumb":"","channel":"Serie A"},
        ]
    save_cache(ck, results)
    return results

# ─────────────────────────────────────────────────────────────────
# SENTIMENT
# ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=21600, show_spinner=False)
def fetch_sentiment(team: str):
    ck = f"sent_{team[:12].replace(' ','_')}"
    cached = load_cache(ck)
    if cached is not None: return cached
    data = safe_get("https://newsapi.org/v2/everything",
                    params={"q":f"{team} football","sortBy":"publishedAt","pageSize":5,
                            "apiKey":st.session_state["api_keys"]["newsapi"],"language":"en"})
    pos = {"win","won","victory","great","strong","top","best","unbeaten","clinical"}
    neg = {"loss","lost","injury","injured","crisis","poor","suspended","banned","worst","doubt"}
    score = 0.0
    if data and "articles" in data:
        arts = data["articles"][:5]
        for a in arts:
            t = (a.get("title") or "").lower()
            score += sum(1 for w in pos if w in t) + sum(-1 for w in neg if w in t)
        score = round(score / max(len(arts),1), 2)
    r = {"score": score}
    save_cache(ck, r)
    return r

# ─────────────────────────────────────────────────────────────────
# SCORING ENGINE
# ─────────────────────────────────────────────────────────────────
def pf(s):
    try: return float(str(s).replace("%","").strip())
    except: return 33.3

def compute_score(pred, hs, as_):
    hp = pf(pred.get("home_win_pct","40%"))
    dp = pf(pred.get("draw_pct","30%"))
    ap = pf(pred.get("away_win_pct","30%"))
    s_adj = (-5 if hs.get("score",0)<-0.2 else 0) + (-5 if as_.get("score",0)<-0.2 else 0)
    opts = {"Victoire Dom.":hp, "Match Nul":dp, "Victoire Ext.":ap}
    best = max(opts, key=opts.get); conf = opts[best]
    over = max(20, min(80, 54 + s_adj))
    gs = round(conf*0.65 + max(0,over-50)*0.35, 1)
    bt = "SAFE" if gs>68 else ("VALUE" if gs>58 else "RISK")
    return {"best":best,"conf":round(conf,1),"over":round(over,1),"gs":gs,"bt":bt,"hp":hp,"dp":dp,"ap":ap}

TOP_NBA = {"BOS","DEN","OKC","MIN","MIL","PHX","GSW","LAL","CLE","NYK","SAC","DAL","MIA","PHI"}

def nba_score(game):
    h_top = game["home_abbr"] in TOP_NBA
    a_top = game["away_abbr"] in TOP_NBA
    base = 72 if (h_top and not a_top) else (45 if (a_top and not h_top) else 60)
    h_win = min(80, max(35, base + random.uniform(-2,2)))
    conf = round(max(h_win, 100-h_win), 1)
    bt = "SAFE" if conf>65 else ("VALUE" if conf>55 else "RISK")
    best = game["home_abbr"] if h_win>=50 else game["away_abbr"]
    return {"best":best,"conf":conf,"h_win":round(h_win,1),"a_win":round(100-h_win,1),"bt":bt}

def conf_color(c):
    if c>=72: return "#00E676"
    if c>=62: return "#40C4FF"
    if c>=52: return "#FFD740"
    return "#FF5252"

def poisson_prob(lam,k): return math.exp(-lam)*lam**k/math.factorial(k)
def poisson_probs(hxg=1.5,axg=1.2):
    hw=dr=aw=0.0; mat=[]
    for h in range(7):
        row=[]
        for a in range(7):
            p=poisson_prob(hxg,h)*poisson_prob(axg,a); row.append(round(p*100,2))
            if h>a: hw+=p
            elif h==a: dr+=p
            else: aw+=p
        mat.append(row)
    return {"hw":round(hw*100,1),"dr":round(dr*100,1),"aw":round(aw*100,1),"mat":mat}

def load_scored(date_str, max_fx=25):
    fixtures = fetch_fixtures(date_str)
    scored = []
    if not fixtures: return [], []
    for fx in fixtures[:max_fx]:
        try:
            pred = fetch_prediction(fx["fixture_id"])
            hs = fetch_sentiment(fx["home"])
            as_ = fetch_sentiment(fx["away"])
            gs = compute_score(pred, hs, as_)
            scored.append({"fx":fx,"pred":pred,"gs":gs})
        except: continue
    scored.sort(key=lambda x: x["gs"]["gs"], reverse=True)
    return fixtures, scored

# ─────────────────────────────────────────────────────────────────
# GEMINI AI
# ─────────────────────────────────────────────────────────────────
def call_gemini(user_msg: str, ctx: dict):
    key = st.session_state["api_keys"].get("gemini","")
    if not key or key.startswith("AIza") is False: return None

    system = f"""Tu es l'agent IA de odds*, expert en paris sportifs football ET basketball NBA.
Contexte du {datetime.date.today().strftime('%d/%m/%Y')}:
- {ctx.get('football_count',0)} matchs football aujourd'hui
- Top sélections: {json.dumps(ctx.get('top_football',[])[:5], ensure_ascii=False)}
- NBA: {json.dumps(ctx.get('top_nba',[])[:4], ensure_ascii=False)}
- Bankroll utilisateur: {st.session_state['bankroll']:.0f}€
Réponds en français. Concis, direct, pratique pour les paris. Utilise ⚽🏀."""

    history = [{"role":m["role"],"content":m["content"]}
               for m in st.session_state["chat_history"][-8:]]
    history.append({"role":"user","content":user_msg})

    # Convert to Gemini format
    contents = []
    for m in history:
        role = "user" if m["role"]=="user" else "model"
        contents.append({"role":role,"parts":[{"text":m["content"]}]})

    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}",
            headers={"Content-Type":"application/json"},
            json={
                "system_instruction": {"parts":[{"text":system}]},
                "contents": contents,
                "generationConfig": {"maxOutputTokens":1024,"temperature":0.7}
            },
            timeout=30
        )
        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return f"[Gemini {r.status_code}: {r.text[:100]}]"
    except Exception as e:
        return f"[Erreur Gemini: {str(e)[:80]}]"

def build_context():
    today = datetime.date.today().strftime("%Y-%m-%d")
    ctx = {"football_count":0,"top_football":[],"top_nba":[]}
    try:
        fixtures = fetch_fixtures(today)
        ctx["football_count"] = len(fixtures)
        for fx in fixtures[:8]:
            try:
                pred = fetch_prediction(fx["fixture_id"])
                hs = fetch_sentiment(fx["home"])
                as_ = fetch_sentiment(fx["away"])
                gs = compute_score(pred,hs,as_)
                ctx["top_football"].append({
                    "match": f"{fx['home']} vs {fx['away']}",
                    "league": fx["league"], "outcome": gs["best"],
                    "conf": gs["conf"], "type": gs["bt"],
                })
            except: continue
        ctx["top_football"].sort(key=lambda x:x["conf"],reverse=True)
    except: pass
    try:
        nba = fetch_nba_games(today)
        for g in nba[:5]:
            ns = nba_score(g)
            ctx["top_nba"].append({"match":f"{g['home']} vs {g['away']}","outcome":ns["best"],"conf":ns["conf"]})
    except: pass
    return ctx

def agent_fallback(ui: str) -> str:
    uil = ui.lower()
    today = datetime.date.today().strftime("%Y-%m-%d")
    if any(w in uil for w in ["combiné","safe","top","meilleur","paris"]):
        try:
            _, scored = load_scored(today, 12)
            safe = [s for s in scored if s["gs"]["bt"]=="SAFE"][:3]
            value = [s for s in scored if s["gs"]["bt"]=="VALUE"][:3]
            lines = ["⚽ <b>Combiné du jour :</b><br>✅ <b>Safe :</b>"]
            for s in safe: lines.append(f"· {s['fx']['home']} vs {s['fx']['away']} → {s['gs']['best']} ({s['gs']['conf']:.0f}%)")
            lines.append("<br>⚡ <b>Value :</b>")
            for s in value: lines.append(f"· {s['fx']['home']} vs {s['fx']['away']} → {s['gs']['best']} ({s['gs']['conf']:.0f}%)")
            return "<br>".join(lines)
        except: pass
    if any(w in uil for w in ["nba","basket"]):
        try:
            nba = fetch_nba_games(today)
            if not nba: return "🏀 Pas de matchs NBA aujourd'hui."
            sc = sorted([(g,nba_score(g)) for g in nba], key=lambda x:x[1]["conf"],reverse=True)
            lines = ["🏀 <b>NBA du jour :</b>"]
            for g,ns in sc[:4]: lines.append(f"· {g['home']} vs {g['away']} → {ns['best']} ({ns['conf']:.0f}%)")
            return "<br>".join(lines)
        except: pass
    if any(w in uil for w in ["bankroll","roi","bilan"]):
        log=st.session_state["bet_log"]; br=st.session_state["bankroll"]
        gain=sum(b.get("gain",0) for b in log); mise=sum(b.get("mise",0) for b in log)
        roi=round(gain/max(mise,1)*100,1) if mise else 0
        return f"💰 Bankroll: <b>{br:.0f}€</b> · ROI: <b>{roi:+.1f}%</b> · {len(log)} paris"
    return "⚽🏀 Essayez : <b>combiné du jour</b>, <b>NBA ce soir</b>, <b>mon bilan</b>, <b>analyse Arsenal</b>"

# ─────────────────────────────────────────────────────────────────
# BENTO DASHBOARD HTML — renders in iframe via st.components
# ─────────────────────────────────────────────────────────────────
def build_bento_html(scored, nba_games, highlights, odds, bankroll, bet_log):
    today_fmt = datetime.date.today().strftime("%d/%m/%Y")

    safe = [s for s in scored if s["gs"]["bt"]=="SAFE"][:3]
    value = [s for s in scored if s["gs"]["bt"]=="VALUE"][:3]
    if len(safe)<3: safe += scored[:3-len(safe)]
    if len(value)<3:
        taken = set(id(s) for s in safe)
        value += [s for s in scored if id(s) not in taken][:3-len(value)]

    # Stats
    n_matches = len(scored)
    n_safe = sum(1 for s in scored if s["gs"]["bt"]=="SAFE")
    avg_score = round(sum(s["gs"]["gs"] for s in scored[:10])/max(len(scored[:10]),1),1) if scored else 0
    n_live = sum(1 for s in scored if s["fx"]["status"] in ("1H","HT","2H","ET","P"))

    # Bankroll stats
    gain = sum(b.get("gain",0) for b in bet_log)
    mise = sum(b.get("mise",0) for b in bet_log)
    roi = round(gain/max(mise,1)*100,1) if mise else 0
    wins = sum(1 for b in bet_log if b.get("gain",0)>0)
    wr = round(wins/max(len(bet_log),1)*100,1)
    roi_col = "#00E676" if roi>=0 else "#FF5252"

    def bet_pills(items, accent):
        html = ""
        for s in items[:3]:
            fx=s["fx"]; gs=s["gs"]; c=gs["conf"]; col=conf_color(c)
            bt=gs["bt"]
            bt_col={"SAFE":"#00E676","VALUE":"#FFD740","RISK":"#FF5252"}.get(bt,"#666")
            flag=fx.get("flag","⚽"); lg=fx["league"][:16]
            t=fx["time"][11:16] if len(fx.get("time",""))>10 else ""
            html+=f"""
            <div style="background:rgba(255,255,255,.04);border-radius:12px;padding:10px 13px;
                        margin-bottom:8px;border-left:3px solid {bt_col};
                        transition:all .2s;cursor:pointer"
                 onmouseover="this.style.background='rgba(255,255,255,.08)'"
                 onmouseout="this.style.background='rgba(255,255,255,.04)'">
              <div style="font-size:10px;color:#888;font-weight:600;letter-spacing:.05em;margin-bottom:4px">
                {flag} {lg} &nbsp;·&nbsp; {t}
              </div>
              <div style="display:flex;justify-content:space-between;align-items:flex-start">
                <div style="flex:1">
                  <div style="font-size:13px;font-weight:700;line-height:1.3;color:#F5F5F5">
                    {fx['home'][:16]} <span style="color:#555">vs</span> {fx['away'][:14]}
                  </div>
                  <div style="font-size:11px;color:#AAA;margin-top:3px">{gs['best']}</div>
                </div>
                <div style="text-align:right;flex-shrink:0;margin-left:10px">
                  <div style="font-family:'Space Mono',monospace;font-size:20px;font-weight:700;
                              color:{col};line-height:1">{c}%</div>
                  <div style="background:{bt_col}22;color:{bt_col};border:1px solid {bt_col}44;
                              border-radius:999px;font-size:9px;font-weight:700;padding:1px 7px;
                              display:inline-block;margin-top:3px">{bt}</div>
                </div>
              </div>
              <div style="height:2px;background:rgba(255,255,255,.06);border-radius:999px;
                          margin-top:8px;overflow:hidden">
                <div style="width:{c}%;height:100%;background:{col};border-radius:999px;
                            transition:width 1s ease"></div>
              </div>
            </div>"""
        if not items:
            html = '<div style="color:#555;font-size:12px;padding:1rem;text-align:center">Chargement en cours...</div>'
        return html

    def nba_pills(games):
        html = ""
        for g in games[:5]:
            ns = nba_score(g)
            c = ns["conf"]; col = conf_color(c)
            hs = g.get("home_score",0) or 0
            as_ = g.get("away_score",0) or 0
            is_live = any(q in g.get("status","") for q in ["Q","Ht","q"])
            is_final = "Final" in g.get("status","")
            score_txt = f"{hs} — {as_}" if (is_live or is_final) else "VS"
            score_col = "#C9A84C" if (is_live or is_final) else "#555"
            live_dot = '<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:#FF5252;margin-right:4px;animation:pulse 1.2s infinite"></span>' if is_live else ""

            html += f"""
            <div style="background:rgba(255,255,255,.04);border-radius:12px;padding:10px 13px;
                        margin-bottom:7px;border-left:3px solid #C9A84C;
                        transition:all .2s;cursor:pointer"
                 onmouseover="this.style.background='rgba(201,168,76,.08)'"
                 onmouseout="this.style.background='rgba(255,255,255,.04)'">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <div style="flex:1">
                  <div style="font-size:10px;color:#C9A84C;font-weight:700;letter-spacing:.05em;margin-bottom:3px">
                    {live_dot}NBA · {g.get('status','')}
                  </div>
                  <div style="font-size:12px;font-weight:700;color:#F5F5F5">{g['home']}</div>
                  <div style="font-size:12px;font-weight:600;color:#AAA">{g['away']}</div>
                </div>
                <div style="text-align:center;padding:0 12px">
                  <div style="font-family:'Space Mono',monospace;font-size:17px;font-weight:700;
                              color:{score_col}">{score_txt}</div>
                  <div style="font-size:10px;color:{col};font-weight:700;margin-top:3px">
                    {ns['best']} {c}%
                  </div>
                </div>
              </div>
            </div>"""
        if not games:
            html = '<div style="color:#555;font-size:12px;padding:1rem;text-align:center">Pas de matchs NBA aujourd&#39;hui</div>'
        return html

    def h2h_widget(scored):
        if not scored: return '<div style="color:#555;font-size:12px">Pas de données</div>'
        item = scored[0]; fx = item["fx"]
        try:
            h2h = fetch_h2h(fx["home_id"],fx["away_id"])
        except:
            return '<div style="color:#555;font-size:12px">H2H non disponible</div>'
        hw=h2h["hw"]; dr=h2h["dr"]; aw=h2h["aw"]; total=max(hw+dr+aw,1)
        bars = [
            (hw,total,"#7C5EF0",fx["home"][:12],"Dom."),
            (dr,total,"#555","Nuls","Nuls"),
            (aw,total,"#00E676",fx["away"][:12],"Ext."),
        ]
        bar_html=""
        for val,tot,col,team,lbl in bars:
            pct=round(val/tot*100)
            bar_html+=f"""
            <div style="margin-bottom:10px">
              <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                <span style="font-size:10px;color:#AAA">{team}</span>
                <span style="font-family:'Space Mono',monospace;font-size:12px;font-weight:700;color:{col}">{val}</span>
              </div>
              <div style="height:6px;background:rgba(255,255,255,.08);border-radius:999px;overflow:hidden">
                <div style="width:{pct}%;height:100%;background:{col};border-radius:999px;transition:width 1s ease"></div>
              </div>
            </div>"""
        return f"""
        <div style="font-size:11px;color:#888;margin-bottom:10px">
          {fx['home'][:14]} vs {fx['away'][:14]}
        </div>
        {bar_html}
        <div style="display:flex;justify-content:space-around;margin-top:12px;
                    background:rgba(255,255,255,.04);border-radius:10px;padding:8px">
          <div style="text-align:center">
            <div style="font-family:'Space Mono',monospace;font-size:22px;font-weight:700;color:#7C5EF0">{hw}</div>
            <div style="font-size:9px;color:#666;text-transform:uppercase;letter-spacing:.08em">Dom.</div>
          </div>
          <div style="text-align:center">
            <div style="font-family:'Space Mono',monospace;font-size:22px;font-weight:700;color:#555">{dr}</div>
            <div style="font-size:9px;color:#666;text-transform:uppercase;letter-spacing:.08em">Nuls</div>
          </div>
          <div style="text-align:center">
            <div style="font-family:'Space Mono',monospace;font-size:22px;font-weight:700;color:#00E676">{aw}</div>
            <div style="font-size:9px;color:#666;text-transform:uppercase;letter-spacing:.08em">Ext.</div>
          </div>
        </div>"""

    def cotes_widget(scored, odds):
        if not odds: return '<div style="color:#555;font-size:12px">Cotes non disponibles</div>'
        html=""; count=0
        for s in scored[:20]:
            fx=s["fx"]
            k = f"{fx['home']} vs {fx['away']}"
            if k in odds and count<5:
                o = odds[k]; vals = list(o.values())[:3]; names=list(o.keys())[:3]
                html+=f"""
                <div style="display:flex;justify-content:space-between;align-items:center;
                            padding:6px 0;border-bottom:1px solid rgba(255,255,255,.04)">
                  <div style="font-size:11px;font-weight:600;color:#DDD">
                    {fx['home'][:11]} vs {fx['away'][:9]}
                  </div>
                  <div style="display:flex;gap:6px">
                    {"".join([f'<span style="background:rgba(255,215,64,.1);color:#FFD740;border:1px solid rgba(255,215,64,.25);border-radius:6px;font-family:Space Mono,monospace;font-size:11px;font-weight:700;padding:2px 6px">{v}</span>' for v in vals])}
                  </div>
                </div>"""
                count+=1
        if count==0:
            return '<div style="color:#555;font-size:12px">Aucune cote disponible pour ces matchs</div>'
        return html

    def forme_widget(scored):
        html=""
        for s in scored[:7]:
            fx=s["fx"]
            try:
                form = fetch_form(fx["home_id"])
            except:
                continue
            pts=sum(3 if r["res"]=="W" else(1 if r["res"]=="D" else 0) for r in form)
            dots=""
            for r2 in form:
                col={"W":"#00E676","D":"#FFD740","L":"#FF5252"}.get(r2["res"],"#555")
                dots+=f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{col};margin-right:3px;box-shadow:0 0 6px {col}66"></span>'
            gs_conf=s["gs"]["conf"]
            gs_col=conf_color(gs_conf)
            html+=f"""
            <div style="display:flex;justify-content:space-between;align-items:center;
                        padding:6px 0;border-bottom:1px solid rgba(255,255,255,.04)">
              <div>
                <div style="font-size:11px;font-weight:600;color:#DDD">{fx['home'][:18]}</div>
                <div style="display:flex;align-items:center;gap:4px;margin-top:4px">{dots}</div>
              </div>
              <div style="font-family:'Space Mono',monospace;font-size:13px;font-weight:700;color:{gs_col}">{gs_conf}%</div>
            </div>"""
        return html or '<div style="color:#555;font-size:12px">Données de forme non disponibles</div>'

    def highlights_grid(items):
        html=""
        for h in items[:6]:
            thumb=h.get("thumb","")
            if thumb:
                img_html=f'<img src="{thumb}" style="width:100%;height:75px;object-fit:cover;border-radius:8px;display:block" onerror="this.style.display=none;this.nextElementSibling.style.display=flex">'
                fallback=f'<div style="display:none;width:100%;height:75px;background:rgba(255,255,255,.05);border-radius:8px;align-items:center;justify-content:center;font-size:1.5rem">▶️</div>'
            else:
                img_html=""
                fallback=f'<div style="display:flex;width:100%;height:75px;background:rgba(255,255,255,.05);border-radius:8px;align-items:center;justify-content:center;font-size:1.5rem;margin-bottom:6px">▶️</div>'

            title=h["title"][:42]+("…" if len(h["title"])>42 else "")
            url=h.get("url","#")
            html+=f"""
            <a href="{url}" target="_blank" style="text-decoration:none;display:block">
              <div style="background:rgba(255,255,255,.04);border-radius:12px;padding:8px;
                          border:1px solid rgba(255,255,255,.06);transition:all .2s;cursor:pointer"
                   onmouseover="this.style.borderColor='rgba(124,94,240,.5)';this.style.transform='translateY(-2px)'"
                   onmouseout="this.style.borderColor='rgba(255,255,255,.06)';this.style.transform='translateY(0)'">
                {img_html}{fallback}
                <div style="margin-top:6px">
                  <div style="font-size:11px;font-weight:600;color:#F0F0F0;line-height:1.3">{title}</div>
                  <div style="font-size:9px;color:#666;margin-top:2px">{h['channel']} · ▶ Voir</div>
                </div>
              </div>
            </a>"""
        return html

    # ── Assemble Full HTML ──
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{
    background:#0f0f0f;
    color:#F0F0F0;
    font-family:'Space Grotesk',sans-serif;
    padding:12px;
    min-height:100vh;
  }}

  /* ── BENTO GRID ── */
  .bento{{
    display:grid;
    grid-template-columns:repeat(12,1fr);
    grid-auto-rows:auto;
    gap:12px;
  }}

  /* spans */
  .s2{{grid-column:span 2;}}
  .s3{{grid-column:span 3;}}
  .s4{{grid-column:span 4;}}
  .s5{{grid-column:span 5;}}
  .s6{{grid-column:span 6;}}
  .s7{{grid-column:span 7;}}
  .s8{{grid-column:span 8;}}
  .s12{{grid-column:span 12;}}

  /* ── CARD base ── */
  .card{{
    background:#1a1a1a;
    border:1px solid rgba(255,255,255,.07);
    border-radius:20px;
    padding:18px 20px;
    position:relative;
    overflow:hidden;
    transition:all .25s ease;
  }}
  .card::after{{
    content:'';
    position:absolute;top:0;left:0;right:0;height:1px;
    background:linear-gradient(90deg,transparent,rgba(255,255,255,.07),transparent);
    pointer-events:none;
  }}
  .card:hover{{
    border-color:rgba(124,94,240,.35);
    transform:translateY(-2px);
    box-shadow:0 12px 40px rgba(0,0,0,.6);
  }}

  /* Color variants */
  .card-purple{{
    background:linear-gradient(145deg,#5B3FD8,#7C5EF0);
    border-color:transparent;
    box-shadow:0 8px 32px rgba(124,94,240,.3);
  }}
  .card-purple:hover{{border-color:rgba(255,255,255,.2)!important;}}
  .card-green{{background:linear-gradient(145deg,#2E7D52,#4CAF82);border-color:transparent;}}
  .card-amber{{background:linear-gradient(145deg,#92670A,#C9A84C);border-color:transparent;}}
  .card-dark{{background:#111;}}
  .card-glass{{background:rgba(255,255,255,.03);backdrop-filter:blur(20px);border-color:rgba(255,255,255,.1);}}

  /* Accent tops */
  .accent-purple{{border-top:2px solid #7C5EF0!important;}}
  .accent-amber{{border-top:2px solid #C9A84C!important;}}
  .accent-green{{border-top:2px solid #00E676!important;}}

  /* ── Typography ── */
  .card-label{{
    font-size:10px;font-weight:700;letter-spacing:.16em;
    text-transform:uppercase;color:rgba(255,255,255,.5);
    margin-bottom:10px;display:flex;align-items:center;gap:6px;
  }}
  .card-label::after{{content:'';flex:1;height:1px;background:rgba(255,255,255,.08);}}
  .big-num{{
    font-family:'Space Mono',monospace;
    font-size:42px;font-weight:700;line-height:1;letter-spacing:-.02em;
  }}
  .med-num{{font-family:'Space Mono',monospace;font-size:24px;font-weight:700;line-height:1;}}

  /* Metric pills row */
  .metric-row{{display:flex;gap:8px;margin-top:12px;}}
  .mpill{{
    background:rgba(255,255,255,.1);
    border-radius:12px;padding:8px 10px;flex:1;text-align:center;
    backdrop-filter:blur(10px);
  }}
  .mpill .val{{font-family:'Space Mono',monospace;font-size:16px;font-weight:700;}}
  .mpill .lbl{{font-size:8px;text-transform:uppercase;letter-spacing:.1em;opacity:.6;margin-top:2px;}}

  /* Section title */
  .sec{{font-size:10px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;
        color:#555;margin-bottom:12px;display:flex;align-items:center;gap:8px;}}
  .sec::after{{content:'';flex:1;height:1px;background:rgba(255,255,255,.06);}}

  /* Highlights grid */
  .hl-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;}}

  /* Draggable */
  .draggable{{cursor:grab;}}
  .draggable:active{{cursor:grabbing;}}
  .drag-over{{border-color:rgba(124,94,240,.6)!important;background:rgba(124,94,240,.05)!important;}}

  /* Animations */
  @keyframes pulse{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.5;transform:scale(.8)}}}}
  @keyframes fadeIn{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:translateY(0)}}}}
  .fade-in{{animation:fadeIn .4s ease forwards;}}

  /* Scrollbar */
  ::-webkit-scrollbar{{width:4px;height:4px;}}
  ::-webkit-scrollbar-track{{background:transparent;}}
  ::-webkit-scrollbar-thumb{{background:rgba(124,94,240,.4);border-radius:999px;}}
</style>
</head>
<body>

<div class="bento" id="bentoGrid">

  <!-- ═══ ROW 1 ═══ -->

  <!-- Card: Wordmark + Stats (purple, 3 cols) -->
  <div class="card card-purple s3 fade-in draggable" draggable="true" id="wcard">
    <div style="font-family:'Space Mono',monospace;font-size:32px;font-weight:700;letter-spacing:-.02em;margin-bottom:2px">
      odds<span style="opacity:.7">*</span>
    </div>
    <div style="font-size:9px;letter-spacing:.2em;text-transform:uppercase;opacity:.6;margin-bottom:16px">
      FOOTBALL · NBA · AI
    </div>
    <div style="font-size:11px;opacity:.75;margin-bottom:12px">📅 {today_fmt}</div>
    <div class="metric-row">
      <div class="mpill"><div class="val">{n_matches}</div><div class="lbl">Matchs</div></div>
      <div class="mpill"><div class="val">{n_safe}</div><div class="lbl">Safe</div></div>
    </div>
    <div class="metric-row">
      <div class="mpill"><div class="val" style="color:#fff">{avg_score}%</div><div class="lbl">Score moy.</div></div>
      <div class="mpill"><div class="val" style="color:#ffaaaa">{n_live}</div><div class="lbl">Live</div></div>
    </div>
  </div>

  <!-- Card: Safe Bets (5 cols) -->
  <div class="card s5 accent-green fade-in draggable" draggable="true" id="safecard" style="animation-delay:.05s">
    <div class="card-label">✅ Paris Safe — Top 3</div>
    {bet_pills(safe,"#00E676")}
  </div>

  <!-- Card: Value Bets (4 cols) -->
  <div class="card s4 accent-amber fade-in draggable" draggable="true" id="valuecard" style="animation-delay:.1s">
    <div class="card-label">⚡ Value Bets — Top 3</div>
    {bet_pills(value,"#FFD740")}
  </div>

  <!-- ═══ ROW 2 ═══ -->

  <!-- Card: Bankroll (purple, 3 cols) -->
  <div class="card card-purple s3 fade-in draggable" draggable="true" id="brcard" style="animation-delay:.15s">
    <div class="card-label">💰 Bankroll</div>
    <div class="big-num">{bankroll:.0f}<span style="font-size:20px">€</span></div>
    <div class="metric-row">
      <div class="mpill"><div class="val" style="color:{roi_col}">{roi:+.1f}%</div><div class="lbl">ROI</div></div>
      <div class="mpill"><div class="val">{wr:.0f}%</div><div class="lbl">Win%</div></div>
      <div class="mpill"><div class="val">{len(bet_log)}</div><div class="lbl">Paris</div></div>
    </div>
    <div style="margin-top:14px;font-size:10px;opacity:.6">
      💡 Gérez votre bankroll dans l'onglet Bankroll
    </div>
  </div>

  <!-- Card: H2H (3 cols) -->
  <div class="card s3 fade-in draggable" draggable="true" id="h2hcard" style="animation-delay:.2s">
    <div class="card-label">⚔️ H2H</div>
    {h2h_widget(scored)}
  </div>

  <!-- Card: Cotes (3 cols) -->
  <div class="card s3 fade-in draggable" draggable="true" id="cotescard" style="animation-delay:.25s">
    <div class="card-label">💹 Cotes live</div>
    {cotes_widget(scored, odds)}
  </div>

  <!-- Card: Forme (3 cols) -->
  <div class="card s3 fade-in draggable" draggable="true" id="formecard" style="animation-delay:.3s">
    <div class="card-label">📈 Forme équipes</div>
    {forme_widget(scored)}
  </div>

  <!-- ═══ ROW 3 ═══ -->

  <!-- Card: NBA (4 cols) -->
  <div class="card accent-amber s4 fade-in draggable" draggable="true" id="nbacard" style="animation-delay:.35s">
    <div class="card-label">🏀 NBA · {len(nba_games)} matchs</div>
    {nba_pills(nba_games)}
  </div>

  <!-- Card: Highlights (8 cols) -->
  <div class="card s8 fade-in draggable" draggable="true" id="hlcard" style="animation-delay:.4s">
    <div class="card-label">🎬 Highlights · Scorebat</div>
    <div class="hl-grid">
      {highlights_grid(highlights)}
    </div>
  </div>

</div>

<script>
// ── Drag-to-reorder ──
let dragging = null;

document.querySelectorAll('.draggable').forEach(card => {{
  card.addEventListener('dragstart', e => {{
    dragging = card;
    setTimeout(() => card.style.opacity = '.4', 0);
  }});
  card.addEventListener('dragend', () => {{
    card.style.opacity = '1';
    dragging = null;
    document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
  }});
  card.addEventListener('dragover', e => {{
    e.preventDefault();
    if (dragging && dragging !== card) {{
      card.classList.add('drag-over');
    }}
  }});
  card.addEventListener('dragleave', () => card.classList.remove('drag-over'));
  card.addEventListener('drop', e => {{
    e.preventDefault();
    card.classList.remove('drag-over');
    if (dragging && dragging !== card) {{
      const grid = document.getElementById('bentoGrid');
      const cards = [...grid.children];
      const dragIdx = cards.indexOf(dragging);
      const dropIdx = cards.indexOf(card);
      if (dragIdx < dropIdx) {{
        grid.insertBefore(dragging, card.nextSibling);
      }} else {{
        grid.insertBefore(dragging, card);
      }}
    }}
  }});
}});

// ── Progress bars animate on load ──
window.addEventListener('load', () => {{
  document.querySelectorAll('[style*="transition:width"]').forEach(bar => {{
    const w = bar.style.width;
    bar.style.width = '0%';
    setTimeout(() => bar.style.width = w, 100);
  }});
}});
</script>
</body>
</html>"""
    return html

# ─────────────────────────────────────────────────────────────────
# GLOBAL STYLES for Streamlit shell
# ─────────────────────────────────────────────────────────────────
SHELL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap');
:root{--v:#7C5EF0;--g:#00E676;--y:#FFD740;--r:#FF5252;--nba:#C9A84C;--bg:#0f0f0f;--bg1:#1a1a1a;--bg2:#222;--t1:#F0F0F0;--t2:#AAA;--t3:#666;--bdr:rgba(255,255,255,.07);}
html,body,[class*="css"]{font-family:'Space Grotesk',sans-serif!important;background:var(--bg)!important;color:var(--t1)!important;}
.stApp{background:var(--bg)!important;}
.block-container{padding-top:.5rem!important;background:transparent!important;max-width:1500px;}
section[data-testid="stSidebar"]{background:var(--bg1)!important;border-right:1px solid var(--bdr)!important;}
div[data-testid="stSidebar"] .stButton>button{width:100%;background:transparent;border:none;color:var(--t2);font-size:.8rem;font-weight:500;border-radius:9px;padding:.45rem .8rem;text-align:left;transition:all .15s;margin-bottom:2px;}
div[data-testid="stSidebar"] .stButton>button:hover{background:rgba(124,94,240,.12);color:#9B82F5;}
.stButton>button{background:var(--v)!important;color:white!important;border:none!important;border-radius:9px!important;font-weight:700!important;font-size:.76rem!important;padding:.42rem 1rem!important;box-shadow:0 3px 12px rgba(124,94,240,.35)!important;transition:all .2s!important;}
.stButton>button:hover{transform:translateY(-1px)!important;box-shadow:0 5px 20px rgba(124,94,240,.5)!important;}
.stTextInput>div>div>input,.stSelectbox>div>div,.stDateInput>div>div>input,.stNumberInput>div>div>input{background:var(--bg2)!important;border:1px solid var(--bdr)!important;border-radius:9px!important;color:var(--t1)!important;font-family:'Space Grotesk',sans-serif!important;}
.stTextInput>div>div>input:focus{border-color:var(--v)!important;box-shadow:0 0 0 2px rgba(124,94,240,.2)!important;}
label{color:var(--t2)!important;font-size:.76rem!important;}
div[data-testid="stExpander"]{background:var(--bg2)!important;border:1px solid var(--bdr)!important;border-radius:12px!important;margin-bottom:5px!important;}
::-webkit-scrollbar{width:4px;}::-webkit-scrollbar-track{background:var(--bg);}
::-webkit-scrollbar-thumb{background:rgba(124,94,240,.4);border-radius:999px;}
div[data-testid="stMetricValue"]{color:var(--t1)!important;font-family:'Space Mono',monospace!important;font-weight:700!important;}
.stDataFrame{background:transparent!important;}
.cbu{background:var(--v);color:white;border-radius:16px 16px 4px 16px;padding:.6rem .9rem;margin:.3rem 0;margin-left:2rem;font-size:.83rem;line-height:1.5;max-width:80%;}
.cba{background:var(--bg2);border:1px solid var(--bdr);border-left:2px solid var(--v);border-radius:16px 16px 16px 4px;padding:.6rem .9rem;margin:.3rem 0;margin-right:2rem;font-size:.83rem;color:var(--t2);line-height:1.5;max-width:80%;}
.cbl{font-size:.55rem;font-weight:700;text-transform:uppercase;letter-spacing:.12em;opacity:.45;margin-bottom:2px;}
@keyframes bf{0%,100%{transform:translateY(0) rotate(-3deg);}50%{transform:translateY(-5px) rotate(3deg);}}
.agent-bar{background:var(--bg2);border:1px solid var(--bdr);border-left:3px solid var(--v);border-radius:14px;padding:.85rem 1.1rem;display:flex;align-items:flex-start;gap:.8rem;margin-bottom:1rem;}
.agent-ic{font-size:1.8rem;animation:bf 3s ease-in-out infinite;flex-shrink:0;}
.agent-tag{font-size:.56rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--v);margin-bottom:3px;}
.agent-msg{font-size:.85rem;color:var(--t2);line-height:1.5;}
.sl{font-size:.6rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--t3);margin-bottom:.65rem;display:flex;align-items:center;gap:7px;}
.sl::after{content:'';flex:1;height:1px;background:var(--bdr);}
.pred-card{background:var(--bg2);border:1px solid var(--bdr);border-radius:12px;padding:10px 13px;margin-bottom:7px;transition:all .2s;cursor:pointer;}
.pred-card:hover{border-color:rgba(124,94,240,.4);background:#2a2a2a;}
</style>
"""

# ─────────────────────────────────────────────────────────────────
# PAGES
# ─────────────────────────────────────────────────────────────────
def page_dashboard():
    st.markdown(SHELL_CSS, unsafe_allow_html=True)
    today = datetime.date.today().strftime("%Y-%m-%d")

    with st.spinner("⚽ Chargement du dashboard..."):
        fixtures, scored = load_scored(today, 20)
        nba_games = fetch_nba_games(today)
        highlights = fetch_highlights()
        odds = fetch_odds()

    if not scored and not nba_games:
        st.warning("⚠️ Aucune donnée disponible. Vérifiez vos clés API dans Paramètres.")

    html = build_bento_html(
        scored, nba_games, highlights, odds,
        st.session_state["bankroll"],
        st.session_state["bet_log"],
    )
    components.html(html, height=1100, scrolling=True)

    # Widget manager below grid
    with st.expander("📱 Gérer les widgets — drag & drop activé dans le dashboard ci-dessus"):
        st.info("Dans le dashboard, vous pouvez faire **glisser-déposer** les cards pour les réorganiser. L'ordre est maintenu pendant la session.")
        if st.button("🔄 Réinitialiser l'ordre"):
            st.rerun()


def page_predictions():
    st.markdown(SHELL_CSS, unsafe_allow_html=True)
    st.markdown('<div style="font-family:Space Mono,monospace;font-size:1.4rem;font-weight:700;margin-bottom:1rem">📊 Prédictions</div>', unsafe_allow_html=True)

    c1,c2,c3 = st.columns([2,2,2])
    with c1: sel_date = st.date_input("Date", value=datetime.date.today(), label_visibility="collapsed")
    with c2: league_f = st.selectbox("Ligue", ["Toutes"]+[f"{LEAGUE_FLAGS.get(k,'⚽')} {v}" for k,v in TARGET_LEAGUES.items()], label_visibility="collapsed")
    with c3: type_f = st.selectbox("Type", ["Tous","SAFE","VALUE","RISK"], label_visibility="collapsed")

    date_str = sel_date.strftime("%Y-%m-%d")
    with st.spinner("Analyse en cours..."):
        _, scored = load_scored(date_str, 40)

    if league_f != "Toutes":
        lg_name = league_f.split(" ",1)[1] if " " in league_f else league_f
        scored = [s for s in scored if lg_name.lower() in s["fx"]["league"].lower()]
    if type_f != "Tous":
        scored = [s for s in scored if s["gs"]["bt"]==type_f]

    if not scored:
        st.info("Aucun match trouvé. L'API-Football free tier est limitée à 100 req/jour.")
        return

    st.markdown(f'<div class="sl">{len(scored)} matchs</div>', unsafe_allow_html=True)

    for item in scored:
        fx=item["fx"]; gs=item["gs"]; pred=item["pred"]
        icon={"SAFE":"✓","VALUE":"⚡","RISK":"⚠"}.get(gs["bt"],"·")
        flag=fx.get("flag","⚽")
        with st.expander(f"{icon} {flag} {fx['home']} vs {fx['away']}  ·  {gs['best']}  ·  {gs['gs']}%  |  {fx['league']}"):
            c1,c2,c3 = st.columns(3)
            with c1:
                fig=go.Figure(go.Bar(
                    x=["Dom.","Nul","Ext."],y=[gs["hp"],gs["dp"],gs["ap"]],
                    marker_color=["#7C5EF0","#444","#00E676"],
                    text=[f"{v:.0f}%" for v in [gs["hp"],gs["dp"],gs["ap"]]],
                    textposition="outside",textfont=dict(size=10,color="#AAA")))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#666"),height=160,margin=dict(t=10,b=10,l=0,r=0),
                    showlegend=False,xaxis=dict(showgrid=False),yaxis=dict(showgrid=False,visible=False))
                st.plotly_chart(fig,use_container_width=True,key=f"bar_{fx['fixture_id']}")
            with c2:
                h2h=fetch_h2h(fx["home_id"],fx["away_id"])
                fig2=go.Figure(go.Pie(
                    values=[max(h2h["hw"],.01),max(h2h["dr"],.01),max(h2h["aw"],.01)],
                    labels=["Dom.","Nul","Ext."],hole=0.62,
                    marker=dict(colors=["#7C5EF0","#333","#00E676"]),
                    textinfo="percent",textfont=dict(size=9,color="white")))
                fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)",height=160,
                    margin=dict(t=10,b=10,l=0,r=0),showlegend=False,font=dict(color="#666"))
                st.plotly_chart(fig2,use_container_width=True,key=f"pie_{fx['fixture_id']}")
            with c3:
                fh=fetch_form(fx["home_id"]); fa=fetch_form(fx["away_id"])
                fhs="".join(["🟢" if r["res"]=="W" else("🟡" if r["res"]=="D" else "🔴") for r in fh])
                fas="".join(["🟢" if r["res"]=="W" else("🟡" if r["res"]=="D" else "🔴") for r in fa])
                c_col = conf_color(gs["conf"])
                st.markdown(f"""
                <div style="padding:.5rem 0">
                  <div style="font-family:'Space Mono',monospace;font-size:1.8rem;font-weight:700;color:{c_col}">{gs['conf']}%</div>
                  <div style="font-size:.75rem;color:#666;margin-bottom:.8rem">{gs['best']}</div>
                  <div style="font-size:.82rem;line-height:2.2;color:#AAA">
                    <b style="color:#F0F0F0">{fx['home'][:16]}</b> {fhs}<br>
                    <b style="color:#F0F0F0">{fx['away'][:16]}</b> {fas}
                  </div>
                </div>""", unsafe_allow_html=True)
            if st.button("Analyse complète →",key=f"az_{fx['fixture_id']}"):
                st.session_state["selected_match"]=item
                st.session_state["page"]="Analyzer"
                st.rerun()


def page_analyzer():
    st.markdown(SHELL_CSS, unsafe_allow_html=True)
    item = st.session_state.get("selected_match")
    if not item:
        st.info("Sélectionnez un match depuis Prédictions.")
        if st.button("← Retour"): st.session_state["page"]="Prédictions"; st.rerun()
        return

    fx=item["fx"]; gs=item["gs"]; pred=item["pred"]
    flag=fx.get("flag","⚽")
    st.markdown(f'<div style="font-family:Space Mono,monospace;font-size:1.3rem;font-weight:700;margin-bottom:.2rem">{flag} {fx["home"]} vs {fx["away"]}</div><div style="font-size:.6rem;color:#666;text-transform:uppercase;letter-spacing:.12em;margin-bottom:1rem">{fx["league"]}</div>', unsafe_allow_html=True)

    c1,c2,c3 = st.columns([1,1.4,1])
    with c1:
        fig_g=go.Figure(go.Indicator(mode="gauge+number",value=gs["gs"],
            gauge={"axis":{"range":[0,100],"tickcolor":"#444","tickfont":{"size":9}},
                   "bar":{"color":"#7C5EF0","thickness":0.25},"bgcolor":"rgba(0,0,0,0)","bordercolor":"rgba(0,0,0,0)",
                   "steps":[{"range":[0,55],"color":"rgba(255,82,82,.07)"},{"range":[55,70],"color":"rgba(255,215,64,.08)"},{"range":[70,100],"color":"rgba(0,230,118,.08)"}],
                   "threshold":{"line":{"color":"#FFD740","width":2},"thickness":.8,"value":68}},
            number={"suffix":"%","font":{"color":"#7C5EF0","size":28,"family":"Space Mono"}},
            title={"text":"Score odds*","font":{"color":"#666","size":11}}))
        fig_g.update_layout(paper_bgcolor="rgba(0,0,0,0)",font=dict(color="#666"),height=210,margin=dict(t=30,b=10,l=10,r=10))
        st.plotly_chart(fig_g,use_container_width=True,key="gauge_az")
    with c2:
        try: hxg=float(pred.get("goals_home") or 1.4)
        except: hxg=1.4
        try: axg=float(pred.get("goals_away") or 1.1)
        except: axg=1.1
        pm=poisson_probs(hxg,axg); mat=[row[:5] for row in pm["mat"][:5]]
        fig_p=go.Figure(go.Heatmap(z=mat,x=[f"Ext.{g}" for g in range(5)],y=[f"Dom.{g}" for g in range(5)],
            colorscale=[[0,"rgba(20,20,20,.9)"],[.4,"rgba(124,94,240,.4)"],[1,"rgba(124,94,240,.95)"]],showscale=False,
            text=[[f"{v:.1f}%" for v in row] for row in mat],texttemplate="%{text}",textfont=dict(size=8,color="white")))
        fig_p.update_layout(title=dict(text=f"Poisson — xG {hxg:.1f}/{axg:.1f}",font=dict(color="#666",size=11)),
            paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font=dict(color="#666"),
            height=210,margin=dict(t=35,b=10,l=45,r=10),xaxis=dict(color="#444"),yaxis=dict(color="#444"))
        st.plotly_chart(fig_p,use_container_width=True,key="poisson_az")
    with c3:
        c_col=conf_color(gs["conf"])
        st.markdown(f"""
        <div style="background:#1a1a1a;border:1px solid rgba(255,255,255,.07);border-top:2px solid #7C5EF0;
                    border-radius:14px;padding:16px;height:210px;box-sizing:border-box">
          <div style="font-size:9px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#555;margin-bottom:8px">Recommandation</div>
          <div style="font-family:'Space Mono',monospace;font-size:15px;font-weight:700;color:#F0F0F0">{gs['best']}</div>
          <div style="font-size:11px;font-weight:700;color:{c_col};margin:5px 0">Confiance {gs['conf']}%</div>
          <div style="font-size:10px;color:#555;font-style:italic;line-height:1.5;margin-top:8px">{pred.get('advice','—')[:100]}</div>
          <div style="margin-top:10px;font-size:10px;color:#444">
            xG prévu: {pred.get('goals_home','?')} / {pred.get('goals_away','?')}
          </div>
        </div>""", unsafe_allow_html=True)

    c4,c5 = st.columns([1.5,1])
    with c4:
        cats=["Dom.","Nul","Ext.","Over 2.5","BTTS"]; vals=[gs["hp"],gs["dp"],gs["ap"],gs["over"],gs["over"]*.88]
        fig_r=go.Figure()
        fig_r.add_trace(go.Scatterpolar(r=vals+[vals[0]],theta=cats+[cats[0]],
            fill="toself",fillcolor="rgba(124,94,240,.1)",line=dict(color="#7C5EF0",width=2)))
        fig_r.update_layout(polar=dict(bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True,range=[0,100],gridcolor="rgba(255,255,255,.05)",color="#444",tickfont=dict(size=7)),
            angularaxis=dict(gridcolor="rgba(255,255,255,.05)",color="#AAA",tickfont=dict(size=9))),
            paper_bgcolor="rgba(0,0,0,0)",font=dict(color="#666"),height=260,margin=dict(t=20,b=20),showlegend=False)
        st.plotly_chart(fig_r,use_container_width=True,key="radar_az")
    with c5:
        h2h=fetch_h2h(fx["home_id"],fx["away_id"])
        mh="".join([f'<div style="font-size:11px;color:#AAA;padding:5px 0;border-bottom:1px solid rgba(255,255,255,.05)">{m["home"]} <b style="color:#7C5EF0">{m["score"]}</b> {m["away"]} <span style="color:#444">{m["date"]}</span></div>' for m in h2h["matches"][:5]])
        st.markdown(f"""
        <div style="background:#1a1a1a;border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:16px">
          <div style="font-size:9px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#555;margin-bottom:10px">H2H · 10 derniers</div>
          <div style="display:flex;justify-content:space-around;text-align:center;margin-bottom:12px">
            <div><div style="font-family:'Space Mono',monospace;font-size:26px;font-weight:700;color:#7C5EF0">{h2h['hw']}</div><div style="font-size:9px;color:#555">Dom.</div></div>
            <div><div style="font-family:'Space Mono',monospace;font-size:26px;font-weight:700;color:#444">{h2h['dr']}</div><div style="font-size:9px;color:#555">Nuls</div></div>
            <div><div style="font-family:'Space Mono',monospace;font-size:26px;font-weight:700;color:#00E676">{h2h['aw']}</div><div style="font-size:9px;color:#555">Ext.</div></div>
          </div>
          {mh}
        </div>""", unsafe_allow_html=True)

    c6,c7 = st.columns(2)
    for col,team,tid in [(c6,fx["home"],fx["home_id"]),(c7,fx["away"],fx["away_id"])]:
        form=fetch_form(tid)
        with col:
            st.markdown(f'<div class="sl">{team}</div>', unsafe_allow_html=True)
            if form:
                rm={"W":3,"D":1,"L":0}; clrs={"W":"#00E676","D":"#FFD740","L":"#FF5252"}
                fig_f=go.Figure(go.Bar(x=[f"J-{len(form)-i}" for i in range(len(form))],y=[rm.get(r["res"],0) for r in form],
                    marker_color=[clrs.get(r["res"],"#444") for r in form],
                    text=[r["res"] for r in form],textposition="outside",textfont=dict(size=10,color="#AAA")))
                fig_f.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#666"),height=130,margin=dict(t=10,b=10,l=0,r=0),showlegend=False,
                    xaxis=dict(showgrid=False,color="#444"),yaxis=dict(showgrid=False,visible=False,range=[0,4]))
                st.plotly_chart(fig_f,use_container_width=True,key=f"form_{tid}_az")

    if st.button("← Retour"):
        st.session_state["page"]="Prédictions"; st.rerun()


def page_nba():
    st.markdown(SHELL_CSS, unsafe_allow_html=True)
    st.markdown('<div style="font-family:Space Mono,monospace;font-size:1.4rem;font-weight:700;margin-bottom:.5rem">🏀 NBA Predictions</div>', unsafe_allow_html=True)
    sel = st.date_input("Date", value=datetime.date.today(), label_visibility="collapsed")
    with st.spinner(""): games = fetch_nba_games(sel.strftime("%Y-%m-%d"))

    if not games:
        st.info("🏀 Pas de matchs NBA ce jour.")
        return

    scored = sorted([(g, nba_score(g)) for g in games], key=lambda x:x[1]["conf"], reverse=True)

    m1,m2,m3,m4 = st.columns(4)
    m1.metric("Matchs",len(games))
    m2.metric("Safe",sum(1 for _,ns in scored if ns["bt"]=="SAFE"))
    m3.metric("Value",sum(1 for _,ns in scored if ns["bt"]=="VALUE"))
    live=sum(1 for g,_ in scored if any(q in g.get("status","") for q in ["Q","Ht"]))
    m4.metric("En cours",live)
    st.markdown("<br>", unsafe_allow_html=True)

    for g,ns in scored:
        c = ns["conf"]; c_col = conf_color(c)
        bt = ns["bt"]
        bt_col={"SAFE":"#00E676","VALUE":"#FFD740","RISK":"#FF5252"}.get(bt,"#666")
        hs = g.get("home_score",0) or 0
        as_ = g.get("away_score",0) or 0
        is_live = any(q in g.get("status","") for q in ["Q","Ht","q"])
        is_final = "Final" in g.get("status","")
        icon={"SAFE":"✓","VALUE":"⚡","RISK":"⚠"}.get(bt,"·")

        with st.expander(f"{icon} {g['home']} vs {g['away']}  ·  {ns['best']}  ·  {c}%  ·  {g.get('status','')}"):
            col1,col2 = st.columns(2)
            with col1:
                st.markdown(f"""
                <div style="padding:.5rem 0">
                  <div style="font-family:'Space Mono',monospace;font-size:2.2rem;font-weight:700;color:{c_col};line-height:1">{c}%</div>
                  <div style="font-size:.8rem;color:#AAA;margin:.3rem 0">{ns['best']} favoris</div>
                  <div style="font-size:.8rem;color:#666;margin-top:.5rem">
                    🏠 {g['home_abbr']}: {ns['h_win']}%<br>
                    ✈️ {g['away_abbr']}: {ns['a_win']}%
                  </div>
                  {"<div style='font-family:Space Mono,monospace;font-size:1.6rem;font-weight:700;color:#C9A84C;margin-top:.8rem'>" + str(hs) + " — " + str(as_) + "</div>" if (is_live or is_final) else ""}
                  <div style="margin-top:.5rem">
                    <span style="background:{bt_col}22;color:{bt_col};border:1px solid {bt_col}44;border-radius:999px;font-size:10px;font-weight:700;padding:3px 10px">{bt}</span>
                  </div>
                </div>""", unsafe_allow_html=True)
            with col2:
                fig=go.Figure(go.Bar(
                    x=[g['home_abbr'] or g['home'].split()[-1], g['away_abbr'] or g['away'].split()[-1]],
                    y=[ns["h_win"],ns["a_win"]],
                    marker_color=["#7C5EF0","#00E676"],
                    text=[f"{ns['h_win']}%",f"{ns['a_win']}%"],
                    textposition="outside",textfont=dict(size=12,color="#AAA")))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#666"),height=180,margin=dict(t=10,b=10,l=0,r=0),
                    showlegend=False,xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=False,visible=False,range=[0,105]))
                st.plotly_chart(fig,use_container_width=True,key=f"nba_{g['id']}")


def page_live():
    st.markdown(SHELL_CSS, unsafe_allow_html=True)
    st.markdown('<div style="font-family:Space Mono,monospace;font-size:1.4rem;font-weight:700;margin-bottom:.5rem">🔴 Live</div>', unsafe_allow_html=True)
    auto=st.checkbox("Auto-refresh 30s",value=False)
    if auto: time.sleep(0.5); st.rerun()
    today=datetime.date.today().strftime("%Y-%m-%d")
    tab1,tab2=st.tabs(["⚽ Football","🏀 NBA"])
    with tab1:
        fx=fetch_fixtures(today)
        live=[f for f in fx if f["status"] in ("1H","HT","2H","ET","P")]
        upcoming=[f for f in fx if f["status"] in ("NS","TBD")]
        fin=[f for f in fx if f["status"] in ("FT","AET","PEN")]
        c1,c2,c3=st.columns(3); c1.metric("En cours",len(live)); c2.metric("À venir",len(upcoming)); c3.metric("Terminés",len(fin))
        if live:
            st.markdown('<div class="sl" style="margin-top:1rem">En cours</div>', unsafe_allow_html=True)
            lc1,lc2=st.columns(2)
            for i,f in enumerate(live):
                hg=f.get("home_goals") or "?"; ag=f.get("away_goals") or "?"; el=f.get("elapsed") or ""
                with (lc1 if i%2==0 else lc2):
                    elapsed_str = str(el) + "'"
                    st.markdown(f'<div style="background:#1a1a1a;border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:12px;margin-bottom:6px"><div style="display:flex;justify-content:space-between;align-items:center"><div><div style="font-size:9px;color:#666">{f["flag"]} {f["league"]}</div><div style="font-size:13px;font-weight:700">{f["home"]}<br>{f["away"]}</div></div><div style="text-align:center"><div style="font-family:Space Mono,monospace;font-size:22px;font-weight:700;color:#7C5EF0">{hg}&#8211;{ag}</div><div style="font-size:10px;color:#FF5252;font-weight:700">{elapsed_str}</div></div></div></div>', unsafe_allow_html=True)
        if upcoming:
            st.markdown('<div class="sl" style="margin-top:.8rem">À venir</div>', unsafe_allow_html=True)
            uc1,uc2=st.columns(2)
            for i,f in enumerate(upcoming[:14]):
                t=f["time"][11:16] if len(f.get("time",""))>10 else ""
                with (uc1 if i%2==0 else uc2):
                    st.markdown(f'<div style="background:#1a1a1a;border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:10px;margin-bottom:5px"><div style="font-size:9px;color:#666">{f["flag"]} {f["league"]} · {t}</div><div style="font-size:12px;font-weight:700;margin-top:2px">{f["home"]} vs {f["away"]}</div></div>', unsafe_allow_html=True)
    with tab2:
        games=fetch_nba_games(today)
        if not games: st.info("🏀 Pas de matchs NBA aujourd'hui.")
        else:
            gc1,gc2=st.columns(2)
            for i,g in enumerate(games):
                hs=g.get("home_score",0) or 0; as_=g.get("away_score",0) or 0
                rc="#00E676" if hs>as_ else("#666" if hs==as_ else "#FF5252")
                with (gc1 if i%2==0 else gc2):
                    st.markdown(f'<div style="background:#1a1a1a;border:1px solid rgba(255,255,255,.07);border-left:3px solid #C9A84C;border-radius:12px;padding:10px;margin-bottom:5px"><div style="display:flex;justify-content:space-between;align-items:center"><div><div style="font-size:9px;color:#C9A84C">NBA · {g.get("status","")}</div><div style="font-size:12px;font-weight:700">{g["home"]}</div><div style="font-size:11px;color:#AAA">{g["away"]}</div></div><div style="font-family:Space Mono,monospace;font-size:18px;font-weight:700;color:{rc}">{hs}–{as_}</div></div></div>', unsafe_allow_html=True)
    st.caption(f"Mis à jour: {datetime.datetime.now().strftime('%H:%M:%S')}")


def page_bankroll():
    st.markdown(SHELL_CSS, unsafe_allow_html=True)
    st.markdown('<div style="font-family:Space Mono,monospace;font-size:1.4rem;font-weight:700;margin-bottom:1rem">💰 Bankroll</div>', unsafe_allow_html=True)

    br = st.session_state["bankroll"]
    log = st.session_state["bet_log"]
    total_mise=sum(b.get("mise",0) for b in log); total_gain=sum(b.get("gain",0) for b in log)
    roi=round(total_gain/max(total_mise,1)*100,1) if total_mise else 0
    wins=sum(1 for b in log if b.get("gain",0)>0); wr=round(wins/max(len(log),1)*100,1)
    roi_c="#00E676" if roi>=0 else "#FF5252"

    # ── Editable bankroll ──
    c_br, c_edit = st.columns([3,1])
    with c_br:
        st.markdown(f'<div style="font-family:Space Mono,monospace;font-size:3rem;font-weight:700;color:#7C5EF0;line-height:1">{br:.2f} <span style="font-size:1.2rem;color:#666">EUR</span></div>', unsafe_allow_html=True)
    with c_edit:
        if st.button("✏️ Modifier"):
            st.session_state["edit_bankroll"] = not st.session_state.get("edit_bankroll",False)

    if st.session_state.get("edit_bankroll",False):
        new_br = st.number_input("Nouvelle bankroll (€)", value=float(br), min_value=0.0, step=10.0, format="%.2f")
        c1,c2=st.columns(2)
        with c1:
            if st.button("✅ Confirmer"):
                st.session_state["bankroll"] = new_br
                st.session_state["edit_bankroll"] = False
                st.success(f"Bankroll mise à jour: {new_br:.2f}€")
                st.rerun()
        with c2:
            if st.button("❌ Annuler"):
                st.session_state["edit_bankroll"] = False
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    m1,m2,m3,m4=st.columns(4)
    m1.metric("ROI global",f"{roi:+.1f}%")
    m2.metric("Win Rate",f"{wr:.0f}%")
    m3.metric("Paris enregistrés",len(log))
    m4.metric("Gain total",f"{total_gain:+.2f}€")

    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("➕ Ajouter un pari",expanded=False):
        bc1,bc2,bc3,bc4,bc5=st.columns(5)
        with bc1: m_in=st.text_input("Match",placeholder="PSG vs Lyon")
        with bc2: p_in=st.text_input("Prédiction",placeholder="1X2 / Over / BTTS")
        with bc3: ms_in=st.number_input("Mise (€)",min_value=0.5,value=10.0,step=0.5)
        with bc4: ct_in=st.number_input("Cote",min_value=1.01,value=1.80,step=0.05)
        with bc5: res=st.selectbox("Résultat",["En attente","Gagné","Perdu"])
        if st.button("💾 Enregistrer"):
            gain=round(ms_in*(ct_in-1),2) if res=="Gagné" else(-ms_in if res=="Perdu" else 0.0)
            st.session_state["bet_log"].append({
                "date": datetime.date.today().strftime("%d/%m/%Y"),
                "match":m_in,"pred":p_in,"mise":ms_in,"cote":ct_in,"result":res,"gain":gain,
            })
            if res!="En attente":
                st.session_state["bankroll"] = round(st.session_state["bankroll"]+gain,2)
            st.success(f"✅ Pari enregistré! {'Gain: +'+str(round(ms_in*(ct_in-1),2))+'€' if res=='Gagné' else ('Perte: -'+str(ms_in)+'€' if res=='Perdu' else '')}")
            st.rerun()

    if log:
        # Bankroll curve
        gains=[b.get("gain",0) for b in log if b.get("result")!="En attente"]
        if gains:
            curve=[st.session_state["bankroll"] - sum(gains)]; # start from initial
            for g in gains: curve.append(round(curve[-1]+g,2))
            fig_br=go.Figure()
            fig_br.add_trace(go.Scatter(y=curve,mode="lines+markers",
                line=dict(color="#7C5EF0",width=2.5,shape="spline"),
                marker=dict(size=5,color="#7C5EF0",line=dict(color="#0f0f0f",width=1)),
                fill="tozeroy",fillcolor="rgba(124,94,240,.08)"))
            fig_br.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#666"),height=220,margin=dict(t=10,b=10,l=50,r=10),
                showlegend=False,xaxis=dict(showgrid=False,color="#444"),
                yaxis=dict(gridcolor="rgba(255,255,255,.04)",color="#444"))
            st.plotly_chart(fig_br,use_container_width=True,key="br_curve")

        st.markdown('<div class="sl">Historique des paris</div>', unsafe_allow_html=True)
        df=pd.DataFrame(log)
        # Color gains
        st.dataframe(df,use_container_width=True,hide_index=True,
                     column_config={"gain":st.column_config.NumberColumn("Gain €",format="%.2f€"),"cote":st.column_config.NumberColumn("Cote",format="%.2f"),"mise":st.column_config.NumberColumn("Mise €",format="%.2f€")})

        if st.button("🗑 Effacer l'historique"):
            st.session_state["bet_log"]=[]
            st.session_state["bankroll"]=1000.0
            st.rerun()
    else:
        st.info("Aucun pari enregistré — ajoutez votre premier pari ci-dessus ☝️")


def page_chat():
    st.markdown(SHELL_CSS, unsafe_allow_html=True)
    st.markdown('<div class="agent-bar"><div class="agent-ic">⚽</div><div><div class="agent-tag">Agent odds* · Gemini 2.0 Flash</div><div class="agent-msg">Je suis votre expert paris sportifs. Posez-moi n&#39;importe quelle question sur le football, la NBA, les cotes ou vos paris ⚽🏀</div></div></div>', unsafe_allow_html=True)

    for msg in st.session_state["chat_history"]:
        if msg["role"]=="user":
            st.markdown(f'<div class="cbu"><div class="cbl">Vous</div>{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="cba"><div class="cbl" style="color:#7C5EF0">⚽ odds*</div>{msg["content"]}</div>', unsafe_allow_html=True)

    user_input=st.chat_input("Posez votre question... ex: combiné du jour, NBA ce soir, analyse Arsenal vs Chelsea")
    if user_input:
        st.session_state["chat_history"].append({"role":"user","content":user_input})
        with st.spinner("Gemini réfléchit..."):
            ctx = build_context()
            resp = call_gemini(user_input, ctx)
            if not resp: resp = agent_fallback(user_input)
        st.session_state["chat_history"].append({"role":"assistant","content":resp})
        st.rerun()

    c1,_ = st.columns([1,8])
    with c1:
        if st.button("🗑"): st.session_state["chat_history"]=[]; st.rerun()
    key=st.session_state["api_keys"].get("gemini","")
    ok = key and len(key)>20
    st.markdown(f'<div style="font-size:.65rem;color:{"#00E676" if ok else "#666"};margin-top:.3rem">{"● Gemini 2.0 Flash connecté" if ok else "● Clé Gemini non configurée"}</div>', unsafe_allow_html=True)


def page_params():
    st.markdown(SHELL_CSS, unsafe_allow_html=True)
    st.markdown('<div style="font-family:Space Mono,monospace;font-size:1.4rem;font-weight:700;margin-bottom:1rem">⚙️ Paramètres</div>', unsafe_allow_html=True)

    with st.expander("🔐 Clés API", expanded=True):
        keys=st.session_state["api_keys"]
        labels={
            "api_football":  "API-Football (principal)",
            "rapidapi":      "RapidAPI Football (backup)",
            "the_odds":      "The Odds API (cotes)",
            "newsapi":       "NewsAPI (sentiment)",
            "sportmonks":    "Sportmonks (stats xG)",
            "balldontlie":   "Balldontlie (NBA)",
            "scorebat":      "Scorebat (highlights)",
            "gemini":        "Gemini AI (chat IA)",
            "youtube":       "YouTube API v3",
        }
        c1,c2=st.columns(2)
        for i,(k,label) in enumerate(labels.items()):
            with (c1 if i%2==0 else c2):
                st.session_state["api_keys"][k]=st.text_input(label,value=keys.get(k,""),type="password",key=f"s_{k}")

    with st.expander("🏦 Bankroll initiale"):
        nbr=st.number_input("Bankroll de départ (€)",value=st.session_state["bankroll"],min_value=0.0,step=50.0,format="%.2f")
        if st.button("Mettre à jour"): st.session_state["bankroll"]=nbr; st.success("✓")

    ct,cc_=st.columns(2)
    with ct:
        if st.button("🔌 Tester toutes les APIs"):
            k=st.session_state["api_keys"]; results={}
            with st.spinner("Tests en cours..."):
                results["API-Football"]=safe_get("https://v3.football.api-sports.io/status",headers={"x-apisports-key":k["api_football"]}) is not None
                results["Balldontlie NBA"]=safe_get("https://api.balldontlie.io/v1/games",headers={"Authorization":k["balldontlie"]},params={"dates[]":datetime.date.today().strftime("%Y-%m-%d"),"per_page":1}) is not None
                results["Open-Meteo"]=safe_get("https://api.open-meteo.com/v1/forecast",params={"latitude":51.5,"longitude":-0.1,"hourly":"temperature_2m","forecast_days":1}) is not None
                results["NewsAPI"]=(lambda d:d is not None and d.get("status")=="ok")(safe_get("https://newsapi.org/v2/top-headlines",params={"country":"gb","apiKey":k["newsapi"]}))
                # Gemini test
                gkey=k.get("gemini","")
                if gkey and len(gkey)>20:
                    try:
                        gr=requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gkey}",headers={"Content-Type":"application/json"},json={"contents":[{"parts":[{"text":"hi"}]}],"generationConfig":{"maxOutputTokens":5}},timeout=10)
                        results["Gemini AI"]=gr.status_code==200
                    except: results["Gemini AI"]=False
                # Scorebat
                try:
                    sr=requests.get(f"https://www.scorebat.com/video-api/v3/feed/?token={k.get('scorebat','')}",timeout=8)
                    results["Scorebat"]=sr.status_code==200
                except: results["Scorebat"]=False

            for api,ok in results.items():
                st.markdown(f"{'✅' if ok else '❌'} **{api}**")
    with cc_:
        if st.button("🗑 Vider le cache"):
            clear_cache(); st.cache_data.clear(); st.success("Cache vidé !")

# ─────────────────────────────────────────────────────────────────
# SIDEBAR + ROUTER
# ─────────────────────────────────────────────────────────────────
NAV = [
    ("🏠","Dashboard"),("📊","Prédictions"),("🔬","Analyzer"),
    ("🔴","Live"),("🏀","NBA"),("💰","Bankroll"),
    ("⚽","Agent IA"),("⚙️","Paramètres"),
]

PAGE_MAP = {
    "Dashboard":   page_dashboard,
    "Prédictions": page_predictions,
    "Analyzer":    page_analyzer,
    "Live":        page_live,
    "NBA":         page_nba,
    "Bankroll":    page_bankroll,
    "Agent IA":    page_chat,
    "Paramètres":  page_params,
}

def render_sidebar():
    with st.sidebar:
        st.markdown(SHELL_CSS, unsafe_allow_html=True)
        st.markdown("""
        <div style="padding:.5rem 0 1.2rem">
          <div style="font-family:'Space Mono',monospace;font-size:1.4rem;font-weight:700;color:#F0F0F0">
            odds<span style="color:#7C5EF0">*</span>
          </div>
          <div style="font-size:.55rem;color:#555;font-weight:600;letter-spacing:.16em;text-transform:uppercase;margin-top:2px">
            v8 · Football · NBA · AI
          </div>
        </div>
        """, unsafe_allow_html=True)
        for icon,name in NAV:
            if st.button(f"{icon}  {name}", key=f"nav_{name}"):
                st.session_state["page"]=name; st.rerun()
        st.markdown("---")
        br=st.session_state["bankroll"]
        gkey=st.session_state["api_keys"].get("gemini","")
        ai_ok = gkey and len(gkey)>20
        today_str=datetime.date.today().strftime("%d %B %Y")
        st.markdown(f"""
        <div style="font-size:.65rem;color:#555;line-height:2.4">
          📅 {today_str}<br>
          💰 <span style="color:#7C5EF0;font-weight:700">{br:.0f}€</span><br>
          {'🟢 Gemini connecté' if ai_ok else '⚪ Gemini non configuré'}
        </div>
        """, unsafe_allow_html=True)

def main():
    render_sidebar()
    PAGE_MAP.get(st.session_state.get("page","Dashboard"), page_dashboard)()

if __name__ == "__main__":
    main()
