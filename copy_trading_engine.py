import logging

# Configuración básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CopyTradingEngine:
    def __init__(self, min_win_rate=0.65, loss_streak_limit=3):
        # Convertimos los umbrales en atributos dinámicos para autoevolución por IA
        self.min_win_rate = min_win_rate
        self.loss_streak_limit = loss_streak_limit
        
        # Almacenamiento de estadísticas de líderes (preparado para persistencia en BD)
        self.leader_stats = {}
        
        # Historial de adaptaciones realizadas por el motor de IA (para trazabilidad)
        self.evolution_log = []

    def get_leader_stats(self, leader_id):
        return self.leader_stats.get(leader_id, {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "current_loss_streak": 0,
            "ai_trust_score": 1.0  # Métrica adicional para ponderación futura con IA
        })

    def evolve_parameters(self, market_conditions: dict):
        """
        [Punto de integración para IA]
        Método diseñado para que un modelo de IA ajuste dinámicamente los umbrales 
        basándose en las condiciones globales del mercado (ej. alta volatilidad).
        """
        # Ejemplo lógico para el futuro:
        # if market_conditions.get("volatility") == "high":
        #     self.min_win_rate = 0.70  # Endurecer filtro
        #     self.loss_streak_limit = 2
        logger.info(f"Evaluando autoevolución de parámetros. Umbrales actuales - WinRate: {self.min_win_rate}, Racha límite: {self.loss_streak_limit}")

    def validate_signal(self, leader_id, signal_data, market_context=None):
        """
        Valida si una señal debe ser copiada. 
        Acepta opcionalmente 'market_context' para análisis predictivo de IA.
        """
        stats = self.get_leader_stats(leader_id)
        
        # 1. Validar muestra mínima de operaciones
        if stats["total_trades"] < 20:
            logger.info(f"Trader {leader_id} tiene muy pocas operaciones ({stats['total_trades']}). Saltando validación estricta.")
            return True

        # 2. Calcular Win Rate
        win_rate = stats["wins"] / stats["total_trades"]
        
        # 3. Aplicar Cortafuegos de Racha Perdedora
        if stats["current_loss_streak"] >= self.loss_streak_limit:
            logger.warning(f"Cortafuegos activado para {leader_id}: Racha de pérdidas alta ({stats['current_loss_streak']}).")
            return False
            
        # 4. Validar Win Rate mínimo
        if win_rate < self.min_win_rate:
            logger.warning(f"Trader {leader_id} no cumple el win rate del {self.min_win_rate*100}% (Actual: {win_rate*100:.2f}%).")
            return False
            
        # [Punto de integración futuro para IA de análisis de patrones de la señal]
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
            # Incremento leve de confianza administrado por el rendimiento
            stats["ai_trust_score"] = min(2.0, stats["ai_trust_score"] + 0.05)
        else:
            stats["losses"] += 1
            stats["current_loss_streak"] += 1
            # Penalización en la puntuación de confianza
            stats["ai_trust_score"] = max(0.2, stats["ai_trust_score"] - 0.15)
            
        logger.info(f"Stats actualizadas para {leader_id}: {stats}")
