# ai_brain.py
import random
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIBrain:
    def __init__(self, initial_win_rate=0.65, initial_loss_limit=3):
        self.min_win_rate = initial_win_rate
        self.loss_streak_limit = initial_loss_limit
        self.evolution_history = []

    def analyze_and_evolve(self, mode: str):
        """
        Ajusta los parámetros de comportamiento según el modo (Demo/Live).
        """
        # Autoevolución: Modo Live es más conservador
        if mode == "live":
            self.min_win_rate = 0.75
            self.loss_streak_limit = 2
        else:
            self.min_win_rate = 0.65
            self.loss_streak_limit = 3
        
        logger.info(f"🧠 [IA Brain] Evolucionado a modo: {mode}. WinRate: {self.min_win_rate}")
        return {"win_rate": self.min_win_rate, "loss_limit": self.loss_streak_limit}

    def evaluate_signal_confidence(self, base_confidence: float) -> float:
        """
        Calcula un factor de confianza ponderado por la IA.
        """
        # El cerebro añade un factor aleatorio controlado de "intuición"
        ai_boost = random.uniform(-1.5, 2.5)
        final_confidence = round(min(max(base_confidence + ai_boost, 50.0), 99.9), 2)
        return final_confidence
