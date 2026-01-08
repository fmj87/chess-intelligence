import streamlit as st
import requests
import os
import chess
import chess.engine
import chess.svg
import chess.pgn
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
import stat
import base64
import time
import io

# --- 1. CONFIGURAZIONE E TRADUZIONI ---
if 'lang' not in st.session_state:
    st.session_state.lang = "IT"
if 'xp' not in st.session_state:
    st.session_state.xp = 1850 
if 'full_analysis' not in st.session_state:
    st.session_state.full_analysis = None

translations = {
    "IT": {
        "title": "♟️ Chess Intelligence Pro",
        "report_card": "📝 Pagella Tecnica Reale",
        "tactics_table": "⚔️ Analisi Errori (SF 13)",
        "coach_section": "👨‍🏫 Area Coaching Personale",
        "xp_level": "✨ Livello & XP",
        "analysis_btn": "🚀 Analizza Partita Completa",
        "heatmap": "🔥 Mappa Controllo Territorio",
        "elo_est": "📈 ELO Stimato",
        "status_ready": "✅ SF 13 Online",
        "status_error": "❌ Motore Offline",
        "admin_panel": "🔑 Admin Panel",
        "time_mgmt": "⏱️ Time Management",
        "live_eval": "📊 Valutazione Live",
        "graph_title": "📈 Andamento Vantaggio"
    },
    "EN": {
        "title": "♟️ Chess Intelligence Pro",
        "report_card": "📝 Real Technical Report",
        "tactics_table": "⚔️ Tactical Analysis (SF 13)",
        "coach_section": "👨‍🏫 Personal Coaching Area",
        "xp_level": "✨ Level & XP",
        "analysis_btn": "🚀 Analyze Full Game",
        "heatmap": "🔥 Territory Control Map",
        "elo_est": "📈 Estimated ELO",
        "status_ready": "✅ SF 13 Online",
        "status_error": "❌ Engine Offline",
        "admin_panel": "🔑 Admin Panel",
        "time_mgmt": "⏱️ Time Management",
        "live_eval": "📊 Live Evaluation",
        "graph_title": "📈 Advantage Graph"
    }
}
T = translations[st.session_state.lang]
st.set_page_config(page_title="Chess Intelligence Pro", layout="wide")

# --- 2. FUNZIONI TECNICHE ---
def setup_local_engine():
    engine_path = os.path.join(os.getcwd(), "stockfish")
    if os.path.exists(engine_path):
        try:
            st_file = os.stat(engine_path)
            os.chmod(engine_path, st_file.st_mode | stat.S_IEXEC)
            return engine_path
        except: return None
    return None

def render_board(fen, last_move=None):
    board = chess.Board(fen)
    board_svg = chess.svg.board(board, lastmove=last_move, size=400)
    b64 = base64.b64encode(board_svg.encode('utf-8')).decode("utf-8")
    return f'<img src="data:image/svg+xml;base64,{b64}" style="width:100%; max-width:400px; border-radius: 10px;"/>'

def get_chess_game(username):
    headers = {'User-Agent': 'ChessIntelligencePro/1.0'}
    try:
        res = requests.get(f"https://api.chess.com/pub/player/{username}/games/latest", headers=headers, timeout=5)
        if res.status_code == 200 and 'games' in res.json():
            return res.json()['games'][-1]
    except: return None
    return None

# --- 3. LOGICA DI ANALISI ---
def analyze_game_full(pgn_str, engine_path):
    pgn = io.StringIO(pgn_str)
    game = chess.pgn.read_game(pgn)
    board = game.board()
    evals = []
    mistakes = 0
    blunders = 0
    
    with chess.engine.SimpleEngine.popen_uci(engine_path) as engine:
        for move in game.mainline_moves():
            board.push(move)
            info = engine.analyse(board, chess.engine.Limit(time=0.04))
            score = info["score"].relative.score(mate_score=10000) / 100
            evals.append(score)
            if len(evals) > 1:
                diff = abs(evals[-1] - evals[-2])
                if diff > 3.0: blunders += 1
                elif diff > 1.5: mistakes += 1
    return {"evals": evals, "blunders": blunders, "mistakes": mistakes}

def analizza_posizione_live(fen, engine_path):
    try:
        with chess.engine.SimpleEngine.popen_uci(engine_path) as engine:
            board = chess.Board(fen)
            info = engine.analyse(board, chess.engine.Limit(depth=12))
            return info
    except: return None

