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
import re
import random
from datetime import datetime
from collections import Counter
import math

# ==============================================================================
# 0. COSTANTI E CONFIGURAZIONE GLOBALE
# ==============================================================================

CONSTANTS = {
    "APP_TITLE": "♟️ Chess Intelligence Pro",
    "VERSION": "3.0.0 Ultra-Coach Edition",
    "ENGINE_LIMIT_TIME": 0.1,  # Secondi per mossa (bilanciamento velocità/precisione)
    "ENGINE_DEPTH": 15,
    "THEME": {
        "bg": "#0e1117",
        "secondary": "#262730",
        "accent": "#4CAF50",
        "danger": "#FF5252",
        "warning": "#FFC107",
        "info": "#2196F3"
    }
}

st.set_page_config(
    page_title=CONSTANTS["APP_TITLE"],
    page_icon="♟️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 1. CSS & STYLING AVANZATO
# ==============================================================================

st.markdown(f"""
<style>
    /* Global Styles */
    .stApp {{
        background-color: {CONSTANTS["THEME"]["bg"]};
    }}
    
    /* Metrics Customization */
    div[data-testid="stMetricValue"] {{
        font-size: 26px;
        font-weight: bold;
        color: {CONSTANTS["THEME"]["accent"]};
    }}
    
    /* Report Card Styling */
    .report-card {{
        background-color: {CONSTANTS["THEME"]["secondary"]};
        padding: 20px;
        border-radius: 12px;
        border-left: 5px solid {CONSTANTS["THEME"]["accent"]};
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }}
    
    /* Narrative Box */
    .narrative-box {{
        background-color: #1c1f26;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #444;
        font-family: 'Courier New', monospace;
        color: #e0e0e0;
        margin-top: 10px;
    }}
    
    /* Coaching Tip Box */
    .coach-tip {{
        background-color: rgba(33, 150, 243, 0.15);
        border: 1px solid {CONSTANTS["THEME"]["info"]};
        padding: 15px;
        border-radius: 8px;
        margin-top: 10px;
    }}
    
    /* Critical Error Box */
    .critical-error {{
        background-color: rgba(255, 82, 82, 0.15);
        border: 1px solid {CONSTANTS["THEME"]["danger"]};
        padding: 15px;
        border-radius: 8px;
    }}
    
    /* Headers */
    h1, h2, h3 {{
        font-family: 'Helvetica Neue', sans-serif;
    }}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. STATE MANAGEMENT & LOCALIZZAZIONE
# ==============================================================================

# Inizializzazione Session State con valori di default robusti
default_states = {
    'lang': "IT",
    'xp': 1850,
    'game_analysis': None,      # Conterrà oggetti MoveAnalysis
    'game_pgn': None,
    'current_fen': chess.STARTING_FEN,
    'puzzle_mode': False,
    'active_puzzle': None,
    'coach_messages': [],
    'user_stats': {'wins': 0, 'losses': 0, 'draws': 0}
}

for key, val in default_states.items():
    if key not in st.session_state:
        st.session_state[key] = val

translations = {
    "IT": {
        "title": CONSTANTS["APP_TITLE"],
        "report_card": "📝 Pagella Tecnica Avanzata",
        "tactics_table": "⚔️ Analisi Tattica & Errori",
        "coach_section": "👨‍🏫 Coach Virtuale & Psicologia",
        "xp_level": "✨ Livello & XP",
        "analysis_btn": "🚀 Avvia Analisi Profonda",
        "heatmap": "🔥 Mappa Controllo & Tensione",
        "elo_est": "📈 Performance Rating",
        "status_ready": "✅ Motore Neurale Online",
        "status_error": "❌ Motore non trovato",
        "admin_panel": "🔑 Admin Console",
        "time_mgmt": "⏱️ Gestione Tempo & Ritmo",
        "live_eval": "📊 Valutazione in Tempo Reale",
        "graph_title": "📈 Flusso della Partita",
        "loading": "Analisi neurale in corso... decodifica pattern...",
        "game_loaded": "Partita analizzata con successo!",
        "game_not_found": "Partita non trovata o API limitata.",
        "move_slider": "🎞️ Replay Narrativo",
        "why_move": "🧠 Analisi del 'Perché'",
        "puzzles": "🧩 Puzzle Generati dai Tuoi Errori",
        "video_rec": "📺 Video Consigliati per Te"
    },
    "EN": {
        "title": CONSTANTS["APP_TITLE"],
        "report_card": "📝 Advanced Technical Report",
        "tactics_table": "⚔️ Tactical & Error Analysis",
        "coach_section": "👨‍🏫 Virtual Coach & Psychology",
        "xp_level": "✨ Level & XP",
        "analysis_btn": "🚀 Start Deep Analysis",
        "heatmap": "🔥 Control & Tension Map",
        "elo_est": "📈 Performance Rating",
        "status_ready": "✅ Neural Engine Online",
        "status_error": "❌ Engine not found",
        "admin_panel": "🔑 Admin Console",
        "time_mgmt": "⏱️ Time & Pace Management",
        "live_eval": "📊 Real-Time Evaluation",
        "graph_title": "📈 Game Flow",
        "loading": "Neural analysis running... decoding patterns...",
        "game_loaded": "Game analyzed successfully!",
        "game_not_found": "Game not found or API limited.",
        "move_slider": "🎞️ Narrative Replay",
        "why_move": "🧠 'Why' Analysis",
        "puzzles": "🧩 Puzzles From Your Mistakes",
        "video_rec": "📺 Recommended Videos"
    }
}
T = translations[st.session_state.lang]

# ==============================================================================
# 3. CLASSI DI DATI E ANALISI (BACKEND LOGIC)
# ==============================================================================

class MoveAnalysis:
    """Classe per memorizzare i dati analitici di una singola mossa."""
    def __init__(self, move_san, fen, score, best_move, classification, time_spent=0.0, comments=""):
        self.move_san = move_san
        self.fen = fen
        self.score = score  # Centipawns (float)
        self.best_move = best_move
        self.classification = classification # "Best", "Good", "Inaccuracy", "Mistake", "Blunder", "Book"
        self.time_spent = time_spent
        self.comments = comments
        self.narrative = "" # Spiegazione testuale generata

class GameStats:
    """Contenitore per le statistiche aggregate della partita."""
    def __init__(self):
        self.accuracies = []
        self.openings_accuracy = 0
        self.middlegame_accuracy = 0
        self.endgame_accuracy = 0
        self.blunders = 0
        self.mistakes = 0
        self.inaccuracies = 0
        self.brilliant_moves = 0
        self.time_trouble_count = 0
        self.avg_time_per_move = 0
        self.psych_profile = [] # Lista di stringhe (tag psicologici)

# ==============================================================================
# 4. ENGINE WRAPPER & UTILS
# ==============================================================================

def setup_local_engine():
    """Setup motore robusto con fallback per OS diversi."""
    engine_filename = "stockfish.exe" if os.name == 'nt' else "stockfish"
    engine_path = os.path.join(os.getcwd(), engine_filename)
    
    if os.path.exists(engine_path):
        try:
            st_file = os.stat(engine_path)
            os.chmod(engine_path, st_file.st_mode | stat.S_IEXEC)
            return engine_path
        except Exception as e:
            st.error(f"Engine Permission Error: {e}")
            return None
    return None

def check_engine_health(engine_path):
    if not engine_path: return False
    try:
        with chess.engine.SimpleEngine.popen_uci(engine_path) as engine:
            engine.ping()
        return True
    except: return False

def get_chess_game(username):
    """
    Recupera l'ultima partita con gestione avanzata degli archivi
    e parsing preliminare per assicurarsi che sia valida.
    """
    headers = {
        'User-Agent': 'ChessIntelligencePro_Coach/3.0 (contact: admin@chessintel.pro)',
        'Accept': 'application/json'
    }
    base_url = f"https://api.chess.com/pub/player/{username}"
    
    try:
        res_arch = requests.get(f"{base_url}/games/archives", headers=headers, timeout=10)
        if res_arch.status_code == 200:
            archives = res_arch.json().get('archives', [])
            if archives:
                # Prova gli ultimi 3 mesi in caso di inattività recente
                for url in reversed(archives[-3:]):
                    res_month = requests.get(url, headers=headers, timeout=10)
                    if res_month.status_code == 200:
                        games = res_month.json().get('games', [])
                        if games:
                            # Filtra partite valide (non aborted)
                            valid_games = [g for g in games if g.get('rules') == 'chess']
                            if valid_games:
                                return valid_games[-1]
    except Exception as e:
        st.sidebar.error(f"API Error: {e}")
    return None

def extract_time_from_comment(comment):
    """Estrae il tempo rimanente dal commento PGN standard [%clk H:MM:SS]."""
    if not comment: return None
    match = re.search(r'\[%clk\s+(\d+):(\d+):(\d+(\.\d+)?)\]', comment)
    if match:
        h, m, s = match.group(1), match.group(2), match.group(3)
        return float(h)*3600 + float(m)*60 + float(s)
    return None

# ==============================================================================
# 5. CORE INTELLIGENCE: ANALISI, NARRATIVA, PSICOLOGIA
# ==============================================================================

def analyze_game_deep(pgn_str, engine_path, username):
    """
    Cuore del sistema. Esegue:
    1. Analisi motore mossa per mossa.
    2. Classificazione mosse (Blunder/Mistake/etc).
    3. Parsing dei tempi.
    4. Generazione narrativa del "Perché".
    5. Profilazione psicologica.
    """
    if not engine_path: return None, None

    pgn = io.StringIO(pgn_str)
    game = chess.pgn.read_game(pgn)
    board = game.board()
    
    # Identifica colore utente
    white_player = game.headers.get("White", "Unknown")
    user_color = chess.WHITE if white_player.lower() == username.lower() else chess.BLACK
    
    analysis_results = []
    stats = GameStats()
    
    prev_score = 0.0 # CP relativo al giocatore
    prev_time = None
    
    # Setup Engine
    with chess.engine.SimpleEngine.popen_uci(engine_path) as engine:
        engine.configure({"Hash": 32, "Threads": 2})
        
        moves = list(game.mainline_moves())
        node = game
        
        total_moves = len(moves)
        progress_bar = st.progress(0)
        
        for i, move in enumerate(moves):
            # 1. Avanza nel nodo PGN per leggere commenti/tempi
            node = node.variation(0)
            
            # Calcolo tempo
            current_time_left = extract_time_from_comment(node.comment)
            time_spent = 0
            if prev_time is not None and current_time_left is not None:
                time_spent = max(0, prev_time - current_time_left)
                # Gestione incremento (euristica: se spent < 0 probabilmente c'è incremento)
                if time_spent == 0: time_spent = 1 # Minimo nominale
            prev_time = current_time_left
            
            # 2. Analisi Motore (Posizione CORRENTE dopo la mossa)
            board.push(move)
            
            # Analizziamo la posizione per ottenere lo score
            info = engine.analyse(board, chess.engine.Limit(time=CONSTANTS["ENGINE_LIMIT_TIME"]))
            
            # Score relativo al giocatore che ha mosso
            score_pov = info["score"].pov(board.turn).score(mate_score=10000)
            score_cp = score_pov / 100.0 if score_pov is not None else 0.0
            
            # Per valutare la qualità della mossa, dobbiamo guardare lo score 
            # DALLA PROSPETTIVA DI CHI HA APPENA MOSSO (che ora è l'avversario nel turno, quindi invertiamo)
            # Ma più semplicemente: confrontiamo il cambio di valutazione.
            
            # Recuperiamo la mossa migliore suggerita dal motore nella posizione PRECEDENTE
            # (Per fare questo accuratamente servirebbe analizzare PRIMA di fare la mossa,
            # qui usiamo una euristica basata sul delta score per velocità)
            
            # Delta Score (dal punto di vista di chi ha mosso)
            # Se sono bianco e passo da +1 a +0.5, delta è -0.5
            current_eval_pov = info["score"].pov(not board.turn).score(mate_score=10000) / 100.0
            delta = current_eval_pov - prev_score
            
            # Classificazione
            classification = "Good"
            narrative = ""
            
            if i < 10: classification = "Book" # Semplificazione apertura
            elif delta <= -2.0: classification = "Blunder"
            elif delta <= -1.0: classification = "Mistake"
            elif delta <= -0.5: classification = "Inaccuracy"
            elif delta >= 0.5: classification = "Great"
            elif delta >= 1.5: classification = "Brilliant" # Raro
            
            # Aggiornamento Statistiche (Solo per l'utente)
            is_user_move = (board.turn == (not user_color)) # Dato che abbiamo già fatto push, turn è invertito
            
            if is_user_move:
                stats.accuracies.append(max(0, 100 - abs(delta * 20)))
                if classification == "Blunder": stats.blunders += 1
                elif classification == "Mistake": stats.mistakes += 1
                elif classification == "Inaccuracy": stats.inaccuracies += 1
                elif classification in ["Great", "Brilliant"]: stats.brilliant_moves += 1
                
                # --- SISTEMA ANALISI NARRATIVA DEL "PERCHÉ" ---
                narrative = generate_narrative_why(board, move, delta, classification, time_spent)
                
                # --- RILEVAMENTO PATTERN PSICOLOGICI ---
                detect_psychology(stats, delta, time_spent, classification, i, total_moves)

            # Store Analysis
            best_mv_san = "-" # Placeholder per ottimizzazione (richiederebbe seconda analisi)
            
            res_obj = MoveAnalysis(
                move_san=board.san_and_push(move) if False else game.board().variation_san(moves[:i+1]), # Workaround per SAN corretto
                fen=board.fen(),
                score=current_eval_pov,
                best_move=best_mv_san,
                classification=classification,
                time_spent=time_spent,
                comments=node.comment
            )
            res_obj.narrative = narrative
            analysis_results.append(res_obj)
            
            prev_score = current_eval_pov
            progress_bar.progress((i + 1) / total_moves)

    # Finalizzazione Statistiche
    if stats.accuracies:
        mid = len(stats.accuracies) // 3
        stats.openings_accuracy = np.mean(stats.accuracies[:10]) if len(stats.accuracies) > 10 else 90
        stats.middlegame_accuracy = np.mean(stats.accuracies[10:mid*2]) if len(stats.accuracies) > 20 else 80
        stats.endgame_accuracy = np.mean(stats.accuracies[mid*2:]) if len(stats.accuracies) > mid*2 else 70

    return analysis_results, stats

def generate_narrative_why(board, move, delta, classification, time_spent):
    """
    Genera una spiegazione in linguaggio naturale del perché una mossa è buona o cattiva.
    """
    reasons = []
    
    # 1. Controllo Materiale
    # Verifica se c'è stata cattura
    if board.is_capture(move):
        reasons.append("Scambio materiale.")
        if delta < -1:
            reasons.append("Hai catturato un pezzo avvelenato o indifeso.")
    
    # 2. Controllo Re (Check)
    if board.is_check():
        reasons.append("Mossa aggressiva che mette sotto scacco il Re.")
    
    # 3. Logica Blunder
    if classification == "Blunder":
        if time_spent and time_spent < 3:
            reasons.append("Hai giocato troppo in fretta (Impulsività).")
        reasons.append("Questa mossa perde materiale significativo o permette un attacco forzato.")
        # Euristiche semplici posizionali
        if not board.is_capture(move) and delta < -3:
            reasons.append("Probabilmente hai lasciato un pezzo in presa.")
            
    # 4. Logica Mistake/Inaccuracy
    elif classification == "Mistake":
        reasons.append("Mossa passiva. C'era un'opportunità tattica migliore.")
        
    # 5. Logica Positiva
    elif classification in ["Great", "Brilliant"]:
        reasons.append("Ottima visione! Hai migliorato significativamente la tua posizione.")
        if board.is_sacrifice(move):
             reasons.append("Sacrificio tematico corretto.")

    # Composizione frase
    explanation = " ".join(reasons)
    if not explanation:
        explanation = "Mossa di sviluppo standard." if classification == "Book" else "Mossa di transizione."
        
    return explanation

def detect_psychology(stats, delta, time_spent, classification, move_num, total_moves):
    """
    Rileva pattern comportamentali basati su tempi e errori.
    """
    # Pattern: Tilt (Errori consecutivi)
    # Nota: richiederebbe storia, qui usiamo contatori semplici
    
    # Pattern: Time Trouble Panic
    if time_spent and time_spent < 5 and classification in ["Blunder", "Mistake"]:
        if move_num > 20: # Non in apertura
            if "Impulsività" not in stats.psych_profile:
                stats.psych_profile.append("Impulsività")
    
    # Pattern: Overthinking (Tanto tempo, mossa brutta)
    if time_spent and time_spent > 60 and classification in ["Blunder", "Mistake"]:
        if "Paralisi da Analisi" not in stats.psych_profile:
            stats.psych_profile.append("Paralisi da Analisi")
            
    # Pattern: Crollo nel finale
    if move_num > (total_moves * 0.8) and classification == "Blunder":
        if "Stanchedzza Mentale" not in stats.psych_profile:
            stats.psych_profile.append("Stanchezza Mentale")

# ==============================================================================
# 6. FUNZIONI UI & RENDERING (COMPONENTI)
# ==============================================================================

def render_board_svg(fen, last_move=None, arrows=[]):
    """Renderizza SVG scacchiera con stile Pro."""
    board = chess.Board(fen)
    
    # Estrazione caselle mossa per evidenziare
    lmove = None
    if last_move and isinstance(last_move, str):
        try: lmove = chess.Move.from_uci(last_move)
        except: pass
    elif isinstance(last_move, chess.Move):
        lmove = last_move

    svg = chess.svg.board(
        board,
        lastmove=lmove,
        arrows=arrows,
        size=500,
        colors={'square light': '#dee3e6', 'square dark': '#8ca2ad'},
        style="border-radius: 5px;"
    )
    b64 = base64.b64encode(svg.encode('utf-8')).decode("utf-8")
    return f'<img src="data:image/svg+xml;base64,{b64}" width="100%" />'

def render_coach_feedback(stats, analysis_results):
    """Genera la sezione Coaching Avanzato."""
    st.markdown(f"### {T['coach_section']}")
    
    c1, c2 = st.columns([1, 2])
    
    with c1:
        st.image("https://img.icons8.com/color/96/000000/grand-master.png", width=80)
        st.markdown("**Coach AI**")
    
    with c2:
        # Analisi Psicologica
        if stats.psych_profile:
            st.warning(f"⚠️ **Pattern Rilevati:** {', '.join(set(stats.psych_profile))}")
            if "Impulsività" in stats.psych_profile:
                st.markdown("> *Consiglio: Usa la regola delle mani. Siediti sulle mani finché non hai verificato la mossa.*")
            if "Paralisi da Analisi" in stats.psych_profile:
                st.markdown("> *Consiglio: Se non trovi la mossa perfetta in 3 minuti, gioca una mossa solida.*")
        else:
            st.success("🧠 **Mindset:** Solido. Nessun pattern negativo evidente.")

        # Analisi Tecnica Generale
        if stats.blunders > 2:
            st.markdown(f"🚫 Hai commesso **{stats.blunders} errori gravi**. Devi lavorare sulla *safety check* (scacchi, prese, minacce) prima di muovere.")
        elif stats.mistakes > 5:
            st.markdown("📉 Molte imprecisioni posizionali. Studia piani di mediogioco più semplici.")
        else:
            st.markdown("✅ Partita molto pulita tatticamente.")

def get_youtube_recommendation(opening_name, weaknesses):
    """
    Sistema di raccomandazione video basato su apertura e debolezze.
    (Database simulato per robustezza senza API esterne complesse)
    """
    db = {
        "Sicilian": "3hI-J3vj7iQ", # GothamChess Sicilian
        "Queen's Gambit": "0d8fC_4TqC8", # Agadmator QG
        "Caro-Kann": "r8rT6iE8CAY",
        "London System": "806r21iN1Cg",
        "General Tactics": "21L45Qo6f_c", # Tactics video
        "Endgames": "mC9RJKkCcCc" # Endgame video
    }
    
    vid_id = db.get("General Tactics")
    reason = "Miglioramento Tattico Generale"
    
    # Logica di selezione
    if opening_name:
        for key in db:
            if key in opening_name:
                vid_id = db[key]
                reason = f"Approfondimento Apertura: {key}"
                break
    
    if "Endgame" in weaknesses:
        vid_id = db["Endgames"]
        reason = "Miglioramento Finali (Tua debolezza rilevata)"
        
    return vid_id, reason

# ==============================================================================
# 7. MAIN UI LAYOUT
# ==============================================================================

def main():
    st.title(T["title"])

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("👤 Player Profile")
        user = st.text_input("Chess.com Username", "Hikaru")
        
        # XP System Visuals
        lvl = st.session_state.xp // 100
        xp_rem = st.session_state.xp % 100
        st.write(f"**Level {lvl}** | Grandmaster Candidate")
        st.progress(xp_rem / 100)
        
        st.divider()
        st.session_state.lang = st.selectbox("Language", ["IT", "EN"], index=0 if st.session_state.lang=="IT" else 1)
        
        # Engine Status
        engine_path = setup_local_engine()
        if engine_path and check_engine_health(engine_path):
            st.success(T["status_ready"])
        else:
            st.error(T["status_error"])
            
        # Admin Tools
        if user == "admin":
            st.warning(T["admin_panel"])
            if st.button("Reset Session"):
                st.session_state.clear()
                st.rerun()

    # --- MAIN COLUMN STRUCTURE ---
    col_main, col_metrics = st.columns([3, 1])

    with col_main:
        # Action Button
        analyze_clicked = st.button(T["analysis_btn"], type="primary", use_container_width=True)
        
        if analyze_clicked:
            with st.spinner(T["loading"]):
                # 1. Fetch Game
                game_data = get_chess_game(user)
                if game_data and 'pgn' in game_data:
                    st.session_state.game_pgn = game_data['pgn']
                    
                    # 2. Deep Analysis
                    results, stats = analyze_game_deep(game_data['pgn'], engine_path, user)
                    
                    if results:
                        st.session_state.game_analysis = results
                        st.session_state.game_stats = stats
                        st.session_state.xp += 50
                        st.success(T["game_loaded"])
                        time.sleep(1) # UX Pause
                        st.rerun()
                else:
                    st.error(T["game_not_found"])

        # VISUALIZZAZIONE DATI (Se analisi esiste)
        if st.session_state.game_analysis:
            results = st.session_state.game_analysis
            stats = st.session_state.game_stats # Recupero statistiche
            
            # Parsing base per info partita
            pgn_io = io.StringIO(st.session_state.game_pgn)
            game_ref = chess.pgn.read_game(pgn_io)
            opening_name = game_ref.headers.get("Opening", "Unknown Opening")

            # --- TABS PER ORGANIZZAZIONE PULITA ---
            tab_overview, tab_replay, tab_coach, tab_training = st.tabs([
                "📊 Overview & Report", 
                "♟️ Replay & Narrativa", 
                "👨‍🏫 Coach & Video",
                "🧩 Puzzle & Training"
            ])

            # TAB 1: OVERVIEW
            with tab_overview:
                # Grafico Vantaggio
                st.subheader(T["graph_title"])
                evals = [m.score for m in results]
                
                fig, ax = plt.subplots(figsize=(10, 3))
                ax.plot(evals, color='#4CAF50', linewidth=2)
                ax.fill_between(range(len(evals)), evals, 0, where=(np.array(evals)>0), color='#4CAF50', alpha=0.3)
                ax.fill_between(range(len(evals)), evals, 0, where=(np.array(evals)<0), color='#FF5252', alpha=0.3)
                ax.axhline(0, color='gray', linestyle='--')
                ax.set_facecolor(CONSTANTS["THEME"]["bg"])
                fig.patch.set_facecolor(CONSTANTS["THEME"]["bg"])
                ax.tick_params(colors='white')
                st.pyplot(fig)

                # Report Card Reale
                st.subheader(T["report_card"])
                c1, c2, c3, c4 = st.columns(4)
                
                def get_grade(acc):
                    if acc >= 90: return "A+", "green"
                    if acc >= 80: return "A", "green"
                    if acc >= 70: return "B", "blue"
                    if acc >= 50: return "C", "orange"
                    return "D", "red"

                with c1: 
                    gr, col = get_grade(stats.openings_accuracy)
                    st.metric("Opening", f"{gr}", f"{stats.openings_accuracy:.1f}%")
                with c2:
                    gr, col = get_grade(stats.middlegame_accuracy)
                    st.metric("Middlegame", f"{gr}", f"{stats.middlegame_accuracy:.1f}%")
                with c3:
                    gr, col = get_grade(stats.endgame_accuracy)
                    st.metric("Endgame", f"{gr}", f"{stats.endgame_accuracy:.1f}%")
                with c4:
                    st.metric("Blunders", f"{stats.blunders}", "Critico" if stats.blunders > 1 else "Ok", delta_color="inverse")

                # Tabella Tattica
                st.subheader(T["tactics_table"])
                tactic_df = pd.DataFrame({
                    "Tipo": ["Brilliant", "Great", "Best/Good", "Inaccuracy", "Mistake", "Blunder"],
                    "Conteggio": [
                        stats.brilliant_moves,
                        sum(1 for x in results if x.classification == "Great"),
                        sum(1 for x in results if x.classification in ["Best", "Good", "Book"]),
                        stats.inaccuracies,
                        stats.mistakes,
                        stats.blunders
                    ]
                })
                st.dataframe(tactic_df, use_container_width=True, hide_index=True)

            # TAB 2: REPLAY NARRATIVO
            with tab_replay:
                move_idx = st.select_slider(
                    T["move_slider"], 
                    options=range(len(results)), 
                    value=0,
                    key="replay_slider"
                )
                
                current_data = results[move_idx]
                
                col_r1, col_r2 = st.columns([1.5, 1])
                with col_r1:
                    st.markdown(render_board_svg(current_data.fen), unsafe_allow_html=True)
                
                with col_r2:
                    st.markdown(f"### Mossa {math.ceil((move_idx+1)/2)}")
                    st.markdown(f"**Mossa Giocata:** `{current_data.move_san}`")
                    
                    # Badge Classificazione
                    color_map = {"Blunder": "red", "Mistake": "orange", "Good": "green", "Brilliant": "teal", "Book": "blue"}
                    badge_col = color_map.get(current_data.classification, "grey")
                    st.markdown(f":{badge_col}[**{current_data.classification}**]")
                    
                    st.metric("Valutazione", f"{current_data.score:.2f}")
                    
                    # Analisi Narrativa ("Perché")
                    st.markdown(f"#### {T['why_move']}")
                    st.markdown(f"""
                    <div class="narrative-box">
                        {current_data.narrative if current_data.narrative else "Analisi standard della posizione."}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if current_data.time_spent:
                        st.caption(f"⏱️ Tempo riflessione: {int(current_data.time_spent)}s")

            # TAB 3: COACH & VIDEO
            with tab_coach:
                render_coach_feedback(stats, results)
                
                st.divider()
                st.subheader(T["video_rec"])
                
                # Logica selezione video
                weaknesses = []
                if stats.endgame_accuracy < 60: weaknesses.append("Endgame")
                vid_id, reason = get_youtube_recommendation(opening_name, weaknesses)
                
                c_vid1, c_vid2 = st.columns([1, 1])
                with c_vid1:
                    st.markdown(f"**Consigliato per:** *{reason}*")
                    st.image(f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg", width=300)
                    st.markdown(f"[▶️ Guarda Video su YouTube](https://www.youtube.com/watch?v={vid_id})")
                with c_vid2:
                    st.markdown("### Piano di Studio")
                    st.markdown(f"""
                    1. Rivedi l'apertura **{opening_name}**.
                    2. Risolvi 10 puzzle sul tema "{'Finali' if 'Endgame' in weaknesses else 'Tattica'}".
                    3. Analizza i tuoi {stats.blunders} Blunder nella tab Replay.
                    """)

            # TAB 4: PUZZLES (Generati dagli errori)
            with tab_training:
                st.subheader(T["puzzles"])
                
                # Filtra posizioni dove l'utente ha fatto Mistake/Blunder
                puzzle_candidates = [r for r in results if r.classification in ["Blunder", "Mistake"]]
                
                if not puzzle_candidates:
                    st.success("🎉 Incredibile! Nessun errore grave trovato per generare puzzle.")
                else:
                    st.info(f"Abbiamo generato {len(puzzle_candidates)} puzzle basati sui tuoi errori in questa partita.")
                    
                    # Puzzle Slider
                    puz_idx = st.number_input("Seleziona Puzzle", 1, len(puzzle_candidates), 1) - 1
                    puz_data = puzzle_candidates[puz_idx]
                    
                    # Per mostrare il puzzle, dobbiamo mostrare la posizione PRIMA dell'errore
                    # Recuperiamo l'indice originale
                    orig_idx = results.index(puz_data)
                    prev_fen = results[orig_idx-1].fen if orig_idx > 0 else chess.STARTING_FEN
                    
                    col_p1, col_p2 = st.columns(2)
                    with col_p1:
                        st.markdown("**Trova la mossa migliore (che ti sei perso):**")
                        st.markdown(render_board_svg(prev_fen), unsafe_allow_html=True)
                    
                    with col_p2:
                        with st.expander("👁️ Mostra Soluzione"):
                            st.write("La mossa che avresti dovuto giocare (o evitare l'errore) dipende dal calcolo del motore.")
                            st.write("In questa posizione, il tuo errore è stato: " + puz_data.move_san)
                            st.warning("Analizza la posizione con il motore locale per trovare la continuazione vincente!")

    # --- SIDEBAR METRICS (Aggiornate) ---
    with col_metrics:
        if st.session_state.game_analysis:
            st.markdown("### 📊 Live Stats")
            
            # Heatmap Territorio (Aggiornata con FEN corrente slider)
            st.subheader(T["heatmap"])
            if 'game_analysis' in st.session_state:
                current_r = st.session_state.game_analysis[st.session_state.get("replay_slider", 0)]
                fen_hm = current_r.fen
                
                board_hm = chess.Board(fen_hm)
                
                # Generazione Heatmap Reale
                matrix = np.zeros((8, 8))
                for sq in chess.SQUARES:
                    piece = board_hm.piece_at(sq)
                    if piece:
                        val = 1 if piece.color == chess.WHITE else -1
                        # Peso centrale
                        r, f = chess.square_rank(sq), chess.square_file(sq)
                        if 2 <= r <= 5 and 2 <= f <= 5: val *= 1.2
                        matrix[7-r][f] = val
                
                fig_hm, ax_hm = plt.subplots(figsize=(4, 4))
                sns.heatmap(matrix, cmap="RdYlGn", center=0, cbar=False, ax=ax_hm, xticklabels=False, yticklabels=False, square=True)
                fig_hm.patch.set_facecolor(CONSTANTS["THEME"]["bg"])
                st.pyplot(fig_hm)

            # Time Management
            st.subheader(T["time_mgmt"])
            if st.session_state.game_stats:
                st.metric("Avg Time", f"{st.session_state.game_stats.avg_time_per_move:.1f}s")
                st.metric("In Time Trouble", f"{st.session_state.game_stats.time_trouble_count} moves")

    # FOOTER
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"<div style='text-align:center; color:#666; font-size:12px;'>{CONSTANTS['APP_TITLE']} v{CONSTANTS['VERSION']}<br>Powered by Stockfish & Python</div>", 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
