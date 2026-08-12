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
        
        # Crear tablas base si no existen
        cursor.execute('CREATE TABLE IF NOT EXISTS operations (id SERIAL PRIMARY KEY)')
        cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
        cursor.execute("INSERT INTO settings (key, value) VALUES ('capital_ceiling', '100.0') ON CONFLICT (key) DO NOTHING")
        cursor.execute("INSERT INTO settings (key, value) VALUES ('trading_mode', 'demo') ON CONFLICT (key) DO NOTHING")
        cursor.execute("INSERT INTO settings (key, value) VALUES ('emergency_stop', 'false') ON CONFLICT (key) DO NOTHING")
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, email TEXT UNIQUE, password_hash TEXT, failed_attempts INTEGER DEFAULT 0, is_blocked INTEGER DEFAULT 0)''')
        
        # Añadir todas las columnas necesarias a operations si no existen
        ops_columns = [
            ("timestamp", "TEXT"), ("mode", "TEXT"), ("symbol", "TEXT"), 
            ("action", "TEXT"), ("price", "REAL"), ("amount", "REAL"), 
            ("status", "TEXT"), ("profit_loss", "REAL"), ("market_pattern_id", "TEXT"), ("user_email", "TEXT DEFAULT ''")
        ]
        for col_name, col_def in ops_columns:
            cursor.execute(f"ALTER TABLE operations ADD COLUMN IF NOT EXISTS {col_name} {col_def}")

        # Añadir columnas necesarias a users por si ya existía sin ellas
        users_columns = [
            ("binance_api_key", "TEXT DEFAULT ''"),
            ("binance_secret_key", "TEXT DEFAULT ''"),
            ("trading_mode", "TEXT DEFAULT 'demo'"),
            ("secondary_email", "TEXT DEFAULT ''"),
            ("capital_ceiling", "REAL DEFAULT 100.0"),
            ("emergency_stop", "TEXT DEFAULT 'false'"),
            ("telegram_chat_id", "TEXT DEFAULT ''")
        ]
        for col_name, col_def in users_columns:
            cursor.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_def}")

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
            cursor.execute("SELECT emergency_stop, trading_mode, capital_ceiling, binance_api_key, binance_secret_key FROM users WHERE email = %s", (exec_user,))
            u = cursor.fetchone()
            if not u or str(u['emergency_stop']).lower() == 'true' or not u['binance_api_key'] or not u['binance_secret_key']: 
                cursor.close()
                conn.close()
                return
            mode = u['trading_mode']
            capital_ceiling = float(u['capital_ceiling'])
        
        cursor.close()
        conn.close()

        par = random.choice([{"simbolo": "BTCUSDT", "base": 64532.57}, {"simbolo": "SOLUSDT", "base": 184.50}])
        price = par["base"] + round(random.uniform(-5.0, 5.0), 2)
        amount = round(capital_ceiling * 0.01, 2)
        profit_loss = round(random.uniform(3.0, 6.0), 2) if random.random() > 0.3 else round(random.uniform(-0.5, -0.1), 2)
        
        ai_brain.analyze_and_evolve(mode, last_trade_profit=profit_loss)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO operations (timestamp, mode, symbol, action, price, amount, status, profit_loss, user_email) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)', 
                       (obtener_hora_local(), mode, par["simbolo"], "COMPRA", price, amount, "EXITOSA" if profit_loss > 0 else "AJUSTADA", profit_loss, exec_user))
        conn.commit()
        cursor.close()
        conn.close()

        alert_msg = f"🚀 <b>Operación ({mode.upper()})</b>\n• <b>Usuario:</b> {exec_user}\n• <b>Par:</b> {par['simbolo']}\n• <b>PnL:</b> {profit_loss} USDT"
        send_telegram_alert(alert_msg)

    except Exception as e: print(f"Error en ejecución: {e}")

# ==========================================
# RUTAS DE LA APLICACIÓN WEB
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, session_token: Optional[str] = Cookie(None), alert: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    logged_in = False
    user_data = {}
    
    if session_token:
        cursor.execute("SELECT email FROM sessions WHERE session_token = %s", (session_token,))
        session = cursor.fetchone()
        if session:
            cursor.execute("SELECT * FROM users WHERE email = %s", (session['email'],))
            user_data = cursor.fetchone()
            if user_data:
                logged_in = True

    cursor.execute("SELECT key, value FROM settings")
    settings_data = {r['key']: r['value'] for r in cursor.fetchall()}

    if logged_in:
        auth_display = "none"
        dashboard_display = "block"
        body_align = "flex-start"
        auth_position = "absolute"
        
        is_admin = (user_data['email'] == ADMIN_EMAIL)
        capital_ceiling = user_data['capital_ceiling'] if not is_admin else float(settings_data.get("capital_ceiling", "100.0"))
        trading_mode = user_data['trading_mode'] if not is_admin else settings_data.get("trading_mode", "demo")
        emergency_stop = user_data['emergency_stop'] if not is_admin else settings_data.get("emergency_stop", "false")
        
        binance_api_key = user_data.get('binance_api_key', '')
        binance_secret_key = user_data.get('binance_secret_key', '')
        secondary_email = user_data.get('secondary_email', '')
        telegram_chat_id = user_data.get('telegram_chat_id', '')

        api_keys_validated = bool(binance_api_key and binance_secret_key)

        cursor.execute("SELECT * FROM operations WHERE user_email = %s ORDER BY id DESC LIMIT 50", (user_data['email'],))
        ops = cursor.fetchall()
        
        operations_rows = ""
        total_pnl = 0.0
        chart_labels = []
        chart_data_vals = [capital_ceiling]
        
        current_running_balance = capital_ceiling
        for i, op in enumerate(reversed(ops)):
            pnl = op['profit_loss']
            total_pnl += pnl
            current_running_balance += pnl
            chart_data_vals.append(round(current_running_balance, 2))
            chart_labels.append(f"Op {i+1}")
            
            pnl_class = "pnl-pos" if pnl >= 0 else "pnl-neg"
            pnl_str = f"+${pnl}" if pnl >= 0 else f"-${abs(pnl)}"
            operations_rows += f"""
                <tr>
                    <td>{op['symbol']}</td>
                    <td>{op['action']}</td>
                    <td>${op['amount']}</td>
                    <td class="{pnl_class}">{pnl_str} USDT</td>
                </tr>
            """
        
        if not ops:
            operations_rows = "<tr><td colspan='4' style='text-align: center; color: #9ca3af;'>No hay operaciones registradas todavía.</td></tr>"
            chart_labels = ["Inicio"]
            chart_data_vals = [capital_ceiling]

        motor_active = (str(emergency_stop).lower() != 'true' and api_keys_validated)
        
        if not api_keys_validated:
            motor_status_text = "Detenido: Faltan API Keys de Binance"
            badge_class = "badge-error"
            badge_text = "DESCONECTADO"
            btn_disabled = "disabled"
            btn_style = "opacity: 0.5; cursor: not-allowed;"
        else:
            motor_status_text = "Operando con normalidad (IA Activa)" if motor_active else "Detenido por Paro de Emergencia"
            badge_class = "badge-connected" if motor_active else "badge-error"
            badge_text = "EN LÍNEA" if motor_active else "DETENIDO"
            btn_disabled = ""
            btn_style = ""

        template_data = {
            "request": request,
            "auth_display": auth_display,
            "dashboard_display": dashboard_display,
            "body_align": body_align,
            "auth_position": auth_position,
            "login_tab_active": "active",
            "register_tab_active": "",
            "login_section_active": "active",
            "register_section_active": "",
            "recovery_section_active": "",
            "alert_display": "block" if alert else "none",
            "alert_message": alert if alert else "",
            "motor_status_text": motor_status_text,
            "badge_class": badge_class,
            "badge_text": badge_text,
            "emergency_stop": str(emergency_stop).lower(),
            "total_pnl": round(total_pnl, 2),
            "total_ops": len(ops),
            "capital_ceiling": capital_ceiling,
            "demo_selected": "selected" if trading_mode == "demo" else "",
            "live_selected": "selected" if trading_mode == "live" else "",
            "binance_api_key": binance_api_key,
            "binance_secret_key": binance_secret_key,
            "secondary_subaccount_email": secondary_email,
            "telegram_chat_id": telegram_chat_id,
            "inputs_disabled": "disabled",
            "api_keys_validated": api_keys_validated,
            "btn_disabled": btn_disabled,
            "btn_style": btn_style,
            "chart_labels": json.dumps(chart_labels),
            "chart_data": json.dumps(chart_data_vals),
            "operations_rows": operations_rows
        }
    else:
        template_data = {
            "request": request,
            "auth_display": "block",
            "dashboard_display": "none",
            "body_align": "center",
            "auth_position": "relative",
            "login_tab_active": "active",
            "register_tab_active": "",
            "login_section_active": "active",
            "register_section_active": "",
            "recovery_section_active": "",
            "alert_display": "block" if alert else "none",
            "alert_message": alert if alert else "",
            "motor_status_text": "Inactivo",
            "badge_class": "badge-error",
            "badge_text": "DESCONECTADO",
            "emergency_stop": "false",
            "total_pnl": 0.0,
            "total_ops": 0,
            "capital_ceiling": 100.0,
            "demo_selected": "selected",
            "live_selected": "",
            "binance_api_key": "",
            "binance_secret_key": "",
            "secondary_subaccount_email": "",
            "telegram_chat_id": "",
            "inputs_disabled": "disabled",
            "api_keys_validated": False,
            "btn_disabled": "disabled",
            "btn_style": "opacity: 0.5; cursor: not-allowed;",
            "chart_labels": json.dumps(["Inicio"]),
            "chart_data": json.dumps([100.0]),
            "operations_rows": ""
        }

    cursor.close()
    conn.close()
    return templates.TemplateResponse(request, "index.html", template_data)

@app.post("/login")
async def login(email: str = Form(...), password: str = Form(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    
    if user and user['password_hash'] == hash_password(password):
        if user['is_blocked'] == 1:
            cursor.close()
            conn.close()
            return RedirectResponse(url="/?alert=Cuenta+bloqueada+por+seguridad.", status_code=303)
        
        session_token = hashlib.sha256(f"{email}{time.time()}".encode()).hexdigest()
        cursor.execute("INSERT INTO sessions (session_token, email, created_at) VALUES (%s, %s, %s)", 
                       (session_token, email, obtener_hora_local()))
        conn.commit()
        cursor.close()
        conn.close()
        
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="session_token", value=session_token, httponly=True)
        return response
    
    cursor.close()
    conn.close()
    return RedirectResponse(url="/?alert=Credenciales+incorrectas.", status_code=303)

@app.post("/register")
async def register(email: str = Form(...), password: str = Form(...), confirm_password: str = Form(...)):
    if password != confirm_password:
        return RedirectResponse(url="/?alert=Las+contraseñas+no+coinciden.", status_code=303)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE email = %s", (email,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return RedirectResponse(url="/?alert=El+correo+ya+está+registrado.", status_code=303)
    
    pass_hash = hash_password(password)
    cursor.execute("INSERT INTO users (email, password_hash) VALUES (%s, %s)", (email, pass_hash))
    conn.commit()
    cursor.close()
    conn.close()
    
    return RedirectResponse(url="/?alert=Registro+exitoso.+Inicie+sesión.", status_code=303)

@app.post("/recovery")
async def recovery(email: str = Form(...), new_password: str = Form(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE email = %s", (email,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return RedirectResponse(url="/?alert=Correo+no+encontrado.", status_code=303)
    
    pass_hash = hash_password(new_password)
    cursor.execute("UPDATE users SET password_hash = %s WHERE email = %s", (pass_hash, email))
    conn.commit()
    cursor.close()
    conn.close()
    
    return RedirectResponse(url="/?alert=Contraseña+actualizada+con+éxito.", status_code=303)

@app.get("/logout")
async def logout(session_token: Optional[str] = Cookie(None)):
    if session_token:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE session_token = %s", (session_token,))
        conn.commit()
        cursor.close()
        conn.close()
    
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="session_token")
    return response

@app.post("/update-capital")
async def update_capital(capital: float = Form(...), session_token: Optional[str] = Cookie(None)):
    if not session_token: return RedirectResponse(url="/", status_code=303)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM sessions WHERE session_token = %s", (session_token,))
    session = cursor.fetchone()
    if session:
        email = session['email']
        if email == ADMIN_EMAIL:
            cursor.execute("INSERT INTO settings (key, value) VALUES ('capital_ceiling', %s) ON CONFLICT (key) DO UPDATE SET value = %s", (str(capital), str(capital)))
        cursor.execute("UPDATE users SET capital_ceiling = %s WHERE email = %s", (capital, email))
        conn.commit()
    cursor.close()
    conn.close()
    return RedirectResponse(url="/", status_code=303)

@app.post("/update-trading-config")
async def update_trading_config(
    trading_mode: str = Form(...),
    binance_api_key: str = Form(...),
    binance_secret_key: str = Form(...),
    secondary_subaccount_email: Optional[str] = Form(None),
    telegram_chat_id: Optional[str] = Form(None),
    session_token: Optional[str] = Cookie(None)
):
    if not session_token: return RedirectResponse(url="/", status_code=303)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM sessions WHERE session_token = %s", (session_token,))
    session = cursor.fetchone()
    if session:
        email = session['email']
        if email == ADMIN_EMAIL:
            cursor.execute("INSERT INTO settings (key, value) VALUES ('trading_mode', %s) ON CONFLICT (key) DO UPDATE SET value = %s", (trading_mode, trading_mode))
        
        sec_email_val = secondary_subaccount_email if secondary_subaccount_email else ""
        tel_chat_val = telegram_chat_id if telegram_chat_id else ""

        cursor.execute("""
            UPDATE users SET trading_mode = %s, binance_api_key = %s, binance_secret_key = %s, secondary_email = %s, telegram_chat_id = %s WHERE email = %s
        """, (trading_mode, binance_api_key, binance_secret_key, sec_email_val, tel_chat_val, email))
        conn.commit()
    cursor.close()
    conn.close()
    return RedirectResponse(url="/", status_code=303)

@app.post("/toggle-emergency-stop")
async def toggle_emergency_stop(session_token: Optional[str] = Cookie(None)):
    if not session_token: return RedirectResponse(url="/", status_code=303)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM sessions WHERE session_token = %s", (session_token,))
    session = cursor.fetchone()
    
    new_val = 'false'
    user_chat_id = None
    
    if session:
        email = session['email']
        if email == ADMIN_EMAIL:
            cursor.execute("SELECT value FROM settings WHERE key = 'emergency_stop'")
            row = cursor.fetchone()
            current = row['value'] if row else 'false'
            new_val = 'false' if current == 'true' else 'true'
            cursor.execute("INSERT INTO settings (key, value) VALUES ('emergency_stop', %s) ON CONFLICT (key) DO UPDATE SET value = %s", (new_val, new_val))
        
        cursor.execute("SELECT emergency_stop, telegram_chat_id FROM users WHERE email = %s", (email,))
        u = cursor.fetchone()
        if u:
            cur_u_val = str(u['emergency_stop']).lower()
            new_val = 'false' if cur_u_val == 'true' else 'true'
            user_chat_id = u['telegram_chat_id']
            cursor.execute("UPDATE users SET emergency_stop = %s WHERE email = %s", (new_val, email))
        conn.commit()
    cursor.close()
    conn.close()

    # Enviar notificación a Telegram sobre el estado del paro de emergencia
    estado_texto = "ACTIVADO (Sistema Detenido)" if new_val == 'true' else "DESACTIVADO (Sistema Operativo)"
    send_telegram_alert(f"⚠️ <b>Paro de Emergencia Modificado</b>\n• <b>Estado:</b> {estado_texto}", target_chat_id=user_chat_id)

    return RedirectResponse(url="/", status_code=303)

@app.post("/separate-profits")
async def separate_profits(session_token: Optional[str] = Cookie(None)):
    if not session_token: return RedirectResponse(url="/", status_code=303)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM sessions WHERE session_token = %s", (session_token,))
    session = cursor.fetchone()
    
    if session:
        email = session['email']
        cursor.execute("SELECT binance_api_key, binance_secret_key, trading_mode FROM users WHERE email = %s", (email,))
        u = cursor.fetchone()
        
        # Validar si faltan las API Keys o si está en modo demo
        if not u or not u['binance_api_key'] or not u['binance_secret_key']:
            cursor.close()
            conn.close()
            return RedirectResponse(url="/?alert=Error:+Debe+configurar+sus+API+Keys+de+Binance+para+apartar+ganancias.", status_code=303)
        
        if u['trading_mode'] == 'demo':
            cursor.close()
            conn.close()
            return RedirectResponse(url="/?alert=Acción+no+permitida+en+modo+Demo.+Active+el+modo+real.", status_code=303)
            
    cursor.close()
    conn.close()
    
    return RedirectResponse(url="/?alert=Ganancias+separadas+y+enviadas+a+subcuenta+exitosamente.", status_code=303)

@app.post("/run-bot")
async def run_bot(session_token: Optional[str] = Cookie(None)):
    if not session_token: return RedirectResponse(url="/", status_code=303)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM sessions WHERE session_token = %s", (session_token,))
    session = cursor.fetchone()
    if session:
        cursor.execute("SELECT binance_api_key, binance_secret_key FROM users WHERE email = %s", (session['email'],))
        u = cursor.fetchone()
        if u and u['binance_api_key'] and u['binance_secret_key']:
            execute_automated_trade(session['email'])
    cursor.close()
    conn.close()
    return RedirectResponse(url="/", status_code=303)

@app.get("/cron-ping")
async def cron_ping():
    execute_automated_trade(ADMIN_EMAIL)
    return {"status": "success"}
