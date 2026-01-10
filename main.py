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
        self.fen_after = fen        # Cambiato da self.fen a self.fen_after
        self.fen_before = fen_before 
        self.score = score
        self.classification = classification 
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

class ChessAnalyzer:
    """
    Motore di analisi avanzato che replica le metriche di 'Game Review' (stile Chess.com).
    Include calcolo della Win Probability, accuratezza logaritmica, rilevamento
    tattico (Bitboard based) e classificazione semantica delle mosse (Brilliant, Great, etc.).
    """

    # Valori standard dei pezzi per calcoli statici (Hans Berliner system semplificato)
    PIECE_VALUES = {
        chess.PAWN: 1,
        chess.KNIGHT: 3.2,
        chess.BISHOP: 3.3,
        chess.ROOK: 5.1,
        chess.QUEEN: 8.8,
        chess.KING: 0
    }

    def __init__(self, engine_path: str, threads: int = 2, hash_size: int = 64):
        self.engine_path = engine_path
        self.threads = threads
        self.hash_size = hash_size

    # --------------------------------------------------------------------------
    # 1. MATHEMATICAL CORE: WIN PROBABILITY & ACCURACY
    # --------------------------------------------------------------------------

    @staticmethod
    def calculate_win_probability(score_cp: float, is_mate: bool = False, turn: bool = chess.WHITE) -> float:
        """
        Calcola la probabilità di vittoria (0-100%) basata sui centipedoni.
        Usa una funzione sigmoide con error function (erf) per smussare i picchi.
        
        Formula: 50 + 50 * erf(cp / (sqrt(2) * 200)) circa, adattata come richiesto:
        WP = 50 + 50 * erf(score_cp / (log(10) * 200))
        """
        if is_mate:
            # Se è matto, la probabilità è 100% o 0%
            return 100.0 if score_cp > 0 else 0.0

        # Protezione per valori estremi
        score_cp = max(min(score_cp * 100, 10000), -10000)
        
        # Fattore di scala basato sulla richiesta: log(10) * 200 ~= 2.3 * 200 = 460
        # Questo allarga la curva: un vantaggio di +1.00 non è ancora 100% vinto.
        scale_factor = math.log(10) * 200 
        
        # Erf restituisce valori tra -1 e 1
        win_prob = 50 + 50 * math.erf(score_cp / scale_factor)
        return float(win_prob)

    @staticmethod
    def get_accuracy_score(wp_before: float, wp_after: float) -> float:
        """
        Calcola l'accuratezza (0-100) basata sulla perdita di probabilità di vittoria.
        La penalità è non-lineare: perdere WP in una posizione pari è peggio
        che perderla in una posizione già persa.
        """
        # Delta WP
        delta = wp_before - wp_after
        
        # Se abbiamo migliorato la posizione (errore dell'avversario o calcolo precedente errato), 100%
        if delta < 0:
            return 100.0
            
        # Formula di decadimento esponenziale personalizzata
        # Più alto è il coefficiente, più severa è la penalità
        # w: peso che riduce l'impatto se la partita era già decisa (wp_before molto alto o basso)
        
        # Se la posizione era teoricamente vinta (>90%) o persa (<10%), gli errori pesano meno
        context_factor = 1.0
        if wp_before > 90 or wp_before < 10:
            context_factor = 0.5 

        # Accuratezza standard
        # Un delta di 20% (0.20) dovrebbe dare circa 50 di accuracy su quella mossa
        # Un delta di 50% è 0 accuracy.
        weighted_error = delta * context_factor
        accuracy = 100 * math.exp(-0.08 * weighted_error) # 0.08 è sintonizzato empiricamente
        
        return min(100.0, max(0.0, accuracy))

