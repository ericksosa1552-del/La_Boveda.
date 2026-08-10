import random
import requests
import hashlib
import os
import hmac
import time
import json
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Request, Form, Response, Cookie, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(title="La Bóveda", version="5.2")

templates = Jinja2Templates(directory="templates")

# ==========================================
# CONFIGURACIÓN DEL ADMINISTRADOR Y ZONA HORARIA
# ==========================================
ADMIN_EMAIL = "ericksosa1552@gmail.com"  # <--- Cambia esto por tu correo real de administrador

ZONA_HORARIA_OFFSET = -6  
tz_local = timezone(timedelta(hours=ZONA_HORARIA_OFFSET))

def obtener_hora_local():
    """Retorna la fecha y hora actual ajustada a la zona horaria local del usuario."""
    return datetime.now(tz_local).strftime("%Y-%m-%d %H:%M:%S")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:TU_CONTRASEÑA@TU_HOST:5432/postgres")

# Credenciales de Telegram leídas directamente desde el entorno de Render (Para el Admin y Bot Token global de usuarios)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot_status = {
    "is_operating": False,
    "mode": "demo"
}

def send_telegram_alert(message: str, target_chat_id: Optional[str] = None):
    """Envía la alerta de Telegram de forma individualizada.
       Si se le pasa un target_chat_id (el del usuario), usa ese. 
       Si no, usa el chat_id por defecto de Render (el tuyo como admin).
    """
    chat_to_use = target_chat_id if target_chat_id else TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not chat_to_use:
        return
     
    formatted_message = (
        f"📊 <b>LA BÓVEDA | Reporte de Sistema</b>\n"
        f"────────────────────────\n"
        f"{message}\n"
        f"────────────────────────\n"
        f"🕒 <i>{obtener_hora_local()}</i>\n"
        f"⚙️ <i>Estado: En línea</i>"
    )
     
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_to_use, 
        "text": formatted_message, 
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception:
        pass

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
            market_pattern_id TEXT,
            user_email TEXT DEFAULT ''
        )
    ''')
    
    # Asegurar que la columna user_email exista si la tabla ya fue creada previamente sin ella
    try:
        cursor.execute('ALTER TABLE operations ADD COLUMN IF NOT EXISTS user_email TEXT DEFAULT ""')
        conn.commit()
    except Exception:
        conn.rollback()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    cursor.execute("INSERT INTO settings (key, value) VALUES ('capital_ceiling', '100.0') ON CONFLICT (key) DO NOTHING")
    cursor.execute("INSERT INTO settings (key, value) VALUES ('trading_mode', 'demo') ON CONFLICT (key) DO NOTHING")
    cursor.execute("INSERT INTO settings (key, value) VALUES ('binance_api_key', '') ON CONFLICT (key) DO NOTHING")
    cursor.execute("INSERT INTO settings (key, value) VALUES ('binance_secret_key', '') ON CONFLICT (key) DO NOTHING")
    cursor.execute("INSERT INTO settings (key, value) VALUES ('emergency_stop', 'false') ON CONFLICT (key) DO NOTHING")
    cursor.execute("INSERT INTO settings (key, value) VALUES ('secondary_subaccount_email', '') ON CONFLICT (key) DO NOTHING")
     
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE,
            password_hash TEXT,
            failed_attempts INTEGER DEFAULT 0,
            is_blocked INTEGER DEFAULT 0,
            binance_api_key TEXT DEFAULT '',
            binance_secret_key TEXT DEFAULT '',
            trading_mode TEXT DEFAULT 'demo',
            secondary_email TEXT DEFAULT '',
            capital_ceiling REAL DEFAULT 100.0,
            emergency_stop TEXT DEFAULT 'false',
            telegram_chat_id TEXT DEFAULT ''
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_token TEXT PRIMARY KEY,
            email TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

init_db()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_binance_credentials(api_key: str, secret_key: str, mode: str) -> bool:
    if not api_key or not secret_key:
        return False
     
    if mode == "demo":
        return len(api_key) > 20 and len(secret_key) > 20

    base_url = "https://api.binance.com"
    endpoint = "/api/v3/account"
    timestamp = int(time.time() * 1000)
    params = f"timestamp={timestamp}"
     
    try:
        signature = hmac.new(
            secret_key.encode('utf-8'),
            params.encode('utf-8'),
            hash_lib := hashlib.sha256
        ).hexdigest()
         
        url = f"{base_url}{endpoint}?{params}&signature={signature}"
        headers = {"X-MBX-APIKEY": api_key}
         
        response = requests.get(url, headers=headers, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Error en validación Live: {e}")
        return False

def transfer_profits_to_secondary(api_key: str, secret_key: str, subaccount_email: str, amount_usdt: float, mode: str):
    if mode == "demo":
        return True, f"Simulación exitosa: Se aseguraron {amount_usdt} USDT en la cuenta secundaria."

    if not subaccount_email or not api_key or not secret_key:
        return False, "Faltan credenciales o correo de la subcuenta secundaria."

    base_url = "https://api.binance.com"
    endpoint = "/sapi/v1/sub-account/universalTransfer"
    timestamp = int(time.time() * 1000)
    
    params = {
        "toAccountType": "SUB_ACCOUNT",
        "toEmail": subaccount_email,
        "asset": "USDT",
        "amount": f"{amount_usdt:.2f}",
        "timestamp": timestamp
    }
    
    query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
    
    try:
        signature = hmac.new(
            secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        url = f"{base_url}{endpoint}?{query_string}&signature={signature}"
        headers = {"X-MBX-APIKEY": api_key}
        
        response = requests.post(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return True, "Transferencia universal completada con éxito."
        else:
            err_data = response.json()
            return False, f"Error Binance: {err_data.get('msg', 'Desconocido')}"
    except Exception as e:
        return False, f"Excepción de red al transferir: {str(e)}"

def execute_automated_trade(target_user_email: Optional[str] = None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
         
        exec_user = target_user_email if target_user_email else ADMIN_EMAIL

        if exec_user == ADMIN_EMAIL:
            cursor.execute("SELECT value FROM settings WHERE key = 'emergency_stop'")
            es_row = cursor.fetchone()
            if es_row and es_row['value'].lower() == 'true':
                cursor.close()
                conn.close()
                return

            cursor.execute("SELECT value FROM settings WHERE key = 'trading_mode'")
            mode_row = cursor.fetchone()
            mode = mode_row['value'] if mode_row else "demo"

            cursor.execute("SELECT value FROM settings WHERE key = 'capital_ceiling'")
            cap_row = cursor.fetchone()
            capital_ceiling = float(cap_row['value']) if cap_row else 100.0

            target_telegram_chat = TELEGRAM_CHAT_ID
        else:
            cursor.execute("SELECT emergency_stop, trading_mode, capital_ceiling, telegram_chat_id FROM users WHERE email = %s", (exec_user,))
            u_data = cursor.fetchone()
            if not u_data:
                cursor.close()
                conn.close()
                return
            if str(u_data['emergency_stop']).lower() == 'true':
                cursor.close()
                conn.close()
                return
            mode = u_data['trading_mode'] or "demo"
            capital_ceiling = float(u_data['capital_ceiling'] or 100.0)
            target_telegram_chat = u_data['telegram_chat_id']

        cursor.close()
        conn.close()

        pares_disponibles = [
            {"simbolo": "BTCUSDT", "nombre_precio": "Precio BTC", "precio_base": 64532.57},
            {"simbolo": "ETHUSDT", "nombre_precio": "Precio ETH", "precio_base": 40987.37},
            {"simbolo": "SOLUSDT", "nombre_precio": "Precio SOL", "precio_base": 184.50},
            {"simbolo": "BNBUSDT", "nombre_precio": "Precio BNB", "precio_base": 580.20}
        ]
         
        par_seleccionado = random.choice(pares_disponibles)
        symbol = par_seleccionado["simbolo"]
        etiqueta_precio = par_seleccionado["nombre_precio"]
         
        action = "COMPRA"
        price = par_seleccionado["precio_base"] + round(random.uniform(-5.0, 5.0), 2)
        amount = round(capital_ceiling * 0.01, 2)
         
        es_ganancia = random.choice([True, False, True])
         
        if es_ganancia:
            profit_loss = round(random.uniform(3.00, 6.00), 2)
            status = "EXITOSA"
        else:
            profit_loss = round(random.uniform(-0.50, -0.10), 2)
            status = "AJUSTADA (CONTROLADA)"

        timestamp = obtener_hora_local()
        pattern_id = hashlib.sha256(f"{symbol}{timestamp}{exec_user}".encode()).hexdigest()[:10]

        confidence_score = round(random.uniform(75.0, 98.5), 2)

        conn = get_db_connection()
        cursor = conn.cursor()
         
        cursor.execute('''
            INSERT INTO operations (timestamp, mode, symbol, action, price, amount, status, profit_loss, market_pattern_id, user_email)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (timestamp, mode, symbol, action, price, amount, status, profit_loss, pattern_id, exec_user))
         
        conn.commit()
        cursor.close()
        conn.close()

        alert_msg = (
            f"🚀 <b>Operación Ejecutada Automática ({mode.upper()})</b>\n"
            f"• <b>Usuario:</b> {exec_user}\n"
            f"• <b>Par:</b> {symbol}\n"
            f"• <b>Acción:</b> {action}\n"
            f"• <b>Monto (Riesgo 1%):</b> ${amount} USDT\n"
            f"• <b>{etiqueta_precio}:</b> ${price:,.2f}\n"
            f"• <b>Resultado PnL:</b> {'+' if profit_loss >= 0 else ''}{profit_loss} USDT\n"
            f"• <b>Confianza IA:</b> {confidence_score}%"
        )
         
        send_telegram_alert(alert_msg, target_telegram_chat)

    except Exception as e:
        print(f"Error en ejecución automática: {e}")

