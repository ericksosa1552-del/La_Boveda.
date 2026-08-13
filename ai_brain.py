import random
import logging
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

class AIBrain:
    def __init__(self, initial_win_rate=0.65, initial_loss_limit=3):
        self.min_win_rate = initial_win_rate
        self.loss_streak_limit = initial_loss_limit
        self.evolution_history = []
        self.load_memory()

    def get_db_connection(self):
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

    def load_memory(self):
        """Carga el estado evolutivo de la IA desde la base de datos."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = 'ai_brain_state'")
            row = cursor.fetchone()
            if row and row['value']:
                data = json.loads(row['value'])
                self.min_win_rate = data.get("min_win_rate", self.min_win_rate)
                self.loss_streak_limit = data.get("loss_streak_limit", self.loss_streak_limit)
                self.evolution_history = data.get("history", [])
                logger.info(f"🧠 [IA Brain] Memoria cargada. WinRate actual: {self.min_win_rate}")
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error cargando memoria de la IA: {e}")

    def save_memory(self):
        """Guarda el estado actual de la IA de forma persistente en la base de datos."""
        try:
            data = {
                "min_win_rate": self.min_win_rate,
                "loss_streak_limit": self.loss_streak_limit,
                "history": self.evolution_history[-50:]
            }
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO settings (key, value) VALUES ('ai_brain_state', %s) ON CONFLICT (key) DO UPDATE SET value = %s",
                (json.dumps(data), json.dumps(data))
            )
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error guardando memoria de la IA: {e}")

    def analyze_and_evolve(self, mode: str, last_trade_profit: float = None, is_live: bool = False):
        """Ajusta los parámetros y autoevoluciona basado en resultados reales con protección estricta en modo vivo."""
        
        if mode.lower() == "live":
            is_live = True

        if last_trade_profit is not None:
            if last_trade_profit > 0:
                reduction = 0.005 if is_live else 0.01
                self.min_win_rate = max(0.70 if is_live else 0.60, round(self.min_win_rate - reduction, 2))
            else:
                increase = 0.03 if is_live else 0.02
                self.min_win_rate = min(0.92, round(self.min_win_rate + increase, 2))
            
            self.evolution_history.append({
                "mode": mode, 
                "profit": last_trade_profit, 
                "new_win_rate": self.min_win_rate,
                "is_live": is_live
            })

        # Comportamiento de "Cirujano" (Modo Live de Alta Exigencia)
        if is_live:
            if self.min_win_rate < 0.78:
                self.min_win_rate = 0.78
            self.loss_streak_limit = 2  
        else:
            if self.min_win_rate < 0.65:
                self.min_win_rate = 0.65
            self.loss_streak_limit = 3
        
        self.save_memory()
        
        logger.info(f"🧠 [IA Brain] Evolución aplicada. Modo: {mode} | Live Mode: {is_live} | WinRate: {self.min_win_rate} | LossLimit: {self.loss_streak_limit}")
        return {"win_rate": self.min_win_rate, "loss_limit": self.loss_streak_limit}

    def evaluate_signal_confidence(self, base_confidence: float, is_live: bool = False) -> float:
        """Evalúa la confianza con filtros estrictos si se encuentra en modo real (Live)."""
        if is_live:
            ai_boost = random.uniform(-2.5, 1.5)
        else:
            ai_boost = random.uniform(-1.5, 2.5)
            
        final_confidence = round(min(max(base_confidence + ai_boost, 50.0), 99.9), 2)
        return final_confidence
