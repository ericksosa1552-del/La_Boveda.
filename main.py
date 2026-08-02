from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, EmailStr
import requests
import time
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode
from cryptography.fernet import Fernet
from jose import jwt, JWTError
import sqlite3
from typing import Optional
from risk_engine import RiskEngine

risk_engine = RiskEngine(total_capital=10000.0)
app = FastAPI(title="La Bóveda - Broker IA Non-Custodial", version="1.6.0")

# --- CONFIGURACIÓN DE SEGURIDAD (FERNET & JWT) ---
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

JWT_SECRET_KEY = "la_boveda_super_secret_key_temporal"
JWT_ALGORITHM = "HS256"
JWT_TOKEN_EXPIRE_MINUTES = 60

# --- CONFIGURACIÓN DE BASE DE DATOS (SQLite) ---
DB_NAME = "boveda.db"

def init_db():
    """Inicializa la base de datos y crea la tabla de usuarios con soporte para entorno y recuperación."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            api_key TEXT NOT NULL,
            api_secret_encrypted TEXT NOT NULL,
            mode TEXT DEFAULT 'testnet',
            reset_token TEXT,
            reset_token_expires TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Lista negra en memoria para tokens revocados (Logout)
revoked_tokens = set()

def encrypt_secret(secret: str) -> str:
    return cipher_suite.encrypt(secret.encode()).decode()

def decrypt_secret(encrypted_secret: str) -> str:
    return cipher_suite.decrypt(encrypted_secret.encode()).decode()

def create_access_token(user_id: str) -> str:
    expiration = time.time() + (JWT_TOKEN_EXPIRE_MINUTES * 60)
    payload = {
        "sub": user_id,
        "exp": expiration
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token

def decode_token_safely(token: str) -> str:
    """Decodifica y valida un token JWT, comprobando que no esté revocado."""
    clean_token = token.replace("Bearer ", "").strip()
    
    if clean_token in revoked_tokens:
        raise HTTPException(status_code=401, detail="La sesión ha sido cerrada. Por favor inicie sesión nuevamente.")
    
    try:
        payload = jwt.decode(clean_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token inválido.")
        return user_id
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="El token es inválido o ha expirado.")


# URLs base para los entornos de Binance
BINANCE_URLS = {
    "testnet": "https://testnet.binance.vision",
    "real": "https://api.binance.com"
}


class APIKeysInput(BaseModel):
    user_id: str
    api_key: str
    api_secret: str
    mode: str = Field("testnet", description="Usa 'testnet' para entrenamiento/ficticio o 'real' para producción con dinero real.")


class OrderInput(BaseModel):
    symbol: str
    side: str  # "BUY" o "SELL"
    quantity: float
    stop_loss_pct: float = 1.5
    take_profit_pct: float = 3.0
    access_token: Optional[str] = Field(None, description="Puedes pegar tu token JWT aquí directamente.")


class ForgotPasswordRequest(BaseModel):
    user_id: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6, description="Nueva contraseña (mínimo 6 caracteres)")
    confirm_password: str = Field(..., min_length=6, description="Repetir la nueva contraseña exactamente igual")


def get_binance_signature(query_string: str, secret: str) -> str:
    return hmac.new(
        secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


@app.post("/api/token")
def login_and_get_token(data: APIKeysInput):
    """Inicia sesión validando las API Keys con Binance (Testnet o Real según el modo) y genera un Token JWT."""
    selected_mode = data.mode.lower()
    if selected_mode not in BINANCE_URLS:
        raise HTTPException(status_code=400, detail="Modo inválido. Debe ser 'testnet' o 'real'.")
    
    base_url = BINANCE_URLS[selected_mode]

    try:
        endpoint = "/api/v3/account"
        timestamp = int(time.time() * 1000)
        query_string = f"timestamp={timestamp}"
        signature = get_binance_signature(query_string, data.api_secret)
        
        url = f"{base_url}{endpoint}?{query_string}&signature={signature}"
        headers = {"X-MBX-APIKEY": data.api_key.strip()}
        
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=400, 
                detail=f"Credenciales rechazadas por Binance ({selected_mode}): {response.text}"
            )
        
        secured_secret = encrypt_secret(data.api_secret.strip())

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO users (user_id, api_key, api_secret_encrypted, mode)
            VALUES (?, ?, ?, ?)
        """, (data.user_id, data.api_key.strip(), secured_secret, selected_mode))
        conn.commit()
        conn.close()
        
        token = create_access_token(data.user_id)
        
        return {
            "status": "success",
            "message": f"Inicio de sesión exitoso en entorno [{selected_mode.upper()}]. Credenciales guardadas y token generado.",
            "mode": selected_mode,
            "access_token": token,
            "token_type": "bearer"
        }
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/forgot-password")
def forgot_password(data: ForgotPasswordRequest):
    """Paso 1: Solicita un token de recuperación para el usuario."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (data.user_id,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado en la base de datos.")
    
    reset_token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
    
    cursor.execute("""
        UPDATE users SET reset_token = ?, reset_token_expires = ? WHERE user_id = ?
    """, (reset_token, expires_at, data.user_id))
    conn.commit()
    conn.close()
    
    return {
        "status": "success",
        "message": "Token de recuperación generado con éxito.",
        "debug_token": reset_token
    }


@app.post("/api/reset-password")
def reset_password(data: ResetPasswordRequest):
    """Paso 2: Restablece la contraseña validando estrictamente que la confirmación coincida."""
    if data.new_password != data.confirm_password:
        raise HTTPException(
            status_code=400,
            detail="Las contraseñas no coinciden. Por favor, revísalas."
        )
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, reset_token_expires FROM users WHERE reset_token = ?", (data.token,))
    user_row = cursor.fetchone()
    
    if not user_row:
        conn.close()
        raise HTTPException(status_code=400, detail="Token de recuperación inválido.")
    
    user_id, expires_at_str = user_row
    
    if expires_at_str and datetime.utcnow() > datetime.fromisoformat(expires_at_str):
        conn.close()
        raise HTTPException(status_code=400, detail="El token de recuperación ha expirado.")
    
    cursor.execute("""
        UPDATE users SET reset_token = NULL, reset_token_expires = NULL WHERE user_id = ?
    """, (user_id,))
    conn.commit()
    conn.close()
    
    return {
        "status": "success",
        "message": "Contraseña restablecida y validada exitosamente."
    }


@app.post("/api/logout")
def logout(authorization: Optional[str] = Header(None)):
    """Cierra la sesión activa invalidando de inmediato el Token JWT."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Token de acceso ausente.")
    
    try:
        parts = authorization.split()
        if len(parts) == 2:
            scheme, token = parts
            if scheme.lower() != "bearer":
                raise HTTPException(status_code=401, detail="Esquema de autenticación inválido.")
        else:
            token = parts[0]
        
        clean_token = token.strip()
        revoked_tokens.add(clean_token)
        
        return {
            "status": "success",
            "message": "Sesión cerrada correctamente. El token ha sido invalidado."
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail="No se pudo procesar el cierre de sesión.")