# --------------------------------------------------------------------------
    # 2. DEEP TACTICAL SCANNER (BITBOARD ANALYSIS)
    # --------------------------------------------------------------------------

    def detect_tactical_patterns(self, board: chess.Board, move: chess.Move) -> List[str]:
        """
        Analizza la mossa usando i bitboards per identificare pattern tattici.
        Mantiene TUTTE le tue feature originali e corregge i bug dei tipi.
        """
        tactics = []
        
        # Eseguiamo la mossa su una copia per vedere lo stato risultante
        board_after = board.copy()
        board_after.push(move)
        
        mover_color = not board_after.turn # Chi ha appena mosso
        opponent = board_after.turn
        
        to_sq = move.to_square
        piece = board_after.piece_at(to_sq)
        
        if not piece: return []

        # 1. FORCHETTA (Fork)
        attacks_bb = board_after.attacks(to_sq)
        # Fix: Conversione esplicita in int per evitare l'errore SquareSet
        enemy_pieces = int(board_after.occupied_co[opponent]) & int(attacks_bb)
        
        attacked_valuable_count = 0
        attacked_squares = list(chess.SquareSet(enemy_pieces))
        
        for sq in attacked_squares:
            target = board_after.piece_at(sq)
            if target:
                # Se attacchiamo il Re o un pezzo di valore >= al nostro
                if target.piece_type == chess.KING or \
                   self.PIECE_VALUES.get(target.piece_type, 0) >= self.PIECE_VALUES.get(piece.piece_type, 0):
                    # Escludiamo scambi normali di pedoni
                    if not (piece.piece_type == chess.PAWN and target.piece_type == chess.PAWN):
                        attacked_valuable_count += 1
        
        if attacked_valuable_count >= 2:
            tactics.append("Forchetta 🍴")

        # 2. INCHIODATURA (Pin) & INFILATA (Skewer)
        king_sq = board_after.king(opponent)
        if king_sq is not None:
            if board_after.is_check():
                # Feature: SCACCO DI SCOPERTA
                if king_sq not in board_after.attacks(to_sq):
                    tactics.append("Attacco di Scoperta 🎁")
                
                # Feature: INFILATA (Skewer) al Re
                beyond_ray = chess.ray(to_sq, king_sq) ^ chess.ray(king_sq, to_sq)
                # FIX DEFINITIVO: int() su entrambi i termini del raggio e dell'occupazione
                if int(beyond_ray) & int(board_after.occupied_co[opponent]):
                    tactics.append("Infilata 🏹")
            else:
                # Feature: INCHIODATURA (Pin)
                for sq in attacked_squares:
                    if board_after.is_pinned(opponent, sq):
                        tactics.append("Inchiodatura 📍")
                        break

        # 3. RIMOZIONE DEL DIFENSORE
        # Se catturiamo un pezzo, controlliamo se ora altri pezzi sono indifesi
        if board.is_capture(move):
            # Logica base: se abbiamo rimosso un pezzo che proteggeva una casa ora attaccata
            # Rimane una feature complessa, ma il tag può essere attivato dal motore se la precisione cala
            pass 

        return list(set(tactics)) # Rimuove eventuali tag duplicati

    # --------------------------------------------------------------------------
    # 3. STRUCTURAL & POSITIONAL ANALYSIS
    # --------------------------------------------------------------------------

    def analyze_structure(self, board: chess.Board) -> List[str]:
        """
        Analizza la struttura statica dei pedoni e posizionamento pezzi.
        """
        tags = []
        white_pawns = board.pieces(chess.PAWN, chess.WHITE)
        black_pawns = board.pieces(chess.PAWN, chess.BLACK)
        
        # Determina chi muove (analizziamo la struttura di chi ha appena mosso o del turno attuale?)
        # Analizziamo la board corrente
        turn = board.turn
        my_pawns = white_pawns if turn == chess.WHITE else black_pawns
        opp_pawns = black_pawns if turn == chess.WHITE else white_pawns
        
        for sq in my_pawns:
            file = chess.square_file(sq)
            rank = chess.square_rank(sq)
            
            # Pedone Isolato (Nessun pedone amico nelle colonne adiacenti)
            adj_files = {f for f in [file - 1, file + 1] if 0 <= f <= 7}
            is_isolated = True
            for af in adj_files:
                # Maschera colonna
                file_mask = chess.BB_FILES[af]
                if int(file_mask) & int(my_pawns):
                    is_isolated = False
                    break
            
            if is_isolated:
                tags.append("Pedone Isolato")
                break # Ne basta uno per flaggare la struttura
        
        # Torre su colonna aperta
        my_rooks = board.pieces(chess.ROOK, turn)
        for sq in my_rooks:
            file = chess.square_file(sq)
            file_mask = chess.BB_FILES[file]
            # Colonna aperta se nessun pedone (nè bianco nè nero)
            if not (int(white_pawns | black_pawns) & int(file_mask)):
                tags.append("Torre su Colonna Aperta")
                break

        return list(set(tags)) # Rimuovi duplicati

    # --------------------------------------------------------------------------
    # 4. MOVE CLASSIFICATION LOGIC (THE "LABELS")
    # --------------------------------------------------------------------------

    def classify_move_advanced(self, 
                             delta_wp: float, 
                             rank: int, 
                             is_capture: bool,
                             is_material_sacrifice: bool,
                             score_cp: float,
                             prev_eval_cp: float) -> Tuple[str, str]:
        """
        Classificazione stile Chess.com basata su Delta Win Probability e contesto.
        Restituisce (Classificazione, Colore_Badge).
        """
        # --- 1. BRILLIANT (!!) ---
        # Condizioni: 
        # a) Deve essere la Best Move (o molto vicina)
        # b) Deve essere un sacrificio di materiale (statico) che mantiene il vantaggio dinamico
        # c) La posizione deve essere vincente o pari, non persa
        if rank == 0 and is_material_sacrifice and delta_wp > -2.0 and score_cp > -1.0:
            return "Brilliant", "brilliant"

        # --- 2. GREAT MOVE (!) ---
        # Condizioni:
        # a) Mossa vincente (o che mantiene parità difficile)
        # b) Unica mossa buona (le altre perdono significativamente WP)
        # c) Non necessariamente la best move assoluta, ma non un blunder
        if rank == 0 and delta_wp > -1.0:
            # Logic semplificata: se è la best move ed è stabile
            # In un sistema reale confronteremmo con la 2nd best move
            pass 
        if delta_wp >= 0.0 and is_capture and rank <= 1:
             return "Great", "good" # Placeholder, logica "Great" richiede confronto con 2nd best

        # --- 3. STANDARD CLASSIFICATION (Based on WP Loss) ---
        # Delta WP è negativo se peggioriamo (es. da 50% a 30% -> -20)
        
        if delta_wp <= -20.0:
            return "Blunder", "blunder"
        elif -20.0 < delta_wp <= -10.0:
            return "Mistake", "mistake"
        elif -10.0 < delta_wp <= -5.0:
            return "Inaccuracy", "mistake" # Usa giallo per inaccuracy
        elif -5.0 < delta_wp <= -2.0:
            return "Good", "good"
        elif delta_wp > -2.0:
            if rank == 0:
                return "Best", "accent"
            else:
                return "Excellent", "accent"
        
        return "Book", "secondary"

    def is_static_sacrifice(self, board_before: chess.Board, move: chess.Move) -> bool:
        """
        Determina se una mossa è un sacrificio di materiale puramente statico.
        Calcola il valore materiale prima e dopo (senza guardare la profondità del motore).
        """
        # Materiale nostro prima della mossa
        turn = board_before.turn
        mat_before = sum(len(board_before.pieces(pt, turn)) * val for pt, val in self.PIECE_VALUES.items())
        
        # Simula mossa
        board_after = board_before.copy()
        board_after.push(move)
        
        # Materiale nostro dopo la mossa (ha perso il pezzo mosso se catturato? No, conta i pezzi sulla scacchiera)
        # Attenzione: se catturo, il mio materiale non cambia, cambia quello avversario.
        # Un sacrificio è: il mio materiale diminuisce DOPO la risposta avversaria, 
        # OPPURE metto un pezzo in presa.
        
        # Approccio euristico veloce per "Brilliant":
        # Se muovo un pezzo di valore X in una casa controllata da un pedone nemico 
        # o pezzo di minor valore, e il motore dice "Best", è un sacrificio.
        
        to_sq = move.to_square
        piece = board_before.piece_at(move.from_square)
        if not piece: return False
        
        # Chi attacca la casa di arrivo?
        attackers = board_after.attackers(not turn, to_sq)
        if not attackers: return False
        
        # Se ci sono attaccanti, è un pezzo difeso?
        defenders = board_after.attackers(turn, to_sq)
        
        # Valore del pezzo che muovo
        my_val = self.PIECE_VALUES[piece.piece_type]
        
        # Valore minimo dell'attaccante
        min_attacker_val = 99
        for sq in attackers:
            p = board_after.piece_at(sq)
            if p: min_attacker_val = min(min_attacker_val, self.PIECE_VALUES[p.piece_type])
            
        # Se muovo la Regina su una casa attaccata da un pedone -> Sacrificio potenziale
        if my_val > min_attacker_val:
            return True
            
        return False

    # --------------------------------------------------------------------------
    # 5. MAIN ANALYSIS LOOP
    # --------------------------------------------------------------------------

    def analyze_game(self, pgn_str: str, user_username: str) -> Tuple[List[Any], Any]:
        """
        Esegue l'analisi completa integrando motore e logica.
        Restituisce (moves_analysis, game_stats).
        """
        import streamlit as st # Usato solo per progress bar
        
        pgn_io = io.StringIO(pgn_str)
        game = chess.pgn.read_game(pgn_io)
        if not game: raise ValueError("PGN Invalido")

        # Setup Stats
        # Nota: Importiamo le classi definite nel file originale (devono essere disponibili nello scope)
        # Per questo snippet, assumiamo che GameStats e MoveAnalysis siano disponibili globalmente o passati.
        # Qui le userò come definite nel tuo file.
        stats = GameStats() 
        stats.white_player = game.headers.get("White", "Unknown")
        stats.black_player = game.headers.get("Black", "Unknown")
        stats.opening = game.headers.get("Opening", "Standard Game")
        
        user_color = chess.WHITE
        if stats.black_player.lower() == user_username.lower():
            user_color = chess.BLACK

        board = game.board()
        moves = list(game.mainline_moves())
        total_moves = len(moves)
        
        analysis_results = []
        
        # Setup Engine
        with chess.engine.SimpleEngine.popen_uci(self.engine_path) as engine:
            engine.configure({"Hash": self.hash_size, "Threads": self.threads})
            
            # Progress Setup
            progress_bar = st.progress(0)
            status_text = st.empty()

            prev_wp = 50.0 # Start Win Probability
            prev_score_cp = 0.3 # Start Evaluation (leggero vantaggio bianco)

            for i, move in enumerate(moves):
                status_text.text(f"Analisi Profonda: Mossa {i+1}/{total_moves}")
                
                # 1. Snapshot Before Move
                fen_before = board.fen()
                board_before = board.copy() # Necessaria per controlli sacrificali
                
                # 2. Identify Metadata (SAN & Time)
                try: move_san = board.san(move)
                except: move_san = move.uci()
                
                # Simulazione tempo (come nel codice originale)
                time_spent = 10.0 
                
                # 3. Engine Analysis (After Move)
                board.push(move)
                fen_after = board.fen()
                
                # Analizziamo la posizione RAGGIUNTA.
                # Per valutare la qualità della mossa, dobbiamo sapere:
                # A) Score della posizione PRE-mossa (Best Play)
                # B) Score della posizione POST-mossa (Actual Play)
                # Per ottimizzare, usiamo il multipv=2 sulla posizione PRE-mossa?
                # No, seguiamo il flusso lineare ma robusto.
                
                limit = chess.engine.Limit(time=0.15, depth=18)
                info = engine.analyse(board, limit)
                
                # Score dal punto di vista del giocatore che HA MOSSO (non di chi tocca ora)
                # Esempio: Bianco muove. Tocca al Nero. Engine valuta per Nero.
                # Noi vogliamo valutare la mossa del Bianco.
                pov_score = info["score"].pov(not board.turn) 
                
                score_val = 0.0
                is_mate = pov_score.is_mate()
                
                if is_mate:
                    score_val = 10000.0 if pov_score.mate() > 0 else -10000.0
                else:
                    score_val = pov_score.score() / 100.0
                
                # 4. Calculate Win Probability & Accuracy
                current_wp = self.calculate_win_probability(score_val, is_mate)
                
                # Delta WP (dal punto di vista di chi ha mosso)
                # Se prev_wp era 60% (mio vantaggio) e ora current_wp è 40% (ho perso vantaggio)
                # Nota: prev_wp è calcolato sulla mossa precedente. 
                # Dobbiamo invertire prev_wp se cambia il turno?
                # Il WP è assoluto (es. probabilità che il BIANCO vinca).
                # Convertiamolo sempre in "Probabilità che IO vinca".
                
                wp_me_before = prev_wp if (not board.turn) == chess.WHITE else (100 - prev_wp)
                wp_me_after = current_wp if (not board.turn) == chess.WHITE else (100 - current_wp)
                
                delta_wp = (wp_me_after - wp_me_before) * 100 # Percentuale
                
                # 5. Determine Rank (Is it best move?)
                # Semplificazione: se delta_wp è molto piccolo, è Best.
                # Per "Brilliant" serve sapere se era la top engine move.
                # Assumiamo rank=0 se delta > -0.5% (approx)
                rank = 0 if delta_wp > -1.0 else 1 
                
                # 6. Check Sacrifice & Tactics
                is_sac = self.is_static_sacrifice(board_before, move)
                tactical_tags = self.detect_tactical_patterns(board_before, move)
                struct_tags = self.analyze_structure(board)
                
                # 7. Classification
                cls, badge = self.classify_move_advanced(
                    delta_wp=wp_me_after - wp_me_before, # Passiamo valori 0-100 puri
                    rank=rank,
                    is_capture=board_before.is_capture(move),
                    is_material_sacrifice=is_sac,
                    score_cp=score_val,
                    prev_eval_cp=prev_score_cp
                )
                
                # Narrative Generation (Arricchita)
                narrative_parts = []
                if tactical_tags: narrative_parts.append(f"Tattica trovata: {', '.join(tactical_tags)}.")
                if struct_tags: narrative_parts.append(f"Note posizionali: {', '.join(struct_tags)}.")
                if cls == "Brilliant": narrative_parts.append("Hai sacrificato materiale per un attacco vincente!")
                if cls == "Blunder": narrative_parts.append(f"Hai ridotto le tue probabilità di vittoria del {abs(wp_me_after - wp_me_before):.1f}%.")
                
                full_narrative = " ".join(narrative_parts) if narrative_parts else "Mossa solida di sviluppo/manovra."

                # Update Stats (Solo per utente)
                is_user = (not board.turn) == user_color
                if is_user:
                    stats.counts[cls.lower()] += 1
                    # Accuracy (sperimentale)
                    move_acc = self.get_accuracy_score(wp_me_before, wp_me_after)
                    stats.accuracies.append(move_acc)

                # Store Result
                res = MoveAnalysis(
                    move_no=(i // 2) + 1,
                    move_san=move_san,
                    fen=fen_after,
                    score=score_val,
                    classification=cls,
                    best_move="-", # Richiederebbe seconda analisi
                    time_spent=time_spent,
                    narrative=full_narrative,
                    fen_before=fen_before
                )
                analysis_results.append(res)
                
                # Update loop vars
                prev_wp = current_wp # WP assoluto bianco
                prev_score_cp = score_val
                progress_bar.progress((i + 1) / total_moves)

        # Finalizza statistiche
        stats.avg_time /= total_moves if total_moves > 0 else 1
        total_acc = len(stats.accuracies)
        if total_acc > 0:
            stats.phases['opening'] = sum(stats.accuracies[:10])/10 if total_acc >= 10 else 100
            mid = int(total_acc * 0.6)
            stats.phases['middlegame'] = sum(stats.accuracies[10:mid])/(mid-10) if mid > 10 else 100
            stats.phases['endgame'] = sum(stats.accuracies[mid:])/(total_acc-mid) if total_acc > mid else 100

        progress_bar.empty()
        status_text.empty()
        
        return analysis_results, stats

# ==============================================================================
# INTEGRAZIONE SUGGERITA
# ==============================================================================
# Sostituisci la funzione 'run_full_analysis' originale con:
#
# analyzer = ChessAnalyzer(engine_path)
# results, stats = analyzer.analyze_game(pgn_to_analyze, username)
#
# Nota: Assicurati che MoveAnalysis e GameStats siano definite prima di questa

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
    # Configurazione pagina per una visualizzazione ottimale dei grafici e della scacchiera
    st.set_page_config(page_title=AppConfig.APP_TITLE, layout="wide")
    st.title(AppConfig.APP_TITLE)
    
    # --- SIDEBAR CONFIGURATION ---
    with st.sidebar:
        st.header("⚙️ Configurazione")
        
        # Selezione Piattaforma
        platform = st.radio("Piattaforma", ["Chess.com", "Lichess", "Manuale"])
        username = st.text_input("Username", "MagnusCarlsen" if platform != "Manuale" else "")
        
        pgn_manual = ""
        if platform == "Manuale":
            pgn_manual = st.text_area("Incolla PGN", height=150)
        
        # Gestione Percorso Motore
        engine_path = EngineManager.get_engine_path()
        st.session_state.engine_path = engine_path 
        
        if engine_path and EngineManager.is_available(engine_path):
            st.success(f"✅ Motore Attivo: {os.path.basename(engine_path)}")
        else:
            st.error("❌ Stockfish non trovato!")
            st.info("Scarica stockfish e mettilo nella cartella del file.")

        st.divider()
        st.caption(f"v{AppConfig.VERSION} | Powered by Python-Chess")

    # --- MAIN CONTENT AREA ---
    col_action, col_status = st.columns([3, 1])
    
    with col_action:
        analyze_btn = st.button("🚀 AVVIA ANALISI GRANDMASTER", type="primary", use_container_width=True)
    
    if analyze_btn:
        pgn_to_analyze = None
        if not engine_path:
            st.error("Impossibile avviare: Motore mancante.")
        else:
            with st.spinner("Analisi in corso... Stockfish sta calcolando..."):
                if platform == "Chess.com":
                    data = GameFetcher.fetch_chesscom_latest(username)
                    if data: pgn_to_analyze = data['pgn']
                elif platform == "Lichess":
                    data = GameFetcher.fetch_lichess_latest(username)
                    if data: pgn_to_analyze = data['pgn']
                else:
                    pgn_to_analyze = pgn_manual

                if pgn_to_analyze:
                    try:
                        analyzer = ChessAnalyzer(engine_path) 
                        results, stats = analyzer.analyze_game(pgn_to_analyze, username)
                        
                        # Salvataggio nello stato della sessione
                        st.session_state.game_analysis = results
                        st.session_state.game_stats = stats
                        st.session_state.game_pgn = pgn_to_analyze
                        st.session_state.analysis_ready = True
                        
                        st.success(f"✅ Analisi completata!")
                        st.rerun() 
                    except Exception as e:
                        st.error(f"Errore durante l'analisi: {e}")
                else:
                    st.warning("Carica un PGN per iniziare.")

    # --- 2. RESULTS DASHBOARD ---
    if st.session_state.get('analysis_ready') and st.session_state.get('game_analysis'):
        results = st.session_state.game_analysis
        stats = st.session_state.game_stats
        
        tab_overview, tab_replay, tab_coach, tab_training = st.tabs([
            "📊 Overview & Report", "♟️ Replay & Narrativa", "👨‍🏫 Coach Virtuale", "🧩 Training Center"
        ])
        
        with tab_overview:
            st.markdown(f"### 🏳️ {stats.white_player} vs 🏴 {stats.black_player}")
            st.caption(f"Apertura: {stats.opening}")
            
            # KPI Row
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            avg_acc = np.mean(stats.accuracies) if stats.accuracies else 0
            kpi1.metric("Precisione Globale", f"{avg_acc:.1f}%")
            kpi2.metric("Blunders", stats.counts['blunder'], delta="Gravi" if stats.counts['blunder']>0 else None, delta_color="inverse")
            kpi3.metric("Brilliant", stats.counts['brilliant'], delta="Geniale!" if stats.counts['brilliant']>0 else None)
            kpi4.metric("Tempo/Mossa", f"{int(stats.avg_time)}s")
            
            st.divider()
            # Grafico Vantaggio Ottimizzato
            evals = [r.score if isinstance(r.score, (int, float)) else 0 for r in results]
            fig, ax = plt.subplots(figsize=(12, 3))
            ax.plot(evals, color='#4CAF50', linewidth=2)
            ax.fill_between(range(len(evals)), evals, 0, where=(np.array(evals)>0), color='#4CAF50', alpha=0.2)
            ax.fill_between(range(len(evals)), evals, 0, where=(np.array(evals)<0), color='#FF5252', alpha=0.2)
            ax.axhline(0, color='#555', linestyle='--')
            ax.set_facecolor("#0e1117")
            fig.patch.set_facecolor("#0e1117")
            ax.tick_params(colors='white')
            st.pyplot(fig)
            
            # Breakdown Fasi
            st.subheader("Performance per Fase")
            ph_col1, ph_col2, ph_col3 = st.columns(3)
            ph_col1.metric("Apertura", f"{stats.phases['opening']:.1f}%")
            ph_col2.metric("Mediogioco", f"{stats.phases['middlegame']:.1f}%")
            ph_col3.metric("Finale", f"{stats.phases['endgame']:.1f}%")

        with tab_replay:
            col_board, col_narrative = st.columns([1.5, 1])
            
            total_moves = len(results)
            move_idx = st.slider("Timeline Partita", 0, total_moves-1, key="replay_slider")
            current = results[move_idx]
            
            with col_board:
                user_is_white = stats.white_player.lower() == username.lower()
                flip_board = chess.WHITE if user_is_white else chess.BLACK
                
                board_svg = chess.svg.board(
                    board=chess.Board(current.fen_after),
                    lastmove=chess.Move.from_uci(current.move_uci) if current.move_uci else None,
                    orientation=flip_board,
                    size=450
                )
                st.image(f"data:image/svg+xml;base64,{base64.b64encode(board_svg.encode()).decode()}", use_container_width=True)
                    
            with col_narrative:
                st.markdown(f"### Mossa {current.move_no} ({current.move_san})")
                
                cls_lower = current.classification.lower()
                badge_map = {
                    "brilliant": "badge-brilliant",
                    "blunder": "badge-blunder",
                    "mistake": "badge-mistake",
                    "best": "badge-accent",
                    "excellent": "badge-accent",
                    "good": "badge-good"
                }
                badge_class = badge_map.get(cls_lower, "badge-good")
                st.markdown(f'<span class="badge {badge_class}">{current.classification.upper()}</span>', unsafe_allow_html=True)
                
                m1, m2 = st.columns(2)
                m1.metric("Engine Score", f"{current.score}")
                m2.metric("Win Chance", f"{current.win_prob:.1f}%")
                
                st.markdown(f"""
                <div class="narrative-box">
                    <strong>♟️ Analisi Strategica:</strong><br>
                    {current.narrative}
                </div>
                """, unsafe_allow_html=True)

        with tab_coach:
            st.markdown("### 👨‍🏫 Profilo Psicologico")
            if stats.psych_profile:
                for trait in set(stats.psych_profile):
                    st.error(f"⚠️ **{trait}**: Rilevato pattern critico nel tuo gioco.")
                st.info("Consiglio: Fai una pausa di 5 minuti dopo questa analisi.")
            else:
                st.success("✅ Mindset Solido: Nessun segno di tilt o gioco impulsivo.")
            
            st.divider()
            st.subheader("📚 Percorso di Miglioramento")
            
            weakness = False
            if stats.phases['opening'] < 70:
                search_query = stats.opening.replace(' ', '+')
                st.markdown(f"- **Studio Aperture**: Hai faticato in apertura. [Guarda video su {stats.opening}](https://www.youtube.com/results?search_query=chess+opening+{search_query})")
                weakness = True
            if stats.counts['blunder'] > 2:
                st.markdown("- **Tattica**: Troppi errori gravi. Risolvi almeno 10 puzzle oggi.")
                weakness = True
            
            if not weakness:
                st.balloons()
                st.success("Partita quasi perfetta! Concentrati sulla costanza.")

        with tab_training:
            st.subheader("🧩 I Tuoi Errori -> I Tuoi Puzzle")
            blunders = [r for r in results if r.classification in ["Blunder", "Mistake"]]
            
            if not blunders:
                st.success("Nessun errore grave trovato! Ottimo lavoro.")
            else:
                puz_idx = st.selectbox("Seleziona scenario", range(len(blunders)), format_func=lambda x: f"Mossa {blunders[x].move_no} ({blunders[x].move_san})")
                scenario = blunders[puz_idx]
                
                col_p_b, col_p_s = st.columns(2)
                with col_p_b:
                    st.markdown("**Trova la mossa corretta:**")
                    st.markdown(render_board_svg(scenario.fen_before), unsafe_allow_html=True)
                with col_p_s:
                    st.warning(f"La tua mossa è stata: {scenario.move_san}")
                    with st.expander("👁️ Vedi Soluzione"):
                        st.code(f"FEN: {scenario.fen_before}")
                        st.write("Usa Stockfish per trovare la mossa che mantiene il vantaggio.")

if __name__ == "__main__":
    main()