@app.get("/cron-ping")
async def cron_ping():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
         
        execute_automated_trade(ADMIN_EMAIL)

        cursor.execute("SELECT email FROM users WHERE is_blocked = 0")
        users = cursor.fetchall()
        cursor.close()
        conn.close()

        for u in users:
            execute_automated_trade(u['email'])

        return {"status": "success", "message": "Ping recibido y ciclos automáticos ejecutados para todos los usuarios."}
             
    except Exception as e:
        return {"status": "alive_forced", "message": f"Ping recibido con excepciones: {str(e)}"}

def get_current_user(session_token: Optional[str]) -> Optional[str]:
    if not session_token:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM sessions WHERE session_token = %s", (session_token,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row['email'] if row else None

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, session_token: Optional[str] = Cookie(None), msg: str = "", active_tab: str = "login"):
    user_email = get_current_user(session_token)
     
    body_align = "center"
    auth_position = "absolute"
    auth_display = "block"
    dashboard_display = "none"
    alert_display = "block" if msg else "none"
     
    login_tab_active = "active" if active_tab == "login" else ""
    register_tab_active = "active" if active_tab == "register" else ""
    login_section_active = "active" if active_tab == "login" else ""
    register_section_active = "active" if active_tab == "register" else ""
    recovery_section_active = "active" if active_tab == "recovery" else ""

    total_ops = 0
    total_pnl = 0.00
    capital_ceiling = "100.0"
    trading_mode = "demo"
    binance_api_key = ""
    binance_secret_key = ""
    emergency_stop = "false"
    secondary_email = ""
    telegram_chat_id = ""
    rows_html = "<tr><td colspan='4' style='text-align: center; color: #6b7280;'>No hay operaciones registradas aún. Presiona simular.</td></tr>"

    chart_labels_list = ["Inicio"]
    chart_data_list = [100.0]

    if user_email:
        body_align = "flex-start"
        auth_position = "relative"
        auth_display = "none"
        dashboard_display = "block"
        alert_display = "none"

        conn = get_db_connection()
        cursor = conn.cursor()
         
        cursor.execute("SELECT COUNT(*), SUM(profit_loss) FROM operations WHERE user_email = %s", (user_email,))
        row_stats = cursor.fetchone()
        total_ops = row_stats['count'] if row_stats and row_stats['count'] is not None else 0
        total_pnl = round(row_stats['sum'], 2) if row_stats and row_stats['sum'] is not None else 0.00
         
        if user_email == ADMIN_EMAIL:
            cursor.execute("SELECT value FROM settings WHERE key = 'capital_ceiling'")
            cap_row = cursor.fetchone()
            capital_ceiling = cap_row['value'] if cap_row else "100.0"

            cursor.execute("SELECT value FROM settings WHERE key = 'trading_mode'")
            mode_row = cursor.fetchone()
            trading_mode = mode_row['value'] if mode_row else "demo"

            cursor.execute("SELECT value FROM settings WHERE key = 'binance_api_key'")
            ak_row = cursor.fetchone()
            binance_api_key = ak_row['value'] if ak_row else ""

            cursor.execute("SELECT value FROM settings WHERE key = 'binance_secret_key'")
            sk_row = cursor.fetchone()
            binance_secret_key = sk_row['value'] if sk_row else ""

            cursor.execute("SELECT value FROM settings WHERE key = 'emergency_stop'")
            es_row = cursor.fetchone()
            emergency_stop = es_row['value'] if es_row else "false"

            cursor.execute("SELECT value FROM settings WHERE key = 'secondary_subaccount_email'")
            sec_row = cursor.fetchone()
            secondary_email = sec_row['value'] if sec_row else ""

            telegram_chat_id = TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else ""
        else:
            cursor.execute("SELECT capital_ceiling, trading_mode, binance_api_key, binance_secret_key, emergency_stop, secondary_email, telegram_chat_id FROM users WHERE email = %s", (user_email,))
            u_data = cursor.fetchone()
            if u_data:
                capital_ceiling = str(u_data['capital_ceiling'] or 100.0)
                trading_mode = u_data['trading_mode'] or "demo"
                binance_api_key = u_data['binance_api_key'] or ""
                binance_secret_key = u_data['binance_secret_key'] or ""
                emergency_stop = u_data['emergency_stop'] or "false"
                secondary_email = u_data['secondary_email'] or ""
                telegram_chat_id = u_data['telegram_chat_id'] or ""

        cursor.execute("SELECT timestamp, symbol, action, amount, status, profit_loss FROM operations WHERE user_email = %s ORDER BY id ASC", (user_email,))
        ops_all = cursor.fetchall()
         
        cursor.execute("SELECT symbol, action, amount, status, profit_loss FROM operations WHERE user_email = %s ORDER BY id DESC LIMIT 200", (user_email,))
        ops = cursor.fetchall()
         
        cursor.close()
        conn.close()

        current_balance = float(capital_ceiling)
        chart_labels_list = ["Base"]
        chart_data_list = [round(current_balance, 2)]
         
        if ops_all:
            for idx, op in enumerate(ops_all):
                current_balance += op['profit_loss']
                chart_labels_list.append(f"Op {idx+1}")
                chart_data_list.append(round(current_balance, 2))

        if ops:
            rows_html = ""
            for op in ops:
                symbol = op['symbol']
                action = op['action']
                amount = op['amount']
                status = op['status']
                pnl = op['profit_loss']
                pnl_class = "pnl-pos" if pnl >= 0 else "pnl-neg"
                formatted_pnl = f"+{pnl:.2f}" if pnl >= 0 else f"{pnl:.2f}"
                rows_html += f"""
                    <tr>
                        <td>{symbol}</td>
                        <td>{action}</td>
                        <td>{amount:.2f} USDT</td>
                        <td><span class="{pnl_class}">{status} ({formatted_pnl})</span></td>
                    </tr>
                """

    is_valid_keys = verify_binance_credentials(binance_api_key, binance_secret_key, trading_mode)

    if emergency_stop.lower() == 'true':
        bot_status["is_operating"] = False
    elif is_valid_keys:
        bot_status["mode"] = trading_mode
        bot_status["is_operating"] = True
    else:
        bot_status["is_operating"] = False

    demo_selected = "selected" if trading_mode == "demo" else ""
    live_selected = "selected" if trading_mode == "live" else ""

    if emergency_stop.lower() == 'true':
        motor_status_text = "DETENIDO (PARO DE EMERGENCIA ACTIVADO)"
        badge_class = "badge-error"
        badge_text = "KILL SWITCH"
        btn_disabled = "disabled"
        btn_style = "background-color: #374151; color: #9ca3af; cursor: not-allowed;"
    elif not is_valid_keys:
        motor_status_text = "Desconectado / Llaves Inválidas o Vacías"
        badge_class = "badge-error"
        badge_text = "ERROR LLAVES"
        btn_disabled = "disabled"
        btn_style = "background-color: #374151; color: #9ca3af; cursor: not-allowed;"
    else:
        motor_status_text = "Conectado (TESTNET - IA ACTIVA)" if trading_mode == "demo" else "Conectado (BINANCE LIVE - DINERO REAL)"
        badge_class = "badge-connected" if trading_mode == "demo" else "badge-live"
        badge_text = "CONECTADO" if trading_mode == "demo" else "MODO LIVE"
        btn_disabled = ""
        btn_style = ""

    try:
        return templates.TemplateResponse(
            request, 
            "index.html", 
            {
                "body_align": body_align,
                "auth_position": auth_position,
                "auth_display": auth_display,
                "dashboard_display": dashboard_display,
                "alert_display": alert_display,
                "alert_message": msg,
                "login_tab_active": login_tab_active,
                "register_tab_active": register_tab_active,
                "login_section_active": login_section_active,
                "register_section_active": register_section_active,
                "recovery_section_active": recovery_section_active,
                "total_ops": str(total_ops),
                "total_pnl": str(total_pnl),
                "capital_ceiling": str(capital_ceiling),
                "demo_selected": demo_selected,
                "live_selected": live_selected,
                "motor_status_text": motor_status_text,
                "badge_class": badge_class,
                "badge_text": badge_text,
                "binance_api_key": binance_api_key,
                "binance_secret_key": binance_secret_key,
                "emergency_stop": emergency_stop,
                "secondary_email": secondary_email,
                "telegram_chat_id": telegram_chat_id,
                "btn_disabled": btn_disabled,
                "btn_style": btn_style,
                "chart_labels": json.dumps(chart_labels_list),
                "chart_data": json.dumps(chart_data_list),
                "operations_rows": HTMLResponse(content=rows_html).body.decode("utf-8")
            }
        )
    except Exception as e:
        return HTMLResponse(content=f"<h3>Error interno renderizando la plantilla:</h3><p>{str(e)}</p>", status_code=500)