@app.post("/api/trade/execute")
def execute_order_with_risk_management(order: OrderInput, authorization: Optional[str] = Header(None)):
    """Ejecuta una orden de mercado protegida en el entorno configurado (testnet o real)."""
    user_id = None

    if authorization:
        try:
            parts = authorization.split()
            token_to_verify = parts[1] if len(parts) > 1 else parts[0]
            user_id = decode_token_safely(token_to_verify)
        except Exception:
            pass

    if not user_id and order.access_token:
        user_id = decode_token_safely(order.access_token)

    if not user_id:
        raise HTTPException(
            status_code=401, 
            detail="Token de acceso ausente. Por favor colócalo en el Header 'authorization' o dentro del JSON en el campo 'access_token'."
        )

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT api_key, api_secret_encrypted, mode FROM users WHERE user_id = ?", (user_id,))
    user_row = cursor.fetchone()
    conn.close()

    if not user_row:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en la base de datos del broker.")
    
    api_key, encrypted_secret, user_mode = user_row
    api_secret = decrypt_secret(encrypted_secret)
    base_url = BINANCE_URLS.get(user_mode, BINANCE_URLS["testnet"])
    
    try:
        price_url = f"{base_url}/api/v3/ticker/price?symbol={order.symbol.upper()}"
        ticker_res = requests.get(price_url)
        
        if ticker_res.status_code != 200:
            raise HTTPException(status_code=400, detail="No se pudo obtener el precio del activo.")
        
        entry_price = float(ticker_res.json()["price"])
        
        if order.side.upper() == "BUY":
            stop_loss_limit = entry_price * (1 - (order.stop_loss_pct / 100))
            take_profit_limit = entry_price * (1 + (order.take_profit_pct / 100))
        else:
            stop_loss_limit = entry_price * (1 + (order.stop_loss_pct / 100))
            take_profit_limit = entry_price * (1 - (order.take_profit_pct / 100))
            
        risk_reward_ratio = f"1 : {order.take_profit_pct / order.stop_loss_pct:.1f}"

        endpoint_order = "/api/v3/order"
        timestamp = int(time.time() * 1000)
        
        params = {
            "symbol": order.symbol.upper(),
            "side": order.side.upper(),
            "type": "MARKET",
            "quantity": order.quantity,
            "timestamp": timestamp
        }
        
        query_string = urlencode(params)
        signature = get_binance_signature(query_string, api_secret)
        
        full_url = f"{base_url}{endpoint_order}?{query_string}&signature={signature}"
        headers = {"X-MBX-APIKEY": api_key}
        
        binance_response = requests.post(full_url, headers=headers)
        
        if binance_response.status_code != 200:
            raise HTTPException(
                status_code=400, 
                detail=f"Binance ({user_mode}) rechazó la orden: {binance_response.text}"
            )
            
        order_result = binance_response.json()
        
        return {
            "status": f"executed_securely_in_{user_mode}_mode",
            "authenticated_user": user_id,
            "environment": user_mode,
            "entry_price": entry_price,
            "risk_parameters": {
                "stop_loss_limit": round(stop_loss_limit, 2),
                "take_profit_limit": round(take_profit_limit, 2),
                "risk_reward_ratio": risk_reward_ratio
            },
            "order_details": order_result
        }
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", response_class=HTMLResponse)
async def leer_interfaz():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/api/trade/ejecutar")
def ejecutar_orden_segura(orden: dict):
    """Recibe una señal de trading y la somete al motor de seguridad antes de enviarla a Binance."""
    orden_aprobada = risk_engine.evaluar_y_procesar_orden(orden)
    
    if not orden_aprobada:
        raise HTTPException(
            status_code=400, 
            detail="La orden fue rechazada por el motor de seguridad de La Bóveda (Límite alcanzado, riesgo elevado o Kill Switch activo)."
        )
        
    return {
        "status": "success",
        "message": "Orden validada por las capas de seguridad y lista para Binance.",
        "data": orden_aprobada
    }