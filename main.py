import random
import requests
import hashlib
import os
import hmac
import time
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Request, Form, Response, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(title="La Bóveda", version="5.0")

# Configurar la carpeta de templates para que FastAPI lea el HTML correcto
templates = Jinja2Templates(directory="templates")

# ==========================================
# CONFIGURACIÓN DE ZONA HORARIA (HORA LOCAL)
# ==========================================
ZONA_HORARIA_OFFSET = -6  
tz_local = timezone(timedelta(hours=ZONA_HORARIA_OFFSET))

def obtener_hora_local():
    return datetime.now(tz_local).strftime("%Y-%m-%d %H:%M:%S")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:TU_CONTRASEÑA@TU_HOST:5432/postgres")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8536842251")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS operations (
            id SERIAL PRIMARY KEY,
            timestamp TEXT,
            mode TEXT,
            symbol TEXT,
            action TEXT,
            price REAL,
            amount REAL,
            status TEXT,
            profit_loss REAL,
            market_pattern_id TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    cursor.execute("INSERT INTO settings (key, value) VALUES ('capital_ceiling', '500.0') ON CONFLICT (key) DO NOTHING")
    cursor.execute("INSERT INTO settings (key, value) VALUES ('trading_mode', 'testnet') ON CONFLICT (key) DO NOTHING")
    conn.commit()
    cursor.close()
    conn.close()

init_db()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Renderiza la interfaz limpia desde la carpeta templates
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/token")
async def api_token(data: dict):
    user_id = data.get("user_id")
    api_key = data.get("api_key")
    api_secret = data.get("api_secret")
    mode = data.get("mode")
    
    if not user_id or not api_key or not api_secret:
        return {"detail": "Faltan datos obligatorios"}, 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO settings (key, value) VALUES ('binance_api_key', %s) ON CONFLICT (key) DO UPDATE SET value = %s", (api_key, api_key))
    cursor.execute("INSERT INTO settings (key, value) VALUES ('binance_secret_key', %s) ON CONFLICT (key) DO UPDATE SET value = %s", (api_secret, api_secret))
    cursor.execute("INSERT INTO settings (key, value) VALUES ('trading_mode', %s) ON CONFLICT (key) DO UPDATE SET value = %s", (mode, mode))
    conn.commit()
    cursor.close()
    conn.close()
    
    return {"status": "success", "message": "Credenciales guardadas correctamente"}

@app.post("/api/configurar-techo")
async def configurar_techo(data: dict):
    user_id = data.get("user_id")
    techo_capital = data.get("techo_capital")
    
    if techo_capital is None:
        return {"detail": "Techo de capital no válido"}, 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO settings (key, value) VALUES ('capital_ceiling', %s) ON CONFLICT (key) DO UPDATE SET value = %s", (str(techo_capital), str(techo_capital)))
    conn.commit()
    cursor.close()
    conn.close()
    
    return {"status": "success", "techo_capital": techo_capital}

@app.get("/api/estado")
async def obtener_estado(user_id: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT SUM(profit_loss) as total FROM operations")
    row_pnl = cursor.fetchone()
    balance = row_pnl['total'] if row_pnl and row_pnl['total'] is not None else 0.00
    
    cursor.execute("SELECT COUNT(*) as count FROM operations")
    row_ops = cursor.fetchone()
    ops_activas = row_ops['count'] if row_ops else 0
    
    cursor.execute("SELECT value FROM settings WHERE key = 'capital_ceiling'")
    row_techo = cursor.fetchone()
    techo_capital = float(row_techo['value']) if row_techo and row_techo['value'] else 500.00
    
    cursor.close()
    conn.close()
    
    return {
        "activo": True,
        "balance": balance,
        "operaciones_activas": ops_activas,
        "techo_capital": techo_capital
    }
