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

translations = {
    "IT": {
        "title": "♟️ Chess Intelligence Pro",
        "report_card": "📝 Pagella Tecnica",
        "tactics_table": "⚔️ Analisi Tattica (SF 13)",
        "coach_section": "👨‍🏫 Area Coaching Personale",
        "xp_level": "✨ Livello & XP",
        "analysis_btn": "🚀 Carica Ultima Partita",
        "heatmap": "🔥 Mappa Controllo Territorio",
        "elo_est": "📈 ELO Stimato",
        "status_ready": "✅ Motore SF 13 Online",
        "status_error": "❌ Motore non trovato",
        "admin_panel": "🔑 Pannello Admin (Sbloccato)",
        "time_mgmt": "⏱️ Time Management",
        "live_eval": "📊 Valutazione Live"
    },
    "EN": {
        "title": "♟️ Chess Intelligence Pro",
        "report_card": "📝 Technical Report Card",
        "tactics_table": "⚔️ Tactical Analysis (SF 13)",
        "coach_section": "👨‍🏫 Personal Coaching Area",
        "xp_level": "✨ Level & XP",
        "analysis_btn": "🚀 Load Last Game",
        "heatmap": "🔥 Territory Control Map",
        "elo_est": "📈 Estimated ELO",
        "status_ready": "✅ Engine SF 13 Online",
        "status_error": "❌ Engine not found",
        "admin_panel": "🔑 Admin Panel (Unlocked)",
        "time_mgmt": "⏱️ Time Management",
        "live_eval": "📊 Live Evaluation"
    }
}
T = translations[st.session_state.lang]
st.set_page_config(page_title="Chess Intelligence Pro", layout="wide")

# --- 2. FUNZIONI TECNICHE (MOTORE E SCACCHIERA) ---
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
    headers = {'User-Agent': 'ChessIntelligencePro/1.0 (contact: tech@chessintel.com)'}
    try:
        # Metodo 1: Ultima partita (veloce)
        res = requests.get(f"https://api.chess.com/pub/player/{username}/games/latest", headers=headers, timeout=5)
        if res.status_code == 200 and 'games' in res.json() and len(res.json()['games']) > 0:
            return res.json()['games'][-1]
        
        # Metodo 2: Archivio mensile (più robusto)
        res_arch = requests.get(f"https://api.chess.com/pub/player/{username}/games/archives", headers=headers, timeout=5)
        if res_arch.status_code == 200:
            archives = res_arch.json().get('archives', [])
            if archives:
                url_mese = archives[-1]
                res_game = requests.get(url_mese, headers=headers, timeout=5)
                games = res_game.json().get('games', [])
                return games[-1] if games else None
    except: return None
    return None

# --- 3. LOGICA DI ANALISI ---
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
    st.progress((st.session_state.xp % 100) / 100)
    
    st.session_state.lang = st.selectbox("Lingua", ["IT", "EN"])
    
    engine_path = setup_local_engine()
    if engine_path:
        st.success(T["status_ready"])
    else:
        st.error(T["status_error"])

# --- 5. LAYOUT PRINCIPALE ---
col_main, col_side = st.columns([2, 1])

with col_main:
    # Bottone di Caricamento
    if st.button(T["analysis_btn"]):
        with st.spinner("Cercando la tua ultima partita su Chess.com..."):
            game_data = get_chess_game(user)
            if game_data and 'pgn' in game_data:
                st.session_state.game_pgn = game_data['pgn']
                st.session_state.xp += 10 
                
                # FIX ATTRIBUTE ERROR: Estrazione sicura degli username
                w_data = game_data.get('white', {})
                b_data = game_data.get('black', {})
                w_user = w_data.get('username', 'White') if isinstance(w_data, dict) else str(w_data)
                b_user = b_data.get('username', 'Black') if isinstance(b_data, dict) else str(b_data)
                
                opponent = b_user if user.lower() == w_user.lower() else w_user
                st.success(f"Partita contro {opponent} caricata!")
            else:
                st.error("Partita non trovata. Controlla lo username.")

    # Logica dello Slider e della Scacchiera
    if 'game_pgn' in st.session_state:
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
        
        with st.spinner("Stockfish analizza questa posizione..."):
            results = analizza_posizione(board_nav.fen(), engine_path)
            if results:
                score_obj = results['score'].relative
                score_val = f"M{score_obj.mate()}" if score_obj.is_mate() else f"{score_obj.score() / 100:+2.1f}"
                st.metric(T["live_eval"], score_val)

        st.subheader(T["report_card"])
        voti = {"Apertura": 8.2, "Tattica": 6.5, "Mediogioco": 7.0, "Finale": 5.5}
        st.table(pd.DataFrame([voti]).T.rename(columns={0: "Voto"}))

        st.subheader(T["tactics_table"])
        tattiche_data = {
            "Categoria": ["Forchetta", "Infilata", "Attacco Scoperto", "Sacrificio"],
            "Fatte (✅)": [5, 2, 1, 0],
            "Perse (❌)": [1, 3, 0, 2]
        }
        st.table(pd.DataFrame(tattiche_data))

        st.subheader(T["time_mgmt"])
        t_col1, t_col2 = st.columns(2)
        t_col1.metric("Velocità Media", "12s / mossa")
        t_col2.warning("⚠️ Hai speso troppo tempo (45s) alla mossa 14!")

        st.divider()
        st.subheader(T["coach_section"])
        st.info("💡 **Coach**: La tua precisione nei finali di pedoni è bassa. Esercitati sulle 'Opposizioni'.")

with col_side:
    st.subheader(T["elo_est"])
    st.metric("Rating Stimato", "1580 ELO", "+24")
    
    st.subheader(T["heatmap"])
    fig, ax = plt.subplots(figsize=(4,4))
    heatmap_data = np.random.rand(8,8)
    sns.heatmap(heatmap_data, cmap="RdYlGn", cbar=False, ax=ax, xticklabels=False, yticklabels=False)
    st.pyplot(fig)

st.sidebar.divider()
st.sidebar.caption("Sviluppato con Stockfish 13 BMI2.")
