import requests

# Tus credenciales oficiales de Telegram recién creadas
TELEGRAM_BOT_TOKEN = "8610300157:AAG86zeR5BBF-o42_ZyyJPYneZf3uzmBxes"
TELEGRAM_CHAT_ID = "8536842251"

def enviar_alerta_telegram(mensaje: str):
    """
    Envía una notificación instantánea al chat de Telegram de La Bóveda.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": f"🚨 *LA BÓVEDA - ALERTA* 🚨\n\n{mensaje}",
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("[Telegram] Alerta enviada con éxito.")
            return True
        else:
            print(f"[Error Telegram] {response.text}")
            return False
    except Exception as e:
        print(f"[Error de conexión con Telegram]: {e}")
        return False

# Prueba rápida de funcionamiento:
if __name__ == "__main__":
    enviar_alerta_telegram("¡El sistema de notificaciones de La Bóveda se ha conectado correctamente!")
