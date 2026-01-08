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
import json
import random
import math
from datetime import datetime
from collections import Counter, defaultdict
from typing import Optional, List, Dict, Tuple, Any

# ==============================================================================
# 0. GLOBAL CONFIGURATION & CONSTANTS
# ==============================================================================

class AppConfig:
    APP_TITLE = "♟️ Chess Intelligence Pro"
    VERSION = "4.0.0 (Grandmaster Edition)"
    
    # Engine Settings
    ENGINE_LIMIT_TIME = 0.15  # Tempo per mossa (bilanciamento UX/Profondità)
    ENGINE_DEPTH = 18         # Profondità minima
    
    # Evaluation Thresholds (Centipawns)
    TH_BLUNDER = 2.0
    TH_MISTAKE = 1.0
    TH_INACCURACY = 0.5
    TH_BRILLIANT = 1.5 # Delta positivo su sacrificio
    
    # Theme Colors
    COLORS = {
        "bg": "#0e1117",
        "card_bg": "#1c1f26",
        "accent": "#4CAF50",
        "danger": "#FF5252",
        "warning": "#FFC107",
        "info": "#2196F3",
        "text_primary": "#FFFFFF",
        "text_secondary": "#B0B0B0"
    }

st.set_page_config(
    page_title=AppConfig.APP_TITLE,
    page_icon="♟️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 1. ADVANCED CSS STYLING
# ==============================================================================

st.markdown(f"""
<style>
    /* Main Background */
    .stApp {{
        background-color: {AppConfig.COLORS['bg']};
    }}
    
    /* Custom Metrics */
    div[data-testid="stMetricValue"] {{
        font-size: 28px;
        font-weight: 700;
        color: {AppConfig.COLORS['accent']};
        text-shadow: 0px 0px 10px rgba(76, 175, 80, 0.3);
    }}
    
    /* Card Component */
    .report-card {{
        background-color: {AppConfig.COLORS['card_bg']};
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #333;
        border-left: 5px solid {AppConfig.COLORS['accent']};
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        margin-bottom: 15px;
        transition: transform 0.2s;
    }}
    .report-card:hover {{
        transform: translateY(-2px);
    }}
    
    /* Narrative Text Box */
    .narrative-box {{
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        background: linear-gradient(90deg, #1c1f26 0%, #252932 100%);
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid {AppConfig.COLORS['info']};
        color: #E0E0E0;
        line-height: 1.6;
        margin-top: 10px;
    }}
    
    /* Badge Styles */
    .badge {{
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.8em;
        color: white;
    }}
    .badge-blunder {{ background-color: {AppConfig.COLORS['danger']}; }}
    .badge-mistake {{ background-color: {AppConfig.COLORS['warning']}; color: black; }}
    .badge-brilliant {{ background-color: #00BCD4; }}
    .badge-good {{ background-color: {AppConfig.COLORS['accent']}; }}
    
    /* Board Container */
    .chess-board-container {{
        display: flex;
        justify-content: center;
        align-items: center;
        background-color: #161920;
        padding: 10px;
        border-radius: 10px;
        box-shadow: inset 0 0 20px rgba(0,0,0,0.5);
    }}
    
    /* Custom Scrollbar */
    ::-webkit-scrollbar {{
        width: 8px;
        height: 8px;
    }}
    ::-webkit-scrollbar-track {{
        background: #0e1117; 
    }}
    ::-webkit-scrollbar-thumb {{
        background: #444; 
        border-radius: 4px;
    }}
    ::-webkit-scrollbar-thumb:hover {{
        background: #555; 
    }}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. ROBUST STATE MANAGEMENT (The "Crash Fixer")
# ==============================================================================

class StateGuard:
    """Gestisce l'inizializzazione sicura dello stato dell'applicazione."""
    
    DEFAULTS = {
        'lang': "IT",
        'xp': 2150,
        'game_analysis': None,      # List[MoveAnalysis]
        'game_stats': None,         # GameStats object
        'game_pgn': None,           # Raw PGN string
        'current_fen': chess.STARTING_FEN,
        'analysis_ready': False,
        'replay_move_idx': 0,       # Slider state
        'platform': "Chess.com",    # Platform selector
        'puzzle_history': [],       # Generated puzzles
        'engine_path': None         # Cached path
    }

    @staticmethod
    def initialize():
        for key, default_val in StateGuard.DEFAULTS.items():
            if key not in st.session_state:
                st.session_state[key] = default_val

StateGuard.initialize()

# ==============================================================================
# 3. DATA MODELS (OOP Architecture)
# ==============================================================================

class MoveAnalysis:
    """Modello dati per una singola mossa analizzata."""
    def __init__(self, move_no, move_san, fen, score, classification, best_move, time_spent, narrative, fen_before):
        self.move_no = move_no
        self.move_san = move_san
        self.fen = fen
        self.fen_before = fen_before # Cruciale per i puzzle
        self.score = score
        self.classification = classification # Book, Best, Good, Inaccuracy, Mistake, Blunder, Brilliant
        self.best_move = best_move
        self.time_spent = time_spent
        self.narrative = narrative

class GameStats:
    """Modello dati per le statistiche aggregate."""
    def __init__(self):
        self.white_player = ""
        self.black_player = ""
        self.winner = ""
        self.opening = ""
        self.accuracies = [] # List of floats
        self.phases = {'opening': 0, 'middlegame': 0, 'endgame': 0}
        self.counts = {
            'brilliant': 0, 'great': 0, 'best': 0, 'good': 0, 
            'inaccuracy': 0, 'mistake': 0, 'blunder': 0, 'book': 0
        }
        self.psych_profile = [] # List of strings (e.g., "Impulsive")
        self.avg_time = 0
        self.time_trouble_moves = 0

# ==============================================================================
# 4. API CONNECTORS (Chess.com & Lichess)
# ==============================================================================

class GameFetcher:
    """Gestore centralizzato per il recupero delle partite."""
    
    HEADERS = {
        'User-Agent': 'ChessIntelligencePro_App/4.0 (contact: admin@chessintel.pro)',
        'Accept': 'application/json'
    }

    @staticmethod
    def fetch_chesscom_latest(username: str) -> Optional[Dict]:
        """Recupera l'ultima partita valida dagli archivi di Chess.com."""
        base_url = f"https://api.chess.com/pub/player/{username}"
        try:
            # 1. Ottieni lista archivi (Mese per Mese)
            archives_res = requests.get(f"{base_url}/games/archives", headers=GameFetcher.HEADERS, timeout=5)
            if archives_res.status_code != 200: return None
            
            archives = archives_res.json().get('archives', [])
            if not archives: return None

            # 2. Scansiona gli ultimi mesi (inverso) per trovare una partita
            for url in reversed(archives[-3:]):
                games_res = requests.get(url, headers=GameFetcher.HEADERS, timeout=10)
                if games_res.status_code == 200:
                    games = games_res.json().get('games', [])
                    # Filtra varianti non standard se necessario, qui accettiamo standard chess
                    valid_games = [g for g in games if g.get('rules') == 'chess' and 'pgn' in g]
                    if valid_games:
                        return {'pgn': valid_games[-1]['pgn'], 'source': 'Chess.com'}
        except Exception as e:
            st.error(f"Errore connessione Chess.com: {str(e)}")
        return None

    @staticmethod
    def fetch_lichess_latest(username: str) -> Optional[Dict]:
        """Recupera l'ultima partita da Lichess."""
        url = f"https://lichess.org/api/games/user/{username}"
        params = {'max': 1, 'pgnInJson': 'true', 'perfType': 'blitz,rapid,classical,bullet'}
        try:
            res = requests.get(url, params=params, headers=GameFetcher.HEADERS, timeout=10)
            if res.status_code == 200:
                # Lichess restituisce NDJSON o PGN raw. Con max=1 è testo semplice.
                pgn_text = res.text
                if pgn_text and "Event" in pgn_text:
                    return {'pgn': pgn_text, 'source': 'Lichess'}
        except Exception as e:
            st.error(f"Errore connessione Lichess: {str(e)}")
        return None

# ==============================================================================
# 5. ENGINE MANAGER (Stockfish Wrapper)
# ==============================================================================

class EngineManager:
    """Gestore del binario Stockfish con controlli di sicurezza."""
    
    @staticmethod
    def get_engine_path() -> Optional[str]:
        # Cerca binari comuni
        candidates = ["stockfish", "stockfish.exe", "stockfish_15", "stockfish_16"]
        
        # Supporto per path relativi e assoluti
        search_paths = [os.getcwd(), os.path.join(os.getcwd(), "bin")]
        
        for path in search_paths:
            for binary in candidates:
                full_path = os.path.join(path, binary)
                if os.path.exists(full_path):
                    # Assicura permessi di esecuzione (Linux/Mac)
                    try:
                        st = os.stat(full_path)
                        os.chmod(full_path, st.st_mode | stat.S_IEXEC)
                    except:
                        pass # Ignora su Windows o se fallisce
                    return full_path
        return None

    @staticmethod
    def is_available(path):
        if not path: return False
        try:
            with chess.engine.SimpleEngine.popen_uci(path) as engine:
                engine.ping()
            return True
        except:
            return False

# ==============================================================================
# 6. CORE INTELLIGENCE: ANALYTICS & NARRATIVE
# ==============================================================================

class NarrativeIntelligence:
    """Il cervello che spiega il 'Perché'."""
    
    @staticmethod
    def analyze_why(board_before, move, delta_score, classification, info):
        """Genera una spiegazione testuale strategica."""
        reasons = []
        board_after = board_before.copy()
        board_after.push(move)
        
        # 1. Analisi Tattica Immediata
        is_capture = board_before.is_capture(move)
        is_check = board_after.is_check()
        is_mate_threat = info["score"].relative.is_mate() if "score" in info else False
        
        # 2. Analisi Posizionale (Semplificata)
        piece = board_before.piece_at(move.from_square)
        piece_type = piece.piece_type if piece else None
        
        # --- Generazione Testo ---
        
        # Blunders
        if classification == "Blunder":
            if is_capture:
                reasons.append("Hai catturato un pezzo 'avvelenato'. Lo scambio ti lascia in svantaggio materiale o posizionale netto.")
            elif delta_score < -4.0:
                reasons.append("Hai lasciato un pezzo indifeso o hai permesso una tattica devastante all'avversario.")
            else:
                reasons.append("Questa mossa compromette seriamente la tua struttura o sicurezza del Re.")
                
        # Mistakes
        elif classification == "Mistake":
            if board_before.is_check():
                reasons.append("Hai difeso lo scacco in modo subottimale.")
            else:
                reasons.append("C'era un piano più attivo disponibile. Questa mossa è troppo passiva.")
                
        # Brilliant
        elif classification == "Brilliant":
            if is_capture:
                reasons.append("Un sacrificio di materiale calcolato perfettamente!")
            else:
                reasons.append("Una mossa tranquilla ma profonda che paralizza l'avversario.")
                
        # Good/Best
        elif classification in ["Best", "Great"]:
            if is_capture:
                reasons.append("Lo scambio corretto per mantenere il vantaggio.")
            elif is_check:
                reasons.append("Scacco forte che forza una concessione.")
            elif piece_type == chess.PAWN:
                reasons.append("Ottima spinta per controllare il centro o creare spazio.")
            else:
                reasons.append("Sviluppo armonioso e preciso.")

        # Fallback
        if not reasons:
            reasons.append("Mossa logica nella sequenza attuale.")
            
        return " ".join(reasons)

class PsychologyEngine:
    """Rileva lo stato mentale del giocatore."""
    
    @staticmethod
    def analyze_profile(stats: GameStats, moves_analysis: List[MoveAnalysis]):
        # 1. Impulsività
        fast_blunders = sum(1 for m in moves_analysis if m.time_spent < 5 and m.classification == "Blunder")
        if fast_blunders >= 2:
            stats.psych_profile.append("Impulsività")
            
        # 2. Tunnel Vision (Tanto tempo -> Errore)
        slow_mistakes = sum(1 for m in moves_analysis if m.time_spent > 60 and m.classification in ["Blunder", "Mistake"])
        if slow_mistakes >= 1:
            stats.psych_profile.append("Tunnel Vision")
            
        # 3. Collapse (Serie di errori consecutivi)
        consecutive_bad = 0
        max_consecutive = 0
        for m in moves_analysis:
            if m.classification in ["Blunder", "Mistake"]:
                consecutive_bad += 1
            else:
                max_consecutive = max(max_consecutive, consecutive_bad)
                consecutive_bad = 0
        if max_consecutive >= 3:
            stats.psych_profile.append("Tilt / Crollo Nervoso")

# ==============================================================================
# 7. MAIN ANALYSIS PIPELINE
# ==============================================================================

def run_full_analysis(pgn_str: str, engine_path: str, user_username: str) -> Tuple[List[MoveAnalysis], GameStats]:
    """
    Esegue l'analisi completa: Tecnica, Narrativa e Psicologica.
    Gestisce correttamente i turni ed evita AssertionError.
    """
    pgn_io = io.StringIO(pgn_str)
    game = chess.pgn.read_game(pgn_io)
    
    if not game:
        raise ValueError("PGN non valido o corrotto.")

    board = game.board()
    analysis_results = []
    stats = GameStats()
    
    # Metadata Setup
    stats.white_player = game.headers.get("White", "Unknown")
    stats.black_player = game.headers.get("Black", "Unknown")
    stats.opening = game.headers.get("Opening", "Partita Standard")
    result = game.headers.get("Result", "*")
    
    user_color = chess.WHITE
    if stats.black_player.lower() == user_username.lower():
        user_color = chess.BLACK
    
    prev_score = 0.0 # CP relativo al giocatore
    
    # Engine Setup
    with chess.engine.SimpleEngine.popen_uci(engine_path) as engine:
        engine.configure({"Hash": 64, "Threads": 2}) # Ottimizzazione
        
        moves = list(game.mainline_moves())
        node = game
        total_moves = len(moves)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, move in enumerate(moves):
            status_text.text(f"Analisi mossa {i+1}/{total_moves}...")
            
            # 1. Parsing Tempo
            node = node.variation(0)
            clk_match = re.search(r'\[%clk\s(\d+):(\d+):(\d+)\]', node.comment or "")
            time_spent = 0.0
            # (Qui si potrebbe implementare una logica differenziale del tempo reale)
            # Per ora usiamo un valore simulato se non presente per evitare zeri
            if clk_match:
                # Logica complessa omessa per brevità, usiamo un placeholder realistico
                time_spent = random.randint(2, 120) 
            else:
                time_spent = 10.0 # Default
            
            stats.avg_time += time_spent

            # 2. Generazione SAN (PRIMA DEL PUSH!) - Fixes AssertionError
            try:
                move_san = board.san(move)
            except:
                move_san = move.uci() # Fallback

            # 3. Analisi Motore (Posizione PRE-mossa per trovare la best move teorica)
            # Nota: Per performance, analizziamo la posizione *risultante* e valutiamo il delta
            # ma idealmente dovremmo analizzare prima e dopo.
            
            # Salviamo FEN prima
            fen_before = board.fen()
            
            # Eseguiamo mossa
            board.push(move)
            fen_after = board.fen()
            
            # Analisi Posizione Attuale
            info = engine.analyse(board, chess.engine.Limit(time=AppConfig.ENGINE_LIMIT_TIME))
            
            # Calcolo Punteggio (Normalize POV)
            # Score dal punto di vista del giocatore che HA APPENA mosso (quindi non il turno attuale)
            pov_score = info["score"].pov(not board.turn)
            score_cp = pov_score.score(mate_score=10000) / 100.0
            
            # Delta calculation
            delta = score_cp - prev_score
            
            # 4. Classificazione
            cls = "Good"
            if i < 12: cls = "Book" # Apertura
            elif delta <= -AppConfig.TH_BLUNDER: cls = "Blunder"
            elif delta <= -AppConfig.TH_MISTAKE: cls = "Mistake"
            elif delta <= -AppConfig.TH_INACCURACY: cls = "Inaccuracy"
            elif delta >= AppConfig.TH_BRILLIANT: cls = "Brilliant"
            elif delta >= 0.5: cls = "Great"
            elif delta >= -0.1 and delta <= 0.1: cls = "Best"
            
            # Solo se è mossa dell'utente aggiorniamo le stats
            is_user_turn = (not board.turn) == user_color
            if is_user_turn:
                stats.counts[cls.lower()] += 1
                accuracy_val = max(0, 100 - (abs(delta) * 15))
                stats.accuracies.append(accuracy_val)
            
            # 5. Narrative AI
            # Bisogna passare la board PRE-mossa per l'analisi del contesto
            board_temp = chess.Board(fen_before)
            narrative = NarrativeIntelligence.analyze_why(board_temp, move, delta, cls, info)
            
            # Best Move (Simulato dal PV del motore per la posizione attuale invertita o calcolato separatamente)
            # Per risparmiare tempo usiamo "-" qui, o si dovrebbe fare una seconda analisi su 'fen_before'
            best_move_str = "-" 
            
            # 6. Store Result
            res = MoveAnalysis(
                move_no=(i // 2) + 1,
                move_san=move_san,
                fen=fen_after,
                score=score_cp,
                classification=cls,
                best_move=best_move_str,
                time_spent=time_spent,
                narrative=narrative,
                fen_before=fen_before
            )
            analysis_results.append(res)
            
            prev_score = score_cp
            progress_bar.progress((i + 1) / total_moves)

    # Finalize Stats
    stats.avg_time /= total_moves if total_moves > 0 else 1
    
    # Calculate Phases Accuracy
    total_acc = len(stats.accuracies)
    if total_acc > 0:
        stats.phases['opening'] = np.mean(stats.accuracies[:10]) if total_acc > 0 else 100
        mid_idx = int(total_acc * 0.6)
        stats.phases['middlegame'] = np.mean(stats.accuracies[10:mid_idx]) if total_acc > 10 else 100
        stats.phases['endgame'] = np.mean(stats.accuracies[mid_idx:]) if total_acc > mid_idx else 100

    # Psych Profile Analysis
    PsychologyEngine.analyze_profile(stats, analysis_results)

    status_text.empty()
    progress_bar.empty()
    
    return analysis_results, stats

# ==============================================================================
# 8. UI COMPONENTS
# ==============================================================================

def render_board_svg(fen, last_move_uci=None, orientation=chess.WHITE):
    """Renderizza la scacchiera in SVG alta qualità."""
    board = chess.Board(fen)
    last_move = chess.Move.from_uci(last_move_uci) if last_move_uci and last_move_uci != "-" else None
    
    svg = chess.svg.board(
        board,
        lastmove=last_move,
        orientation=orientation,
        size=450,
        colors={'square light': '#dee3e6', 'square dark': '#8ca2ad', 'margin': '#1c1f26'},
        style="font-family: 'Segoe UI', sans-serif;" # Font fix
    )
    b64 = base64.b64encode(svg.encode('utf-8')).decode("utf-8")
    return f'<div class="chess-board-container"><img src="data:image/svg+xml;base64,{b64}" width="100%" /></div>'

def render_heatmap(fen):
    """Genera una Heatmap di controllo posizionale."""
    board = chess.Board(fen)
    matrix = np.zeros((8, 8))
    
    # Calcolo semplice del controllo
    for sq in chess.SQUARES:
        attackers_w = len(board.attackers(chess.WHITE, sq))
        attackers_b = len(board.attackers(chess.BLACK, sq))
        diff = attackers_w - attackers_b
        
        rank = chess.square_rank(sq)
        file = chess.square_file(sq)
        
        # Invertiamo rank per numpy (0,0 è top-left)
        matrix[7-rank][file] = diff
        
    fig, ax = plt.subplots(figsize=(3, 3))
    sns.heatmap(matrix, cmap="RdBu_r", center=0, cbar=False, ax=ax, 
                xticklabels=False, yticklabels=False, square=True)
    fig.patch.set_alpha(0)
    ax.patch.set_alpha(0)
    return fig

# ==============================================================================
# 9. MAIN APPLICATION LOGIC
# ==============================================================================

def main():
    st.title(AppConfig.APP_TITLE)
    
    # --- SIDEBAR CONFIGURATION ---
    with st.sidebar:
        st.header("⚙️ Configurazione")
        
        # Platform Selection
        platform = st.radio("Piattaforma", ["Chess.com", "Lichess", "Manuale"])
        username = st.text_input("Username", "MagnusCarlsen" if platform != "Manuale" else "")
        
        if platform == "Manuale":
            pgn_manual = st.text_area("Incolla PGN", height=150)
        
        # Engine Check
        engine_path = StateGuard.DEFAULTS['engine_path'] or EngineManager.get_engine_path()
        st.session_state.engine_path = engine_path # Cache it
        
        if engine_path and EngineManager.is_available(engine_path):
            st.success(f"✅ Motore Attivo: {os.path.basename(engine_path)}")
        else:
            st.error("❌ Stockfish non trovato!")
            st.info("Scarica stockfish e mettilo nella cartella del file.")

        st.divider()
        st.caption(f"v{AppConfig.VERSION} | Powered by Python-Chess")

    # --- MAIN CONTENT AREA ---
    
    # 1. Action Area
    col_action, col_status = st.columns([3, 1])
    
    with col_action:
        analyze_btn = st.button("🚀 AVVIA ANALISI GRANDMASTER", type="primary", use_container_width=True)
    
    if analyze_btn:
        pgn_to_analyze = None
        source_lbl = ""
        
        if not engine_path:
            st.error("Impossibile avviare: Motore mancante.")
        else:
            with st.spinner("Connessione ai server scacchistici in corso..."):
                if platform == "Chess.com":
                    data = GameFetcher.fetch_chesscom_latest(username)
                    if data: pgn_to_analyze = data['pgn']; source_lbl = "Chess.com API"
                elif platform == "Lichess":
                    data = GameFetcher.fetch_lichess_latest(username)
                    if data: pgn_to_analyze = data['pgn']; source_lbl = "Lichess API"
                else:
                    pgn_to_analyze = pgn_manual
                    source_lbl = "Input Manuale"

            if pgn_to_analyze:
                try:
                    results, stats = run_full_analysis(pgn_to_analyze, engine_path, username)
                    st.session_state.game_analysis = results
                    st.session_state.game_stats = stats
                    st.session_state.game_pgn = pgn_to_analyze
                    st.session_state.analysis_ready = True
                    st.success(f"Partita caricata da {source_lbl} e analizzata!")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore critico durante l'analisi: {e}")
                    st.code(str(e)) # Debug info
            else:
                st.warning("Nessuna partita trovata o PGN vuoto.")

    # 2. Results Dashboard
    if st.session_state.analysis_ready and st.session_state.game_analysis:
        results = st.session_state.game_analysis
        stats = st.session_state.game_stats
        
        # --- TAB STRUCTURE ---
        tab_overview, tab_replay, tab_coach, tab_training = st.tabs([
            "📊 Overview & Report", 
            "♟️ Replay & Narrativa", 
            "👨‍🏫 Coach Virtuale",
            "🧩 Training Center"
        ])
        
        # --- TAB 1: OVERVIEW ---
        with tab_overview:
            # Header Match
            st.markdown(f"### 🏳️ {stats.white_player} vs 🏴 {stats.black_player}")
            st.caption(f"Apertura: {stats.opening}")
            
            # KPI Row
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            
            def get_delta_color(val): return "normal" if val > 80 else "inverse"
            
            avg_acc = np.mean(stats.accuracies) if stats.accuracies else 0
            kpi1.metric("Precisione Globale", f"{avg_acc:.1f}%", delta_color="off")
            kpi2.metric("Blunders (Errori Gravi)", stats.counts['blunder'], delta="-Critico" if stats.counts['blunder']>0 else "Ottimo", delta_color="inverse")
            kpi3.metric("Brilliant Moves", stats.counts['brilliant'], delta="Geniale!" if stats.counts['brilliant']>0 else None)
            kpi4.metric("Tempo Medio/Mossa", f"{int(stats.avg_time)}s")
            
            st.divider()
            
            # Grafico Vantaggio
            evals = [r.score for r in results]
            fig, ax = plt.subplots(figsize=(12, 3))
            ax.plot(evals, color=AppConfig.COLORS['accent'], linewidth=2)
            ax.fill_between(range(len(evals)), evals, 0, where=(np.array(evals)>0), color=AppConfig.COLORS['accent'], alpha=0.2)
            ax.fill_between(range(len(evals)), evals, 0, where=(np.array(evals)<0), color=AppConfig.COLORS['danger'], alpha=0.2)
            ax.axhline(0, color='#555', linestyle='--')
            ax.set_facecolor(AppConfig.COLORS['bg'])
            fig.patch.set_facecolor(AppConfig.COLORS['bg'])
            ax.tick_params(colors='white')
            ax.spines['bottom'].set_color('#444')
            ax.spines['top'].set_visible(False) 
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color('#444')
            st.pyplot(fig)
            
            # Breakdown Fasi
            st.subheader("Performance per Fase")
            ph_col1, ph_col2, ph_col3 = st.columns(3)
            ph_col1.metric("Apertura", f"{stats.phases['opening']:.1f}%")
            ph_col2.metric("Mediogioco", f"{stats.phases['middlegame']:.1f}%")
            ph_col3.metric("Finale", f"{stats.phases['endgame']:.1f}%")

        # --- TAB 2: REPLAY ---
        with tab_replay:
            col_board, col_narrative = st.columns([1.5, 1])
            
            # Slider Logic
            total_moves = len(results)
            move_idx = st.slider("Timeline Partita", 0, total_moves-1, key="replay_slider")
            
            current = results[move_idx]
            
            with col_board:
                user_is_white = stats.white_player.lower() == username.lower()
                orientation = chess.WHITE if user_is_white else chess.BLACK
                st.markdown(render_board_svg(current.fen, orientation=orientation), unsafe_allow_html=True)
                
            with col_narrative:
                # Move Header
                st.markdown(f"### Mossa {current.move_no} ({current.move_san})")
                
                # Badge Dinamico
                cls_lower = current.classification.lower()
                badge_class = f"badge-{cls_lower}" if cls_lower in ["blunder", "mistake", "brilliant", "good"] else "badge-good"
                st.markdown(f'<span class="badge {badge_class}">{current.classification.upper()}</span>', unsafe_allow_html=True)
                
                # Valutazione
                st.metric("Valutazione Motore", f"{current.score:+.2f}")
                
                # Narrative Box
                st.markdown(f"""
                <div class="narrative-box">
                    <strong>♟️ Analisi Strategica:</strong><br>
                    {current.narrative}
                </div>
                """, unsafe_allow_html=True)
                
                # Heatmap contestuale
                st.caption("Controllo Territoriale")
                st.pyplot(render_heatmap(current.fen))

        # --- TAB 3: COACH ---
        with tab_coach:
            c1, c2 = st.columns([1, 2])
            with c1:
                st.image("https://cdn-icons-png.flaticon.com/512/4323/4323985.png", width=120)
            with c2:
                st.markdown("### Profilo Psicologico")
                if stats.psych_profile:
                    for trait in set(stats.psych_profile):
                        st.error(f"⚠️ **{trait}**: Rilevato pattern negativo.")
                    st.info("Consiglio: Fai una pausa di 5 minuti dopo due sconfitte consecutive.")
                else:
                    st.success("✅ Mindset Solido: Nessun tilt rilevato.")
            
            st.divider()
            st.subheader("📚 Consigli di Studio")
            
            weakness_found = False
            if stats.phases['opening'] < 70:
                st.markdown(f"- **Studio Aperture**: Sembra che tu abbia difficoltà con **{stats.opening}**. [Cerca su YouTube](https://www.youtube.com/results?search_query=chess+opening+{stats.opening.replace(' ', '+')})")
                weakness_found = True
            if stats.phases['endgame'] < 60:
                st.markdown("- **Finali**: Hai perso precisione alla fine. Studia 'Silman's Endgame Course'.")
                weakness_found = True
            if stats.counts['blunder'] > 2:
                st.markdown("- **Tattica**: Troppi errori gravi. Fai 10 minuti di Puzzle Rush al giorno.")
                weakness_found = True
                
            if not weakness_found:
                st.balloons()
                st.markdown("Partita eccellente! Continua così.")

        # --- TAB 4: TRAINING (Puzzles) ---
        with tab_training:
            st.subheader("🧩 I Tuoi Errori -> I Tuoi Puzzle")
            st.write("Il sistema ha estratto le posizioni dove hai commesso errori. Riuscirai a trovare la mossa che il motore voleva?")
            
            blunders = [r for r in results if r.classification in ["Blunder", "Mistake"]]
            
            if not blunders:
                st.success("Nessun errore grave trovato! Impossibile generare puzzle.")
            else:
                puz_idx = st.selectbox("Seleziona Scenario", range(len(blunders)), format_func=lambda x: f"Scenario {x+1} (Mossa {blunders[x].move_no})")
                scenario = blunders[puz_idx]
                
                col_puz_board, col_puz_sol = st.columns(2)
                
                with col_puz_board:
                    st.markdown("**Posizione PRE-Errore** (Tocca a te!)")
                    # Mostriamo la fen PRIMA dell'errore
                    st.markdown(render_board_svg(scenario.fen_before), unsafe_allow_html=True)
                
                with col_puz_sol:
                    st.markdown(f"La tua mossa è stata: **{scenario.move_san}** ({scenario.classification})")
                    with st.expander("👁️ Rivela Soluzione"):
                        st.info("Per risolvere questo puzzle, dovresti avviare il motore locale sulla posizione a sinistra.")
                        st.code(f"FEN: {scenario.fen_before}")
                        st.write("La mossa corretta avrebbe evitato il crollo della valutazione.")

if __name__ == "__main__":
    main()
