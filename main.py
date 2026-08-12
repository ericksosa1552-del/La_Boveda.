import random
import requests
import hashlib
import os
import hmac
import time
import json
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Request, Form, Response, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor

# --- IMPORTACIÓN DEL MÓDULO IA ---
from ai_brain import AIBrain
ai_brain = AIBrain()

app = FastAPI(title="La Bóveda", version="5.2")
templates = Jinja2Templates(directory="templates")

# ==========================================
# CONFIGURACIÓN DEL ADMINISTRADOR Y ZONA HORARIA
# ==========================================
ADMIN_EMAIL = "ericksosa1552@gmail.com"
ZONA_HORARIA_OFFSET = -6  
tz_local = timezone(timedelta(hours=ZONA_HORARIA_OFFSET))

def obtener_hora_local():
    return datetime.now(tz_local).strftime("%Y-%m-%d %H:%M:%S")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:TU_CONTRASEÑA@TU_HOST:5432/postgres")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot_status = {"is_operating": False, "mode": "demo"}

def send_telegram_alert(message: str, target_chat_id: Optional[str] = None):
    chat_to_use = target_chat_id if target_chat_id else TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not chat_to_use: return
    formatted_message = f"📊 <b>LA BÓVEDA | Reporte de Sistema</b>\n────────────────────────\n{message}\n────────────────────────\n🕒 <i>{obtener_hora_local()}</i>\n⚙️ <i>Estado: En línea</i>"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_to_use, "text": formatted_message, "parse_mode": "HTML"}
    try: requests.post(url, json=payload, timeout=5)
    except: pass

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS operations (id SERIAL PRIMARY KEY, timestamp TEXT, mode TEXT, symbol TEXT, action TEXT, price REAL, amount REAL, status TEXT, profit_loss REAL, market_pattern_id TEXT, user_email TEXT DEFAULT \'\')')
        cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
        cursor.execute("INSERT INTO settings (key, value) VALUES ('capital_ceiling', '100.0') ON CONFLICT (key) DO NOTHING")
        cursor.execute("INSERT INTO settings (key, value) VALUES ('trading_mode', 'demo') ON CONFLICT (key) DO NOTHING")
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, email TEXT UNIQUE, password_hash TEXT, failed_attempts INTEGER DEFAULT 0, is_blocked INTEGER DEFAULT 0, binance_api_key TEXT DEFAULT '', binance_secret_key TEXT DEFAULT '', trading_mode TEXT DEFAULT 'demo', secondary_email TEXT DEFAULT '', capital_ceiling REAL DEFAULT 100.0, emergency_stop TEXT DEFAULT 'false', telegram_chat_id TEXT DEFAULT '')''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS sessions (session_token TEXT PRIMARY KEY, email TEXT, created_at TEXT)''')
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e: print(f"Error inicializando DB: {e}")

init_db()

def hash_password(password: str) -> str: return hashlib.sha256(password.encode()).hexdigest()

def execute_automated_trade(target_user_email: Optional[str] = None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        exec_user = target_user_email if target_user_email else ADMIN_EMAIL
        
        if exec_user == ADMIN_EMAIL:
            cursor.execute("SELECT key, value FROM settings WHERE key IN ('emergency_stop', 'trading_mode', 'capital_ceiling')")
            data = {r['key']: r['value'] for r in cursor.fetchall()}
            mode = data.get('trading_mode', 'demo')
            capital_ceiling = float(data.get('capital_ceiling', 100.0))
            if data.get('emergency_stop') == 'true': 
                cursor.close()
                conn.close()
                return
        else:
            cursor.execute("SELECT emergency_stop, trading_mode, capital_ceiling FROM users WHERE email = %s", (exec_user,))
            u = cursor.fetchone()
            if not u or str(u['emergency_stop']).lower() == 'true': 
                cursor.close()
                conn.close()
                return
            mode = u['trading_mode']
            capital_ceiling = float(u['capital_ceiling'])
        
        cursor.close()
        conn.close()

        # --- SIMULACIÓN DE PAR Y PnL ---
        par = random.choice([{"simbolo": "BTCUSDT", "base": 64532.57}, {"simbolo": "SOLUSDT", "base": 184.50}])
        price = par["base"] + round(random.uniform(-5.0, 5.0), 2)
        amount = round(capital_ceiling * 0.01, 2)
        profit_loss = round(random.uniform(3.0, 6.0), 2) if random.random() > 0.3 else round(random.uniform(-0.5, -0.1), 2)
        
        ai_brain.analyze_and_evolve(mode, last_trade_profit=profit_loss)
        confidence_score = ai_brain.evaluate_signal_confidence(random.uniform(75.0, 95.0))

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO operations (timestamp, mode, symbol, action, price, amount, status, profit_loss, user_email) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)', 
                       (obtener_hora_local(), mode, par["simbolo"], "COMPRA", price, amount, "EXITOSA" if profit_loss > 0 else "AJUSTADA", profit_loss, exec_user))
        conn.commit()
        cursor.close()
        conn.close()

        alert_msg = f"🚀 <b>Operación ({mode.upper()})</b>\n• <b>Usuario:</b> {exec_user}\n• <b>Par:</b> {par['simbolo']}\n• <b>PnL:</b> {profit_loss} USDT\n• <b>Confianza IA:</b> {confidence_score}%"
        send_telegram_alert(alert_msg)

    except Exception as e: print(f"Error en ejecución: {e}")

# ==========================================
# RUTAS DE LA APLICACIÓN WEB
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, session_token: Optional[str] = Cookie(None)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    logged_in = False
    user_email = ""
    
    if session_token:
        cursor.execute("SELECT email FROM sessions WHERE session_token = %s", (session_token,))
        session = cursor.fetchone()
        if session:
            logged_in = True
            user_email = session['email']

    cursor.execute("SELECT key, value FROM settings")
    settings_data = {r['key']: r['value'] for r in cursor.fetchall()}
    cursor.close()
    conn.close()

    return templates.TemplateResponse(request, "index.html", {
        "request": request,
        "logged_in": logged_in,
        "user_email": user_email,
        "emergency_stop": settings_data.get("emergency_stop", "false"),
        "trading_mode": settings_data.get("trading_mode", "demo"),
        "capital_ceiling": settings_data.get("capital_ceiling", "100.0")
    })

@app.get("/cron-ping")
async def cron_ping():
    execute_automated_trade(ADMIN_EMAIL)
    return {"status": "success"}
