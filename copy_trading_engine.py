import logging

# Configuración básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CopyTradingEngine:
    def __init__(self, min_win_rate=0.65, loss_streak_limit=3):
        self.min_win_rate = min_win_rate
        self.loss_streak_limit = loss_streak_limit
        # Estructura para almacenar el estado de los traders líderes
        # En una implementación real, esto vendría de una base de datos
        self.leader_stats = {}

    def get_leader_stats(self, leader_id):
        return self.leader_stats.get(leader_id, {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "current_loss_streak": 0
        })

    def validate_signal(self, leader_id, signal_data):
        stats = self.get_leader_stats(leader_id)
        
        # 1. Validar muestra mínima de operaciones (ejemplo: 20)
        if stats["total_trades"] < 20:
            logger.info(f"Trader {leader_id} tiene muy pocas operaciones. Saltando validación estricta.")
            return True

        # 2. Calcular Win Rate
        win_rate = stats["wins"] / stats["total_trades"]
        
        # 3. Aplicar Cortafuegos de Racha Perdedora
        if stats["current_loss_streak"] >= self.loss_streak_limit:
            logger.warning(f"Cortafuegos activado para {leader_id}: Racha de pérdidas alta.")
            return False
            
        # 4. Validar Win Rate mínimo del 65%
        if win_rate < self.min_win_rate:
            logger.warning(f"Trader {leader_id} no cumple el win rate del {self.min_win_rate*100}%.")
            return False
            
        return True

    def update_stats(self, leader_id, is_win):
        if leader_id not in self.leader_stats:
            self.leader_stats[leader_id] = {"total_trades": 0, "wins": 0, "losses": 0, "current_loss_streak": 0}
        
        stats = self.leader_stats[leader_id]
        stats["total_trades"] += 1
        
        if is_win:
            stats["wins"] += 1
            stats["current_loss_streak"] = 0
        else:
            stats["losses"] += 1
            stats["current_loss_streak"] += 1
            
        logger.info(f"Stats actualizadas para {leader_id}: {stats}")