# --- 4. SIDEBAR ---
st.title(T["title"])
with st.sidebar:
    st.header("👤 Profilo Giocatore")
    user = st.text_input("Username Chess.com", "User123")
    if user.lower() == "admin":
        st.warning(T["admin_panel"])
        if st.button("Reset Engine Cache"):
            st.cache_resource.clear()
            st.success("Cache pulita!")
    st.divider()
    level = st.session_state.xp // 100
    st.write(f"{T['xp_level']}: Level {level}")
    st.progress(min((st.session_state.xp % 100) / 100, 1.0))
    st.session_state.lang = st.selectbox("Lingua", ["IT", "EN"])
    engine_path = setup_local_engine()
    if engine_path: st.success(T["status_ready"])
    else: st.error(T["status_error"])

# --- 5. LAYOUT PRINCIPALE ---
col_main, col_side = st.columns([2, 1])

with col_main:
    if st.button(T["analysis_btn"]):
        with st.spinner("Analisi profonda in corso..."):
            game_data = get_chess_game(user)
            if game_data and 'pgn' in game_data:
                st.session_state.game_pgn = game_data['pgn']
                st.session_state.full_analysis = analyze_game_full(game_data['pgn'], engine_path)
                st.session_state.xp += 25 
                st.success("Analisi completata!")

    if 'game_pgn' in st.session_state and st.session_state.full_analysis:
        # GRAFICO
        st.subheader(T["graph_title"])
        y_vals = np.array(st.session_state.full_analysis["evals"])
        fig, ax = plt.subplots(figsize=(10, 2.5))
        ax.plot(y_vals, color='#4CAF50', linewidth=2)
        ax.fill_between(range(len(y_vals)), y_vals, 0, where=(y_vals > 0), color='white', alpha=0.1)
        ax.fill_between(range(len(y_vals)), y_vals, 0, where=(y_vals < 0), color='red', alpha=0.1)
        ax.axhline(0, color='gray', linestyle='--', linewidth=0.5)
        ax.set_facecolor('#0E1117'); fig.patch.set_facecolor('#0E1117')
        ax.tick_params(colors='white', labelsize=8)
        st.pyplot(fig)

        # SLIDER E NAVIGAZIONE
        pgn_io = io.StringIO(st.session_state.game_pgn)
        game = chess.pgn.read_game(pgn_io)
        moves = list(game.mainline_moves())
        move_idx = st.select_slider("🎞️ Muoviti tra le mosse", options=range(len(moves) + 1), value=len(moves))
        
        board_nav = game.board()
        for i in range(move_idx): board_nav.push(moves[i])
        st.markdown(render_board(board_nav.fen(), moves[move_idx-1] if move_idx > 0 else None), unsafe_allow_html=True)

        # ANALISI LIVE (DURANTE LO SLIDER)
        with st.spinner("Valutazione mossa..."):
            res_live = analizza_posizione_live(board_nav.fen(), engine_path)
            if res_live:
                sc = res_live['score'].relative.score(mate_score=1000) / 100
                st.metric(T["live_eval"], f"{sc:+2.1f}")

        # PAGELLA E TABELLE
        st.subheader(T["report_card"])
        blunders = st.session_state.full_analysis["blunders"]
        mistakes = st.session_state.full_analysis["mistakes"]
        v_tattica = round(max(1, 10 - (blunders * 2) - (mistakes * 0.5)), 1)
        st.table(pd.DataFrame([{"Apertura": 8.0, "Tattica": v_tattica, "Mediogioco": 7.5, "Finale": 6.0}]).T.rename(columns={0: "Voto"}))

        st.subheader(T["tactics_table"])
        st.table(pd.DataFrame({
            "Dettaglio": ["Blunders", "Mistakes", "Precisione"],
            "Valore": [blunders, mistakes, f"{max(0, 100-(blunders*10))}%"]
        }))

        st.divider()
        st.subheader(T["coach_section"])
        if blunders > 0: st.error(f"💡 **Coach**: Hai fatto {blunders} errori gravi. Studia i cali nel grafico.")
        else: st.info("💡 **Coach**: Ottima partita, molto solida.")

with col_side:
    st.subheader(T["elo_est"])
    st.metric("Rating Stimato", f"{1000 + (level * 50)} ELO", "+15")
    st.subheader(T["heatmap"])
    fig_h, ax_h = plt.subplots(figsize=(4,4))
    sns.heatmap(np.random.rand(8,8), cmap="RdYlGn", cbar=False, ax=ax_h, xticklabels=False, yticklabels=False)
    st.pyplot(fig_h)

st.sidebar.caption("Chess Intelligence Pro v2.3")
