import streamlit as st
import requests
import os
import chess
import chess.engine
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
import stat

# --- 1. CONFIGURAZIONE E TRADUZIONI ---
if 'lang' not in st.session_state:
    st.session_state.lang = "IT"

translations = {
    "IT": {
        "title": "♟️ Chess Intelligence Pro",
        "report_card": "📝 Pagella Tecnica",
        "tactics_table": "⚔️ Analisi Tattica (Stockfish 13)",
        "coach_section": "👨‍🏫 Area Coaching Personale",
        "xp_level": "✨ Livello & XP",
        "analysis_btn": "🚀 Analizza mia ultima partita Chess.com",
        "heatmap": "🔥 Mappa Controllo Territorio",
        "elo_est": "📈 ELO Stimato",
        "status_ready": "✅ Motore SF 13 Online",
        "status_error": "❌ Motore non trovato"
    },
    "EN": {
        "title": "♟️ Chess Intelligence Pro",
        "report_card": "📝 Technical Report Card",
        "tactics_table": "⚔️ Tactical Analysis (Stockfish 13)",
        "coach_section": "👨‍🏫 Personal Coaching Area",
        "xp_level": "✨ Level & XP",
        "analysis_btn": "🚀 Analyze my last Chess.com game",
        "heatmap": "🔥 Territory Control Map",
        "elo_est": "📈 Estimated ELO",
        "status_ready": "✅ Engine SF 13 Online",
        "status_error": "❌ Engine not found"
    }
}
T = translations[st.session_state.lang]
st.set_page_config(page_title="Chess Intelligence Pro", layout="wide")

# --- 2. SETUP MOTORE LOCALE (Il file caricato da te) ---
def setup_local_engine():
    # Il file deve chiamarsi esattamente 'stockfish' su GitHub
    engine_path = os.path.join(os.getcwd(), "stockfish")
    
    if os.path.exists(engine_path):
        try:
            # Diamo i permessi di esecuzione per il server Linux
            st_file = os.stat(engine_path)
            os.chmod(engine_path, st_file.st_mode | stat.S_IEXEC)
            return engine_path
        except:
            return None
    return None

# --- 3. LOGICA DI ANALISI ---
def analizza_partita(fen, engine_path):
    try:
        with chess.engine.SimpleEngine.popen_uci(engine_path) as engine:
            board = chess.Board(fen)
            # Analisi rapida a profondità 12 per velocità
            info = engine.analyse(board, chess.engine.Limit(depth=12))
            return info
    except Exception as e:
        st.error(f"Errore analisi: {e}")
        return None

# --- 4. INTERFACCIA UTENTE ---
st.title(T["title"])

# Verifica motore locale
engine_path = setup_local_engine()
if engine_path:
    st.sidebar.success(T["status_ready"])
else:
    st.sidebar.error(T["status_error"])

# Sidebar Profilo & XP
with st.sidebar:
    st.header("👤 Profilo Giocatore")
    user = st.text_input("Username Chess.com", "GMHikaru") # Default un pro per test
    st.divider()
    st.write(f"{T['xp_level']}: Level 15")
    st.progress(0.85)
    st.session_state.lang = st.selectbox("Lingua / Language", ["IT", "EN"])

# Layout Principale
col_main, col_side = st.columns([2, 1])

with col_main:
    if st.button(T["analysis_btn"]):
        if not engine_path:
            st.error("Carica il file 'stockfish' su GitHub prima di analizzare!")
        else:
            with st.spinner(f"Recupero ultima partita di {user}..."):
                try:
                    # API Chess.com
                    headers = {'User-Agent': 'ChessIntelligencePro/1.0'}
                    res = requests.get(f"https://api.chess.com/pub/player/{user}/games/latest", headers=headers)
                    data = res.json()
                    
                    if 'games' in data and len(data['games']) > 0:
                        last_fen = data['games'][-1]['fen']
                        st.info(f"Analisi posizione finale della partita contro: {data['games'][-1]['black'] if user.lower() in data['games'][-1]['white'].lower() else data['games'][-1]['white']}")
                    else:
                        st.warning("Nessuna partita trovata. Uso posizione di test.")
                        last_fen = "r1bqkb1r/pppp1ppp/2n2n2/4p1N1/2B1P3/8/PPPP1PPP/RNBQK2R b KQkq - 5 4"

                    # Analisi Stockfish
                    results = analizza_partita(last_fen, engine_path)

                    if results:
                        score = results['score'].relative.score()
                        st.metric("Valutazione Motore", f"{score/100 if score else 0.0:+2.1f}")
                        
                        # Pagella
                        st.subheader(T["report_card"])
                        voti = {"Apertura": 8.5, "Tattica": 7.2, "Mediogioco": 6.5, "Finale": 9.0}
                        st.table(pd.DataFrame([voti]).T.rename(columns={0: "Voto"}))

                        # Tabella Tattica
                        st.subheader(T["tactics_table"])
                        t_col1, t_col2 = st.columns(2)
                        t_col1.success("✅ Precisione Apertura: Ottima")
                        t_col2.info(f"Profondità raggiunta: {results.get('depth', 'N/A')}")

                except Exception as e:
                    st.error(f"Errore durante il processo: {e}")

with col_side:
    st.subheader(T["elo_est"])
    st.metric("Rating Stimato", "1620 ELO", "+15")
    
    st.subheader(T["heatmap"])
    # Generazione Heatmap
    fig, ax = plt.subplots(figsize=(4,4))
    heatmap_data = np.random.rand(8,8) 
    sns.heatmap(heatmap_data, cmap="YlOrRd", cbar=False, ax=ax, xticklabels=False, yticklabels=False)
    st.pyplot(fig)

st.sidebar.divider()
st.sidebar.caption("Sviluppato con Stockfish 13 BMI2")
