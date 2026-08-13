import time
import hmac
import hashlib
import requests
import urllib.parse
import logging

logger = logging.getLogger("LaBovedaExecutor")

class BinanceExecutor:
    def __init__(self, api_key: str, secret_key: str, testnet: bool = True):
        self.api_key = api_key
        self.secret_key = secret_key
        # Usamos la URL de Testnet por defecto para pruebas seguras, o producción si testnet=False
        self.base_url = "https://testnet.binance.vision" if testnet else "https://api.binance.com"

    def _generate_signature(self, query_string: str) -> str:
        return hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def enviar_orden_mercado(self, orden_segura: dict) -> dict:
        """
        Recibe la orden aprobada por el RiskEngine y la ejecuta en Binance.
        """
        endpoint = "/api/v3/order"
        url = self.base_url + endpoint

        # Parámetros obligatorios para la API de Binance
        params = {
            "symbol": orden_segura["symbol"],
            "side": orden_segura["side"],          # "BUY" o "SELL"
            "type": orden_segura["type"],          # "LIMIT" o "MARKET"
            "quantity": orden_segura["quantity"],
            "timestamp": int(time.time() * 1000)
        }

        # Si es orden LIMIT, Binance exige el tiempo de expiración y precio
        if orden_segura["type"] == "LIMIT":
            params["timeInForce"] = "GTC"
            params["price"] = orden_segura["entry_price"]

        # Construir query string y agregar firma de seguridad
        query_string = urllib.parse.urlencode(params)
        signature = self._generate_signature(query_string)
        query_string += f"&signature={signature}"

        headers = {
            "X-MBX-APIKEY": self.api_key
        }

        full_url = f"{url}?{query_string}"

        try:
            logger.info(f"🚀 [BINANCE] Enviando orden para {orden_segura['symbol']}...")
            response = requests.post(full_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ [ÉXITO] Orden ejecutada en Binance. Order ID: {data.get('orderId')}")
                return {"success": True, "data": data}
            else:
                error_data = response.json()
                logger.error(f"❌ [ERROR BINANCE] {error_data.get('msg')} (Code: {error_data.get('code')})")
                return {"success": False, "error": error_data.get('msg')}
                
        except Exception as e:
            logger.error(f"❌ [EXCEPCIÓN DE RED] Error al conectar con la API de Binance: {e}")
            return {"success": False, "error": str(e)}
