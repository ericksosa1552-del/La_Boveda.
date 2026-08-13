import logging
import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuración básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

class CopyTradingEngine:
    def __init__(self, min_win_rate=0.65, loss_streak_limit=3):
        # Convertimos los umbrales en atributos dinámicos para autoevolución por IA
        self.min_win_rate = min_win_rate
        self.loss_streak_limit = loss_streak_limit
        
        # Almacenamiento de estadísticas (ahora sincronizado con Supabase)
        self.leader_stats = {}
        self.load_engine_state()
        
        # Historial de adaptaciones realizadas por el motor de IA (para trazabilidad)
        self.evolution_log = []

    def get_db_connection(self):
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

    def load_engine_state(self):
        """Carga el estado persistente de los líderes y estadísticas desde Supabase."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = 'copy_trading_engine_state'")
            row = cursor.fetchone()
            if row and row['value']:
                import json
                data = json.loads(row['value'])
                self.leader_stats = data.get("leader_stats", {})
                self.min_win_rate = data.get("min_win_rate", self.min_win_rate)
                self.loss_streak_limit = data.get("loss_streak_limit", self.loss_streak_limit)
                logger.info("📈 [CopyTradingEngine] Estado cargado exitosamente desde Supabase.")
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error cargando estado del motor de Copy Trading desde Supabase: {e}")

    def save_engine_state(self):
        """Guarda el estado actual del motor de Copy Trading de forma persistente en Supabase."""
        try:
            import json
            data = {
                "leader_stats": self.leader_stats,
                "min_win_rate": self.min_win_rate,
                "loss_streak_limit": self.loss_streak_limit
            }
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO settings (key, value) VALUES ('copy_trading_engine_state', %s) ON CONFLICT (key) DO UPDATE SET value = %s",
                (json.dumps(data), json.dumps(data))
            )
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error guardando estado del motor de Copy Trading en Supabase: {e}")

    def get_leader_stats(self, leader_id):
        return self.leader_stats.get(leader_id, {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "current_loss_streak": 0,
            "ai_trust_score": 1.0  # Métrica adicional para ponderación futura con IA
        })

    def evolve_parameters(self, market_conditions: dict, is_live: bool = False):
        """
        [Integración con IA]
        Ajusta dinámicamente los umbrales basándose en las condiciones globales del mercado y modo live.
        """
        if is_live:
            # En modo real endurecemos los parámetros de seguridad por defecto
            self.min_win_rate = max(0.78, self.min_win_rate)
            self.loss_streak_limit = 2
        
        if market_conditions.get("volatility") == "high":
            self.min_win_rate = min(0.90, self.min_win_rate + 0.03)
            self.loss_streak_limit = min(self.loss_streak_limit, 2)

        self.save_engine_state()
        logger.info(f"Evaluando autoevolución de parámetros (Live: {is_live}). Umbrales actuales - WinRate: {self.min_win_rate}, Racha límite: {self.loss_streak_limit}")

    def validate_signal(self, leader_id, signal_data, market_context=None, is_live=False):
        """
        Valida si una señal debe ser copiada, aplicando filtros estrictos de 'cirujano' si está en modo live.
        """
        stats = self.get_leader_stats(leader_id)
        
        # 1. Validar muestra mínima de operaciones
        if stats["total_trades"] < (10 if is_live else 20):
            logger.info(f"Trader {leader_id} tiene pocas operaciones ({stats['total_trades']}).")
            if is_live:
                # En modo live exigimos más prudencia incluso con muestras cortas
                return False

        # Si no hay trades suficientes y no es live estricto
        if stats["total_trades"] < 20 and not is_live:
            return True

        # 2. Calcular Win Rate
        win_rate = stats["wins"] / stats["total_trades"] if stats["total_trades"] > 0 else 0.0
        
        # 3. Aplicar Cortafuegos de Racha Perdedora
        if stats["current_loss_streak"] >= self.loss_streak_limit:
            logger.warning(f"Cortafuegos activado para {leader_id}: Racha de pérdidas alta ({stats['current_loss_streak']}).")
            return False
            
        # 4. Validar Win Rate mínimo
        if win_rate < self.min_win_rate:
            logger.warning(f"Trader {leader_id} no cumple el win rate del {self.min_win_rate*100}% (Actual: {win_rate*100:.2f}%).")
            return False
            
        # 5. Filtro de IA predictiva (si existe contexto)
        if market_context and market_context.get("ai_veto", False):
            logger.warning(f"Señal rechazada por filtro de IA predictiva para el trader {leader_id}.")
            return False
            
        return True

    def update_stats(self, leader_id, is_win, trade_metadata=None):
        if leader_id not in self.leader_stats:
            self.leader_stats[leader_id] = {
                "total_trades": 0, 
                "wins": 0, 
                "losses": 0, 
                "current_loss_streak": 0,
                "ai_trust_score": 1.0
            }
        
        stats = self.leader_stats[leader_id]
        stats["total_trades"] += 1
        
        if is_win:
            stats["wins"] += 1
            stats["current_loss_streak"] = 0
            stats["ai_trust_score"] = min(2.0, stats["ai_trust_score"] + 0.05)
        else:
            stats["losses"] += 1
            stats["current_loss_streak"] += 1
            stats["ai_trust_score"] = max(0.2, stats["ai_trust_score"] - 0.15)
            
        self.save_engine_state()
        logger.info(f"Stats actualizadas y guardadas en Supabase para {leader_id}: {stats}")