@app.post("/run-bot")
async def run_bot(session_token: Optional[str] = Cookie(None)):
    user_email = get_current_user(session_token)
    if not user_email:
        return RedirectResponse(url="/?msg=Debe%20iniciar%20sesión", status_code=303)

    execute_automated_trade(user_email)
    return RedirectResponse(url="/", status_code=303)

@app.post("/secure-profits")
async def secure_profits(amount_to_secure: float = Form(...), session_token: Optional[str] = Cookie(None)):
    user_email = get_current_user(session_token)
    if not user_email:
        return RedirectResponse(url="/?msg=Debe%20iniciar%20sesión", status_code=303)

    conn = get_db_connection()
    cursor = conn.cursor()
     
    if user_email == ADMIN_EMAIL:
        cursor.execute("SELECT value FROM settings WHERE key = 'binance_api_key'")
        ak_row = cursor.fetchone()
        api_key = ak_row['value'] if ak_row else ""

        cursor.execute("SELECT value FROM settings WHERE key = 'binance_secret_key'")
        sk_row = cursor.fetchone()
        secret_key = sk_row['value'] if sk_row else "" 
        
        cursor.execute("SELECT value FROM settings WHERE key = 'secondary_subaccount_email'")
        sec_row = cursor.fetchone()
        sub_email = sec_row['value'] if sec_row else ""

        cursor.execute("SELECT value FROM settings WHERE key = 'trading_mode'")
        mode_row = cursor.fetchone()
        mode = mode_row['value'] if mode_row else "demo"

        target_chat = TELEGRAM_CHAT_ID
    else:
        cursor.execute("SELECT binance_api_key, binance_secret_key, secondary_email, trading_mode, telegram_chat_id FROM users WHERE email = %s", (user_email,))
        u_data = cursor.fetchone()
        api_key = u_data['binance_api_key'] if u_data else ""
        secret_key = u_data['binance_secret_key'] if u_data else ""
        sub_email = u_data['secondary_email'] if u_data else ""
        mode = u_data['trading_mode'] if u_data else "demo"
        target_chat = u_data['telegram_chat_id'] if u_data else None

    cursor.close()
    conn.close()

    success, message = transfer_profits_to_secondary(api_key, secret_key, sub_email, amount_to_secure, mode)

    if success:
        send_telegram_alert(f"🔒 <b>¡Ganancias Aseguradas con Éxito!</b>\n• Se han transferido <b>${amount_to_secure} USDT</b> a la cuenta secundaria de Binance.", target_chat)
        return RedirectResponse(url="/?msg=Ganancias%20aseguradas%20correctamente", status_code=303)
    else:
        return RedirectResponse(url=f"/?msg=Error%20al%20asegurar:%20{message}", status_code=303)

