import time
import logging
from typing import Dict, Any, Optional

# Configuración de logs para auditoría en tiempo real
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LaBovedaSecurity")

class RiskEngine:
    def __init__(self, total_capital: float):
        self.total_capital = total_capital
        self.daily_pnl = 0.0          # Control de pérdidas/ganancias diarias
        self.active_trades = 0        # Contador de operaciones abiertas
        self.is_kill_switch_active = False # Interruptor de emergencia global
        self.last_trade_timestamp = 0
        
        # --- Parámetros de Seguridad Configurados ---
        self.MAX_RISK_PER_TRADE_PCT = 0.02  # Arriesgar máximo 2% del capital por operación
        self.MAX_SIMULTANEOUS_TRADES = 3    # Máximo 3 operaciones abiertas a la vez
        self.MAX_DAILY_LOSS_PCT = 0.05      # Kill Switch: Apagar si se pierde un 5% en el día
        self.COOLDOWN_PERIOD_SECONDS = 15   # Anti-Spam: Mínimo 15s entre órdenes (evita bucles)
        self.MAX_ALLOWED_SL_PCT = 0.04      # Stop Loss máximo permitido (4% de distancia)

    def evaluar_y_procesar_orden(self, orden_externa: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Interceptor de seguridad para cualquier señal (IA propia o Copy Trading).
        Aplica todas las capas de protección antes de enviar a Binance Testnet.
        """
        
        # 1. Verificación del Kill Switch de Emergencia
        if self.is_kill_switch_active:
            logger.critical("🚨 [KILL SWITCH] Operaciones bloqueadas. Se alcanzó el límite de pérdida diaria.")
            return None

        # 2. Control de Frecuencia (Anti-Spam / Rate Limiting)
        tiempo_actual = time.time()
        if (tiempo_actual - self.last_trade_timestamp) < self.COOLDOWN_PERIOD_SECONDS:
            logger.warning("⚠️ [COOLDOWN] Orden rechazada por protección anti-frecuencia.")
            return None

        # 3. Límite de Exposición Simultánea
        if self.active_trades >= self.MAX_SIMULTANEOUS_TRADES:
            logger.warning(f"⚠️ [EXPOSICIÓN] Límite de {self.MAX_SIMULTANEOUS_TRADES} operaciones simultáneas alcanzado.")
            return None

        # Extracción de datos de la señal
        activo = orden_externa.get("symbol")
        precio_entrada = orden_externa.get("entry_price")
        stop_loss_sugerido = orden_externa.get("stop_loss")
        take_profit = orden_externa.get("take_profit")

        if not all([activo, precio_entrada, stop_loss_sugerido]):
            logger.error("❌ [DATOS INVÁLIDOS] La señal no contiene los parámetros mínimos requeridos.")
            return None

        # 4. Cálculo y Validación Independiente del Stop Loss (Aislamiento de Riesgo)
        sl_distancia_pct = abs(precio_entrada - stop_loss_sugerido) / precio_entrada
        
        if sl_distancia_pct > self.MAX_ALLOWED_SL_PCT:
            logger.warning(f"⚠️ [SL AJUSTADO] El Stop Loss sugerido ({sl_distancia_pct:.2%}) supera el límite seguro. Aplicando ajuste estricto.")
            # Forzar un Stop Loss seguro basado en la política de La Bóveda
            stop_loss_sugerido = precio_entrada * (1 - self.MAX_ALLOWED_SL_PCT)

        # 5. Cálculo Dinámico del Tamaño de la Posición (Position Sizing)
        # Asegura que si se toca el SL, la pérdida monetaria sea exactamente el % permitido del capital
        riesgo_por_unidad = abs(precio_entrada - stop_loss_sugerido)
        capital_a_arriesgar = self.total_capital * self.MAX_RISK_PER_TRADE_PCT
        
        # Cantidad de activos a comprar
        cantidad_tokens = capital_a_arriesgar / riesgo_por_unidad

        # 6. Empaquetado de la Orden Segura Lista para Testnet
        orden_segura = {
            "symbol": activo,
            "side": "BUY", # Comprar bajo
            "type": "LIMIT",
            "entry_price": precio_entrada,
            "quantity": round(cantidad_tokens, 4),
            "stop_loss": round(stop_loss_sugerido, 2),
            "take_profit": take_profit,
            "security_status": "APPROVED_BY_LA_BOVEDA"
        }

        # Actualizar estados de control
        self.last_trade_timestamp = tiempo_actual
        self.active_trades += 1
        
        logger.info(f"✅ [APROBADA] Orden segura generada para {activo}. Cantidad calculada: {cantidad_tokens:.4f}")
        return orden_segura

    def registrar_resultado_operacion(self, resultado_pnl: float):
        """Actualiza el balance diario y activa el Kill Switch si es necesario."""
        self.active_trades = max(0, self.active_trades - 1)
        self.daily_pnl += resultado_pnl
        
        limite_perdida_dinero = self.total_capital * self.MAX_DAILY_LOSS_PCT
        if self.daily_pnl <= -limite_perdida_dinero:
            self.is_kill_switch_active = True
            logger.critical(f"🛑 [ACTIVACIÓN DE EMERGENCIA] Pérdida diaria acumulada ({self.daily_pnl} USD) excede el límite permitido. Sistema bloqueado por seguridad.")