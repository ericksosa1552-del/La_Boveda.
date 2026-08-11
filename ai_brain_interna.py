# ai_brain.py (o ai_brain_interna.py)
import random
import logging
import json
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATE_FILE = "ai_memory.json"

class AIBrain:
    def __init__(self, initial_win_rate=0.65, initial_loss_limit=3):
        self.min_win_rate = initial_win_rate
        self.loss_streak_limit = initial_loss_limit
        self.evolution_history = []
        self.load_memory()  # Carga la memoria guardada previamente

    def load_memory(self):
        """Carga el estado previo de la IA desde el disco para tener memoria persistente."""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    data = json.load(f)
                    self.min_win_rate = data.get("min_win_rate", self.min_win_rate)
                    self.loss_streak_limit = data.get("loss_streak_limit", self.loss_streak_limit)
                    self.evolution_history = data.get("history", [])
                    logger.info(f"🧠 [IA Brain] Memoria cargada exitosamente. WinRate actual: {self.min_win_rate}")
            except Exception as e:
                logger.error(f"Error cargando memoria de la IA: {e}")

    def save_memory(self):
        """Guarda el estado actual en el disco para que no se pierda al reiniciar."""
        try:
            data = {
                "min_win_rate": self.min_win_rate,
                "loss_streak_limit": self.loss_streak_limit,
                "history": self.evolution_history[-50:] # Guarda los últimos 50 registros de evolución
            }
            with open(STATE_FILE, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Error guardando memoria de la IA: {e}")

    def analyze_and_evolve(self, mode: str, last_trade_profit: float = None):
        """
        Ajusta los parámetros según el modo y autoevoluciona 
        basándose en si la última operación fue ganadora o perdedora.
        """
        # Autoevolución basada en resultados reales si se proveen
        if last_trade_profit is not None:
            if last_trade_profit > 0:
                # Si ganó, se vuelve un poco más flexible y optimiza su confianza
                self.min_win_rate = max(0.60, round(self.min_win_rate - 0.01, 2))
            else:
                # Si perdió, se vuelve más estricta (defensiva)
                self.min_win_rate = min(0.85, round(self.min_win_rate + 0.02, 2))
            
            self.evolution_history.append({"mode": mode, "profit": last_trade_profit, "new_win_rate": self.min_win_rate})

        # Ajuste base por modo de operación
        if mode == "live":
            if self.min_win_rate < 0.75:
                self.min_win_rate = 0.75
            self.loss_streak_limit = 2
        else:
            if self.min_win_rate < 0.65:
                self.min_win_rate = 0.65
            self.loss_streak_limit = 3
        
        # Guarda los cambios en la memoria persistente
        self.save_memory()
        
        logger.info(f"🧠 [IA Brain] Evolución aplicada. Modo: {mode} | WinRate requerido: {self.min_win_rate}")
        return {"win_rate": self.min_win_rate, "loss_limit": self.loss_streak_limit}

    def evaluate_signal_confidence(self, base_confidence: float) -> float:
        """Calcula un factor de confianza ponderado por la IA."""
        ai_boost = random.uniform(-1.5, 2.5)
        final_confidence = round(min(max(base_confidence + ai_boost, 50.0), 99.9), 2)
        return final_confidence