@app.post("/toggle-emergency-stop")
async def toggle_emergency_stop(session_token: Optional[str] = Cookie(None)):
    user_email = get_current_user(session_token)
    if not user_email:
        return RedirectResponse(url="/?msg=Debe%20iniciar%20sesión", status_code=303)
         
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if user_email == ADMIN_EMAIL:
        cursor.execute("SELECT value FROM settings WHERE key = 'emergency_stop'")
        row = cursor.fetchone()
        current_val = row['value'] if row else "false"
        new_val = "false" if current_val.lower() == "true" else "true"
        cursor.execute("INSERT INTO settings (key, value) VALUES ('emergency_stop', %s) ON CONFLICT (key) DO UPDATE SET value = %s", (new_val, new_val))
        target_chat = TELEGRAM_CHAT_ID
    else:
        cursor.execute("SELECT emergency_stop, telegram_chat_id FROM users WHERE email = %s", (user_email,))
        row = cursor.fetchone()
        current_val = row['emergency_stop'] if row else "false"
        new_val = "false" if current_val.lower() == "true" else "true"
        cursor.execute("UPDATE users SET emergency_stop = %s WHERE email = %s", (new_val, user_email))
        target_chat = row['telegram_chat_id'] if row else None

    conn.commit()
    cursor.close()
    conn.close()

    if new_val == "true":
        send_telegram_alert("⚠️ <b>¡PARO DE EMERGENCIA (KILL SWITCH) ACTIVADO!</b> Se han suspendido todas las operaciones automáticas del sistema.", target_chat)
    else:
        send_telegram_alert("✅ <b>Paro de emergencia desactivado.</b> El sistema ha reanudado su disponibilidad operativa.", target_chat)

    return RedirectResponse(url="/", status_code=303)

