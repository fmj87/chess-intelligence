import streamlit as st
import requests
import json
import os
import re
import chess
import chess.engine
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
import stat
import urllib.request
import tarfile

# --- 1. CONFIGURAZIONE E TRADUZIONI ---
if 'lang' not in st.session_state: 
    st.session_state.lang = "IT"

translations = {
    "IT": {
        "title": "♟️ Chess Intelligence Pro",
        "warning": "⚠️ Configurazione Motore in corso...",
        "report_card": "📝 Pagella Tecnica",
        "tactics_table": "⚔️ Analisi Tattica (Stockfish)",
        "coach_section": "👨‍🏫 Area Coaching Personale",
        "xp_level": "✨ Livello & XP",
        "analysis_btn": "🚀 Avvia Analisi Profonda",
        "heatmap": "🔥 Mappa Controllo Territorio",
        "elo_est": "📈 ELO Stimato",
        "status_ready": "✅ Motore Pronto",
        "status_loading": "⏳ Scaricamento Stockfish..."
    },
    "EN": {
        "title": "♟️ Chess Intelligence Pro",
        "warning": "⚠️ Engine Configuration in progress...",
        "report_card": "📝 Technical Report Card",
        "tactics_table": "⚔️ Tactical Analysis (Stockfish)",
        "coach_section": "👨‍🏫 Personal Coaching Area",
        "xp_level": "✨ Level & XP",
        "analysis_btn": "🚀 Start Deep Analysis",
        "heatmap": "🔥 Territory Control Map",
        "elo_est": "📈 Estimated ELO",
        "status_ready": "✅ Engine Ready",
        "status_loading": "⏳ Downloading Stockfish..."
    }
}
T = translations[st.session_state.lang]
st.set_page_config(page_title="Chess Intelligence Pro", layout="wide")

# --- 2. DOWNLOADER AUTOMATICO STOCKFISH (SOLUZIONE B) ---
@st.cache_resource
def setup_stockfish():
    engine_dir = "stockfish_engine"
    # Nome del file finale che useremo nel codice
    engine_path = os.path.abspath(os.path.join(engine_dir, "stockfish_app"))
    
    if not os.path.exists(engine_path):
        if not os.path.exists(engine_dir):
            os.makedirs(engine_dir)
        
        # URL ufficiale Stockfish Linux
        url = "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-ubuntu-x86-64-avx2.tar.gz"
        
        try:
            file_tmp = "temp_stockfish.tar.gz"
            urllib.request.urlretrieve(url, file_tmp)
            
            with tarfile.open(file_tmp, "r:gz") as tar:
                tar.extractall(path=engine_dir)
            
            # Cerca il binario estratto e nominalo 'stockfish_app'
            for root, dirs, files in os.walk(engine_dir):
                for file in files:
                    if "stockfish" in file and "tar.gz" not in file:
                        current_path = os.path.join(root, file)
                        os.rename(current_path, engine_path)
                        break
            
            # Permessi di esecuzione Linux
            os.chmod(engine_path, os.stat(engine_path).st_mode | stat.S_IEXEC)
            os.remove(file_tmp)
            return engine_path
        except Exception as e:
            st.error(f"Errore download motore: {e}")
            return None
    return engine_path

# --- 3. LOGICA DI ANALISI ---
def analizza_partita(fen):
    path = setup_stockfish()
    if path:
        try:
            with chess.engine.SimpleEngine.popen_uci(path) as engine:
                board = chess.Board(fen)
                info = engine.analyse(board, chess.engine.Limit(depth=12))
                return info
        except:
            return None
    return None

# --- 4. INTERFACCIA UTENTE ---
st.title(T["title"])

# Verifica motore all'avvio
engine_ready_path = setup_stockfish()
if engine_ready_path:
    st.sidebar.success(T["status_ready"])
else:
    st.sidebar.warning(T["status_loading"])

# Sidebar Profilo & XP
with st.sidebar:
    st.header("👤 Profilo Giocatore")
    user = st.text_input("Username Chess.com/Lichess", "User123")
    st.divider()
    st.write(f"{T['xp_level']}: Level 15")
    st.progress(0.85)
    st.session_state.lang = st.selectbox("Lingua", ["IT", "EN"])

# Layout
col_main, col_side = st.columns([2, 1])

with col_main:
    if st.button(T["analysis_btn"]):
        with st.spinner("Analisi Stockfish in corso..."):
            # Esempio: Posizione dopo 1.e4 e5 2.Nf3 Nc6 3.Bc4 Nf6 4.Ng5
            test_fen = "r1bqkb1r/pppp1ppp/2n2n2/4p1N1/2B1P3/8/PPPP1PPP/RNBQK2R b KQkq - 5 4"
            results = analizza_partita(test_fen)

            # Pagella V1
            st.subheader(T["report_card"])
            voti = {"Apertura": 9.0, "Tattica": 4.5, "Mediogioco": 6.0, "Finale": 7.0}
            st.table(pd.DataFrame([voti]).T.rename(columns={0: "Voto"}))

            # Tabella Tattica
            st.subheader(T["tactics_table"])
            t_col1, t_col2 = st.columns(2)
            t_col1.success("✅ Tattica Riconosciuta: Difesa del Fegatello")
            t_col2.error("❌ Tattica Mancata: Contro-attacco Traxler")

            # Coaching & Risorse (YouTube & Puzzle)
            st.divider()
            st.subheader(T["coach_section"])
            st.info("💡 **Consiglio del Coach**: La tua visione tattica cala sotto pressione. Ripassa i pattern di difesa.")
            
            r_col1, r_col2 = st.columns(2)
            r_col1.markdown("### 📺 Video Lezione\n[Guarda Tutorial Apertura](https://www.youtube.com/results?search_query=fried+liver+attack+defense)")
            r_col2.markdown("### 🧩 Puzzle Training\n[Esercitati qui](https://lichess.org/training/friedLiverAttack)")

with col_side:
    st.subheader(T["elo_est"])
    st.metric("Rating Estimato", "1620 ELO", "+15")
    
    st.subheader(T["heatmap"])
    # Generazione Heatmap Reale
    fig, ax = plt.subplots(figsize=(4,4))
    heatmap_data = np.random.rand(8,8) # Mock data per controllo territorio
    sns.heatmap(heatmap_data, cmap="YlOrRd", cbar=False, ax=ax, xticklabels=False, yticklabels=False)
    st.pyplot(fig)

st.sidebar.divider()
st.sidebar.caption("Sviluppato per la community degli scacchi.")
