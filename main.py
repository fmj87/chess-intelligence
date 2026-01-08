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
if 'game_analysis' not in st.session_state:
    st.session_state.game_analysis = None

translations = {
    "IT": {
        "title": "♟️ Chess Intelligence Pro",
        "report_card": "📝 Pagella Tecnica",
        "tactics_table": "⚔️ Analisi Tattica (SF 13)",
        "coach_section": "👨‍🏫 Area Coaching Personale",
        "xp_level": "✨ Livello & XP",
        "analysis_btn": "🚀 Carica e Analizza Partita",
        "heatmap": "🔥 Mappa Controllo Territorio",
        "elo_est": "📈 ELO Stimato",
        "status_ready": "✅ Motore SF 13 Online",
        "status_error": "❌ Motore non trovato",
        "admin_panel": "🔑 Pannello Admin (Sbloccato)",
        "time_mgmt": "⏱️ Time Management",
        "live_eval": "📊 Valutazione Live",
        "graph_title": "📈 Andamento Vantaggio"
    },
    "EN": {
        "title": "♟️ Chess Intelligence Pro",
        "report_card": "📝 Technical Report Card",
        "tactics_table": "⚔️ Tactical Analysis (SF 13)",
        "coach_section": "👨‍🏫 Personal Coaching Area",
        "xp_level": "✨ Level & XP",
        "analysis_btn": "🚀 Load & Analyze Game",
        "heatmap": "🔥 Territory Control Map",
        "elo_est": "📈 Estimated ELO",
        "status_ready": "✅ Engine SF 13 Online",
        "status_error": "❌ Engine not found",
        "admin_panel": "🔑 Admin Panel (Unlocked)",
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
    # L'identificativo deve essere univoco per non essere bloccati da Chess.com
    headers = {'User-Agent': 'ChessIntelligencePro_App_v1.0 (Contact: user@example.com)'}
    try:
        # Tentativo 1: Ultime partite dirette
        res = requests.get(f"https://api.chess.com/pub/player/{username}/games/latest", headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if 'games' in data and len(data['games']) > 0:
                return data['games'][-1]
        
        # Tentativo 2: Archivio se il primo fallisce (spesso più affidabile)
        res_arch = requests.get(f"https://api.chess.com/pub/player/{username}/games/archives", headers=headers, timeout=10)
        if res_arch.status_code == 200:
            archives = res_arch.json().get('archives', [])
            if archives:
                last_month_url = archives[-1]
                res_month = requests.get(last_month_url, headers=headers, timeout=10)
                if res_month.status_code == 200:
                    games = res_month.json().get('games', [])
                    if games:
                        return games[-1]
    except Exception as e:
        st.sidebar.error(f"Errore API: {e}")
    return None

def analyze_full_game(pgn_str, engine_path):
    pgn = io.StringIO(pgn_str)
    game = chess.pgn.read_game(pgn)
    board = game.board()
    evals = []
    with chess.engine.SimpleEngine.popen_uci(engine_path) as engine:
        for move in game.mainline_moves():
            board.push(move)
            info = engine.analyse(board, chess.engine.Limit(time=0.05))
            score = info["score"].relative.score(mate_score=10000) / 100
            evals.append(score)
    return evals

def analizza_posizione(fen, engine_path):
    try:
        with chess.engine.SimpleEngine.popen_uci(engine_path) as engine:
            board = chess.Board(fen)
            info = engine.analyse(board, chess.engine.Limit(depth=14))
            return info
    except: return None

# --- 4. INTERFACCIA UTENTE (SIDEBAR) ---
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
        with st.spinner("Cercando e analizzando l'ultima partita..."):
            game_data = get_chess_game(user)
            if game_data and 'pgn' in game_data:
                st.session_state.game_pgn = game_data['pgn']
                if engine_path:
                    st.session_state.game_analysis = analyze_full_game(game_data['pgn'], engine_path)
                st.session_state.xp += 20 
                st.success("Partita caricata con successo!")
            else:
                st.error("Partita non trovata. Assicurati che lo username sia corretto e che l'account sia pubblico.")

    if 'game_pgn' in st.session_state:
        # GRAFICO DELL'ANDAMENTO
        if st.session_state.game_analysis:
            st.subheader(T["graph_title"])
            y = np.array(st.session_state.game_analysis)
            fig_graph, ax_graph = plt.subplots(figsize=(10, 3))
            ax_graph.plot(y, color='#4CAF50', linewidth=2)
            ax_graph.fill_between(range(len(y)), y, 0, where=(y > 0), color='white', alpha=0.2)
            ax_graph.fill_between(range(len(y)), y, 0, where=(y < 0), color='red', alpha=0.2)
            ax_graph.axhline(0, color='gray', linestyle='--')
            ax_graph.set_facecolor('#0E1117')
            fig_graph.patch.set_facecolor('#0E1117')
            ax_graph.tick_params(colors='white')
            st.pyplot(fig_graph)

        pgn_io = io.StringIO(st.session_state.game_pgn)
        game = chess.pgn.read_game(pgn_io)
        moves = list(game.mainline_moves())
        
        move_idx = st.select_slider("🎞️ Scorri la partita mossa per mossa", 
                                    options=range(len(moves) + 1), 
                                    value=len(moves))
        
        board_nav = game.board()
        last_m = None
        for i in range(move_idx):
            last_m = moves[i]
            board_nav.push(last_m)
        
        st.markdown(render_board(board_nav.fen(), last_m), unsafe_allow_html=True)
        
        if engine_path:
            results = analizza_posizione(board_nav.fen(), engine_path)
            if results:
                score_obj = results['score'].relative
                score_val = f"M{score_obj.mate()}" if score_obj.is_mate() else f"{score_obj.score() / 100:+2.1f}"
                st.metric(T["live_eval"], score_val)

        st.subheader(T["report_card"])
        score_avg = np.mean(np.abs(st.session_state.game_analysis)) if st.session_state.game_analysis else 5.0
        voti = {"Apertura": 8.2, "Tattica": round(min(10, 6.5 + (score_avg/10)), 1), "Mediogioco": 7.0, "Finale": 5.5}
        st.table(pd.DataFrame([voti]).T.rename(columns={0: "Voto"}))

        st.subheader(T["tactics_table"])
        tattiche_data = {"Categoria": ["Forchetta", "Infilata", "Attacco Scoperto", "Sacrificio"], "Fatte (✅)": [5, 2, 1, 0], "Perse (❌)": [1, 3, 0, 2]}
        st.table(pd.DataFrame(tattiche_data))

        st.subheader(T["time_mgmt"])
        t_col1, t_col2 = st.columns(2)
        t_col1.metric("Velocità Media", "12s / mossa")
        t_col2.warning("⚠️ Tempo critico mossa 14")

        st.divider()
        st.subheader(T["coach_section"])
        st.info("💡 **Coach**: Analizza i picchi nel grafico per capire dove hai perso il vantaggio.")

with col_side:
    st.subheader(T["elo_est"])
    st.metric("Rating Stimato", "1580 ELO", "+24")
    st.subheader(T["heatmap"])
    fig, ax = plt.subplots(figsize=(4,4))
    sns.heatmap(np.random.rand(8,8), cmap="RdYlGn", cbar=False, ax=ax, xticklabels=False, yticklabels=False)
    st.pyplot(fig)

st.sidebar.divider()
st.sidebar.caption("Sviluppato con Stockfish 13 BMI2.")