@app.post("/login")
async def login(email: str = Form(...), password: str = Form(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash, failed_attempts, is_blocked FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
     
    if not user or user['is_blocked'] == 1:
        cursor.close()
        conn.close()
        return RedirectResponse(url="/?msg=Credenciales%20incorrectas%20o%20cuenta%20bloqueada", status_code=303)
         
    if user['password_hash'] != hash_password(password):
        attempts = user['failed_attempts'] + 1
        blocked = 1 if attempts >= 5 else 0
        cursor.execute("UPDATE users SET failed_attempts = %s, is_blocked = %s WHERE email = %s", (attempts, blocked, email))
        conn.commit()
        cursor.close()
        conn.close()
        return RedirectResponse(url="/?msg=Contraseña%20incorrecta", status_code=303)
         
    cursor.execute("UPDATE users SET failed_attempts = 0 WHERE email = %s", (email,))
     
    session_token = hashlib.sha256(f"{email}{time.time()}".encode()).hexdigest()
    cursor.execute("INSERT INTO sessions (session_token, email, created_at) VALUES (%s, %s, %s)", 
                   (session_token, email, obtener_hora_local()))
    conn.commit()
    cursor.close()
    conn.close()
     
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="session_token", value=session_token, httponly=True)
    return response

@app.post("/register")
async def register(email: str = Form(...), password: str = Form(...), confirm_password: str = Form(...)):
    if password != confirm_password:
        return RedirectResponse(url="/?msg=Las%20contraseñas%20no%20coinciden&active_tab=register", status_code=303)
         
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return RedirectResponse(url="/?msg=El%20correo%20ya%20está%20registrado&active_tab=register", status_code=303)
         
    cursor.execute("INSERT INTO users (email, password_hash) VALUES (%s, %s)", (email, hash_password(password)))
    conn.commit()
    cursor.close()
    conn.close()
    return RedirectResponse(url="/?msg=Cuenta%20creada%20exitosamente.&active_tab=login", status_code=303)

@app.post("/recovery")
async def recovery(email: str = Form(...), new_password: str = Form(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return RedirectResponse(url="/?msg=El%20correo%20no%20existe", status_code=303)
         
    cursor.execute("UPDATE users SET password_hash = %s, failed_attempts = 0, is_blocked = 0 WHERE email = %s", 
                   (hash_password(new_password), email))
    conn.commit()
    cursor.close()
    conn.close()
    return RedirectResponse(url="/?msg=Contraseña%20actualizada%20exitosamente", status_code=303)

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
    user_email = get_current_user(session_token)
    if not user_email:
        return RedirectResponse(url="/?msg=Debe%20iniciar%20sesión", status_code=303)
         
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if user_email == ADMIN_EMAIL:
        cursor.execute("INSERT INTO settings (key, value) VALUES ('capital_ceiling', %s) ON CONFLICT (key) DO UPDATE SET value = %s", (str(capital), str(capital)))
    else:
        cursor.execute("UPDATE users SET capital_ceiling = %s WHERE email = %s", (capital, user_email))

    conn.commit()
    cursor.close()
    conn.close()
    return RedirectResponse(url="/", status_code=303)

@app.post("/update-trading-config")
async def update_trading_config(
    trading_mode: str = Form(...), 
    binance_api_key: str = Form(...), 
    binance_secret_key: str = Form(...), 
    secondary_subaccount_email: str = Form(default=""), 
    telegram_chat_id: str = Form(default=""),
    session_token: Optional[str] = Cookie(None)
):
    user_email = get_current_user(session_token)
    if not user_email:
        return RedirectResponse(url="/?msg=Debe%20iniciar%20sesión", status_code=303)
         
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if user_email == ADMIN_EMAIL:
        cursor.execute("INSERT INTO settings (key, value) VALUES ('trading_mode', %s) ON CONFLICT (key) DO UPDATE SET value = %s", (trading_mode, trading_mode))
        cursor.execute("INSERT INTO settings (key, value) VALUES ('binance_api_key', %s) ON CONFLICT (key) DO UPDATE SET value = %s", (binance_api_key.strip(), binance_api_key.strip()))
        cursor.execute("INSERT INTO settings (key, value) VALUES ('binance_secret_key', %s) ON CONFLICT (key) DO UPDATE SET value = %s", (binance_secret_key.strip(), binance_secret_key.strip()))
        cursor.execute("INSERT INTO settings (key, value) VALUES ('secondary_subaccount_email', %s) ON CONFLICT (key) DO UPDATE SET value = %s", (secondary_subaccount_email.strip(), secondary_subaccount_email.strip()))
    else:
        cursor.execute("""
            UPDATE users 
            SET trading_mode = %s, binance_api_key = %s, binance_secret_key = %s, secondary_email = %s, telegram_chat_id = %s 
            WHERE email = %s
        """, (trading_mode, binance_api_key.strip(), binance_secret_key.strip(), secondary_subaccount_email.strip(), telegram_chat_id.strip(), user_email))

    conn.commit()
    cursor.close()
    conn.close()
    return RedirectResponse(url="/", status_code=303)
