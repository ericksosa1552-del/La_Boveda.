import random
import requests
import hashlib
import os
import hmac
import time
from datetime import datetime
from fastapi import FastAPI, Request, Form, Response, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(title="La Bóveda", version="4.6")

# URL de conexión a Supabase (PostgreSQL) obtenida desde las variables de entorno de Render
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:TU_CONTRASEÑA@TU_HOST:5432/postgres")

# --- CREDENCIALES DE TELEGRAM SEGURAS (Vía Variables de Entorno) ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8536842251")

# --- ESTADO GLOBAL DE OPERACIÓN ---
bot_status = {
    "is_operating": False,
    "mode": "demo"
}

def send_telegram_alert(message: str):
    """
    Formato de notificación optimizado con diseño de bloques, separadores y énfasis visual[cite: 1].
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    
    # Formato visual tipo "Dashboard" en Telegram[cite: 1]
    formatted_message = (
        f"📊 <b>LA BÓVEDA | Reporte de Sistema</b>\n"
        f"────────────────────────\n"
        f"{message}\n"
        f"────────────────────────\n"
        f"🕒 <i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>\n"
        f"⚙️ <i>Estado: En línea</i>"
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": formatted_message, 
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception:
        pass

def send_ping(message: str):
    """Envía el ping o latido únicamente si el bot se encuentra operando activamente."""
    if bot_status["is_operating"]:
        msg = f"🟢 <b>Status Activo</b>\n{message}"
        send_telegram_alert(msg)

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
    cursor.execute("INSERT INTO settings (key, value) VALUES ('capital_ceiling', '100.0') ON CONFLICT (key) DO NOTHING")
    cursor.execute("INSERT INTO settings (key, value) VALUES ('trading_mode', 'demo') ON CONFLICT (key) DO NOTHING")
    cursor.execute("INSERT INTO settings (key, value) VALUES ('binance_api_key', '') ON CONFLICT (key) DO NOTHING")
    cursor.execute("INSERT INTO settings (key, value) VALUES ('binance_secret_key', '') ON CONFLICT (key) DO NOTHING")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_learning_memory (
            id SERIAL PRIMARY KEY,
            pattern_hash TEXT UNIQUE,
            success_count INTEGER,
            failure_count INTEGER,
            last_updated TEXT,
            weight_adjustment REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE,
            password_hash TEXT,
            failed_attempts INTEGER DEFAULT 0,
            is_blocked INTEGER DEFAULT 0
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
            hashlib.sha256
        ).hexdigest()
        
        url = f"{base_url}{endpoint}?{params}&signature={signature}"
        headers = {"X-MBX-APIKEY": api_key}
        
        response = requests.get(url, headers=headers, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Error en validación Live: {e}")
        return False

# --- ENDPOINT PARA EL PING EXTERNO DE CRON-JOB.ORG ---
@app.get("/cron-ping")
async def cron_ping():
    """Endpoint optimizado para recibir la visita de cron-job.org, verificar base de datos y emitir latido."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'trading_mode'")
        mode_row = cursor.fetchone()
        trading_mode = mode_row['value'] if mode_row else "demo"

        cursor.execute("SELECT value FROM settings WHERE key = 'binance_api_key'")
        ak_row = cursor.fetchone()
        binance_api_key = ak_row['value'] if ak_row else ""

        cursor.execute("SELECT value FROM settings WHERE key = 'binance_secret_key'")
        sk_row = cursor.fetchone()
        binance_secret_key = sk_row['value'] if sk_row else ""
        cursor.close()
        conn.close()

        is_valid = verify_binance_credentials(binance_api_key, binance_secret_key, trading_mode)
        if is_valid:
            bot_status["mode"] = trading_mode
            bot_status["is_operating"] = True
            send_ping(f"El motor se encuentra activo, monitoreando el mercado y operando con normalidad [Modo: {trading_mode.upper()}].")
            return {"status": "success", "message": "Ping enviado correctamente a Telegram."}
        else:
            bot_status["is_operating"] = False
            return {"status": "idle", "message": "Motor inactivo: credenciales no válidas o vacías."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>La Bóveda</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.5.31/jspdf.plugin.autotable.min.js"></script>
    
    <style>
        body {
            background-color: #0b0f19;
            color: #e6edf3;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
            align-items: {{ body_align }};
            min-height: 100vh;
        }
        
        .auth-container, .dashboard-container {
            background-color: #111827;
            border: 1px solid #374151;
            border-radius: 14px;
            padding: 30px;
            width: 400px;
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.7);
            position: {{ auth_position }};
        }
        .dashboard-container {
            width: 650px;
            display: {{ dashboard_display }};
            position: relative;
        }
        .auth-container {
            display: {{ auth_display }};
        }

        h1 { font-size: 24px; color: #fbbf24; text-align: center; margin-bottom: 5px; }
        .subtitle { text-align: center; color: #9ca3af; font-size: 13px; margin-bottom: 25px; }
        
        .tabs { display: flex; margin-bottom: 20px; border-bottom: 1px solid #374151; }
        .tab { flex: 1; text-align: center; padding: 10px; cursor: pointer; color: #9ca3af; font-weight: 600; font-size: 13px; }
        .tab.active { color: #fbbf24; border-bottom: 2px solid #fbbf24; }
        .form-section { display: none; }
        .form-section.active { display: block; }

        .card { background-color: #1f2937; border: 1px solid #374151; border-radius: 8px; padding: 15px; margin-bottom: 15px; }
        .row { display: flex; gap: 15px; }
        .col { flex: 1; }
        
        label { display: block; font-size: 12px; color: #9ca3af; margin-bottom: 5px; font-weight: 600; text-transform: uppercase; }
        .value-text { font-size: 15px; font-weight: bold; color: white; }
        .badge-connected { background-color: #059669; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
        .badge-live { background-color: #dc2626; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
        .badge-error { background-color: #b91c1c; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
        .balance-text { color: #34d399; font-size: 18px; font-weight: bold; }
        
        input, select {
            width: 100%; padding: 10px; background: #111827; border: 1px solid #4b5563;
            color: white; border-radius: 6px; box-sizing: border-box; font-size: 14px; margin-bottom: 12px;
        }

        .password-container { position: relative; }
        .password-container input { padding-right: 40px; }
        .toggle-password {
            position: absolute; right: 12px; top: 10px; background: none;
            border: none; cursor: pointer; font-size: 16px; color: #9ca3af;
        }
        .toggle-password:hover { color: white; }
        
        .btn-gold {
            background-color: #fbbf24; color: #111827; border: none; padding: 10px 20px;
            border-radius: 6px; font-weight: bold; cursor: pointer; transition: background 0.2s;
            width: 100%; font-size: 14px;
        }
        .btn-gold:hover { background-color: #f59e0b; }

        .btn-sim {
            width: 100%; background-color: #10b981; color: white; border: none; padding: 14px;
            border-radius: 8px; font-weight: bold; font-size: 15px; cursor: pointer;
            transition: background 0.2s; text-align: center;
        }
        .btn-sim:hover { background-color: #059669; }

        .btn-logout {
            background-color: #ef4444; color: white; border: none; padding: 6px 12px;
            border-radius: 6px; font-weight: bold; font-size: 12px; cursor: pointer; text-decoration: none;
        }
        .btn-logout:hover { background-color: #dc2626; }

        .btn-pdf {
            background-color: #3b82f6; color: white; border: none; padding: 6px 12px;
            border-radius: 6px; font-weight: bold; font-size: 12px; cursor: pointer; transition: background 0.2s;
        }
        .btn-pdf:hover { background-color: #2563eb; }

        .link-text { text-align: center; font-size: 12px; color: #9ca3af; margin-top: 15px; cursor: pointer; }
        .link-text span { color: #fbbf24; text-decoration: underline; }

        .alert-msg {
            background-color: rgba(239, 68, 68, 0.2); border: 1px solid #ef4444; color: #fca5a5;
            padding: 10px; border-radius: 6px; font-size: 13px; text-align: center; margin-bottom: 15px;
            display: {{ alert_display }};
        }

        .table-container {
            max-height: 280px; overflow-y: auto; border: 1px solid #374151;
            border-radius: 8px; background-color: #111827;
        }
        
        .table-container::-webkit-scrollbar { width: 8px; }
        .table-container::-webkit-scrollbar-track { background: #111827; border-radius: 8px; }
        .table-container::-webkit-scrollbar-thumb { background: #4b5563; border-radius: 8px; }

        table { width: 100%; border-collapse: collapse; font-size: 13px; margin: 0; }
        th { text-align: left; color: #9ca3af; padding: 10px; border-bottom: 1px solid #374151; font-size: 11px; text-transform: uppercase; position: sticky; top: 0; background-color: #1f2937; z-index: 1; }
        td { padding: 10px; border-bottom: 1px solid #1f2937; color: #e6edf3; }
        .pnl-pos { color: #34d399; font-weight: bold; }
        .pnl-neg { color: #f87171; font-weight: bold; }
    </style>
</head>
<body>

    <div class="auth-container" id="authBox">
        <h1>LA BÓVEDA</h1>
        <div class="subtitle">Acceso Seguro al Sistema</div>
        
        <div class="tabs">
            <div class="tab {{ login_tab_active }}" onclick="switchTab('login')">Iniciar Sesión</div>
            <div class="tab {{ register_tab_active }}" onclick="switchTab('register')">Registrarse</div>
        </div>

        <div class="alert-msg">{{ alert_message }}</div>

        <div id="loginSection" class="form-section {{ login_section_active }}">
            <form action="/login" method="post">
                <label>Correo Electrónico</label>
                <input type="email" name="email" required placeholder="correo@ejemplo.com">
                <label>Contraseña</label>
                <div class="password-container">
                    <input type="password" name="password" id="loginPassword" required placeholder="••••••••">
                    <button type="button" class="toggle-password" onclick="togglePassword('loginPassword', this)">👁️</button>
                </div>
                <button type="submit" class="btn-gold" style="margin-top: 10px;">Ingresar a La Bóveda</button>
            </form>
            <div class="link-text" onclick="switchTab('recovery')">¿Olvidaste tu contraseña? <span>Recupérala aquí</span></div>
        </div>

        <div id="registerSection" class="form-section {{ register_section_active }}">
            <form action="/register" method="post">
                <label>Correo Electrónico</label>
                <input type="email" name="email" required placeholder="correo@ejemplo.com">
                <label>Contraseña</label>
                <div class="password-container">
                    <input type="password" name="password" id="regPassword" required placeholder="••••••••">
                    <button type="button" class="toggle-password" onclick="togglePassword('regPassword', this)">👁️</button>
                </div>
                <label>Repetir Contraseña</label>
                <div class="password-container">
                    <input type="password" name="confirm_password" id="regConfirmPassword" required placeholder="••••••••">
                    <button type="button" class="toggle-password" onclick="togglePassword('regConfirmPassword', this)">👁️</button>
                </div>
                <button type="submit" class="btn-gold" style="margin-top: 10px;">Crear Cuenta</button>
            </form>
        </div>

        <div id="recoverySection" class="form-section {{ recovery_section_active }}">
            <form action="/recovery" method="post">
                <label>Correo de Recuperación</label>
                <input type="email" name="email" required placeholder="correo@ejemplo.com">
                <label>Nueva Contraseña</label>
                <div class="password-container">
                    <input type="password" name="new_password" id="recPassword" required placeholder="••••••••">
                    <button type="button" class="toggle-password" onclick="togglePassword('recPassword', this)">👁️</button>
                </div>
                <button type="submit" class="btn-gold" style="margin-top: 10px;">Restablecer Contraseña</button>
            </form>
            <div class="link-text" onclick="switchTab('login')">Volver al <span>Inicio de Sesión</span></div>
        </div>
    </div>

    <div class="dashboard-container" id="dashboardBox">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
            <h1 style="margin: 0; text-align: left;">LA BÓVEDA <span style="font-size: 12px; color: #fbbf24;">v4.6 (Riesgo 1%)</span></h1>
            <a href="/logout" class="btn-logout">Cerrar Sesión</a>
        </div>
        <div class="subtitle" style="text-align: left; margin-bottom: 20px;">Motor con Autoevolución de IA, Notificaciones en Bloque y Riesgo al 1%</div>
        
        <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <label>Estado del Motor:</label>
                    <div class="value-text" style="margin-top: 4px;">{{ motor_status_text }}</div>
                </div>
                <div><span class="{{ badge_class }}">{{ badge_text }}</span></div>
            </div>
        </div>

        <div class="row">
            <div class="col card">
                <label>Balance Disponible (PnL Total)</label>
                <div class="balance-text">${{ total_pnl }} USDT</div>
            </div>
            <div class="col card">
                <label>Op. Registradas / Activas</label>
                <div class="value-text" style="font-size: 18px;">{{ total_ops }}</div>
            </div>
        </div>

        <div class="card">
            <form action="/update-capital" method="post">
                <label for="capital">Ajustar Techo de Capital (USDT)</label>
                <div class="row" style="align-items: center; margin-top: 5px;">
                    <div class="col" style="flex: 3;">
                        <input type="number" step="0.1" id="capital" name="capital" value="{{ capital_ceiling }}" style="margin-bottom: 0;">
                    </div>
                    <div class="col" style="flex: 1;">
                        <button type="submit" class="btn-gold" style="width: 100%;">Guardar</button>
                    </div>
                </div>
            </form>
        </div>

        <div class="card">
            <form action="/update-trading-config" method="post">
                <label style="color: #fbbf24; margin-bottom: 10px; font-size: 13px;">⚙️ Configuración de Operación (Demo vs Live)</label>
                <div class="row">
                    <div class="col">
                        <label>Modo de Operación</label>
                        <select name="trading_mode">
                            <option value="demo" {{ demo_selected }}>Demo / Testnet (Simulación)</option>
                            <option value="live" {{ live_selected }}>Real / Live (Binance Dinero Real)</option>
                        </select>
                    </div>
                </div>
                <div class="row" style="margin-top: 5px;">
                    <div class="col">
                        <label>Binance API Key</label>
                        <input type="text" name="binance_api_key" value="{{ binance_api_key }}" placeholder="Tu API Key de Binance">
                    </div>
                    <div class="col">
                        <label>Binance Secret Key</label>
                        <div class="password-container">
                            <input type="password" name="binance_secret_key" id="dashSecret" value="{{ binance_secret_key }}" placeholder="Tu Secret Key">
                            <button type="button" class="toggle-password" onclick="togglePassword('dashSecret', this)">👁️</button>
                        </div>
                    </div>
                </div>
                <button type="submit" class="btn-gold" style="margin-top: 5px;">Guardar Configuración y Validar Llaves</button>
            </form>
        </div>

        <div class="card" style="background: transparent; border: none; padding: 0; margin-bottom: 20px;">
            <form action="/run-bot" method="post">
                <button type="submit" class="btn-sim" {{ btn_disabled }} style="{{ btn_style }}">Simular Compra por Oportunidad (IA Autoevolutiva)</button>
            </form>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <h3 style="margin: 0; color: #9ca3af; font-size: 14px;">Historial de Operaciones</h3>
            <button onclick="descargarPDF()" class="btn-pdf">📄 Descargar PDF</button>
        </div>
        
        <div class="table-container">
            <table id="historyTable">
                <thead>
                    <tr>
                        <th>Par</th>
                        <th>Tipo</th>
                        <th>Monto (Riesgo 1%)</th>
                        <th>Estado / PnL</th>
                    </tr>
                </thead>
                <tbody>
                    {{ operations_rows }}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        function switchTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.form-section').forEach(s => s.classList.remove('active'));
            
            if(tabName === 'login') {
                document.querySelectorAll('.tab')[0].classList.add('active');
                document.getElementById('loginSection').classList.add('active');
            } else if(tabName === 'register') {
                document.querySelectorAll('.tab')[1].classList.add('active');
                document.getElementById('registerSection').classList.add('active');
            } else if(tabName === 'recovery') {
                document.getElementById('recoverySection').classList.add('active');
            }
        }

        function togglePassword(fieldId, btn) {
            const input = document.getElementById(fieldId);
            if (input.type === 'password') {
                input.type = 'text';
                btn.textContent = '🙈';
            } else {
                input.type = 'password';
                btn.textContent = '👁️';
            }
        }

        function descargarPDF() {
            const { jsPDF } = window.jspdf;
            const doc = new jsPDF();
            
            doc.setFontSize(16);
            doc.setTextColor(251, 191, 36);
            doc.text("Historial de Operaciones - La Bóveda", 14, 20);
            
            doc.setFontSize(10);
            doc.setTextColor(100, 100, 100);
            const fecha = new Date().toLocaleString('es-ES');
            doc.text("Generado el: " + fecha, 14, 27);
            
            doc.autoTable({
                html: '#historyTable',
                startY: 35,
                theme: 'grid',
                headStyles: { fillColor: [17, 24, 39], textColor: [251, 191, 36] },
                styles: { fontSize: 10, cellPadding: 4 }
            });
            
            doc.save('Historial_La_Boveda.pdf');
        }
    </script>
</body>
</html>
"""

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
    rows_html = "<tr><td colspan='4' style='text-align: center; color: #6b7280;'>No hay operaciones registradas aún. Presiona simular.</td></tr>"

    if user_email:
        body_align = "flex-start"
        auth_position = "relative"
        auth_display = "none"
        dashboard_display = "block"
        alert_display = "none"

        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*), SUM(profit_loss) FROM operations")
        row_stats = cursor.fetchone()
        total_ops = row_stats['count'] if row_stats and row_stats['count'] is not None else 0
        total_pnl = round(row_stats['sum'], 2) if row_stats and row_stats['sum'] is not None else 0.00
        
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
        
        cursor.execute("SELECT symbol, action, amount, status, profit_loss FROM operations ORDER BY id DESC LIMIT 200")
        ops = cursor.fetchall()
        cursor.close()
        conn.close()
        
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

    if is_valid_keys:
        bot_status["mode"] = trading_mode
        bot_status["is_operating"] = True
    else:
        bot_status["is_operating"] = False

    demo_selected = "selected" if trading_mode == "demo" else ""
    live_selected = "selected" if trading_mode == "live" else ""

    if not is_valid_keys:
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

    html_output = (
        HTML_TEMPLATE
        .replace("{{ body_align }}", body_align)
        .replace("{{ auth_position }}", auth_position)
        .replace("{{ auth_display }}", auth_display)
        .replace("{{ dashboard_display }}", dashboard_display)
        .replace("{{ alert_display }}", alert_display)
        .replace("{{ alert_message }}", msg)
        .replace("{{ login_tab_active }}", login_tab_active)
        .replace("{{ register_tab_active }}", register_tab_active)
        .replace("{{ login_section_active }}", login_section_active)
        .replace("{{ register_section_active }}", register_section_active)
        .replace("{{ recovery_section_active }}", recovery_section_active)
        .replace("{{ total_ops }}", str(total_ops))
        .replace("{{ total_pnl }}", str(total_pnl))
        .replace("{{ capital_ceiling }}", str(capital_ceiling))
        .replace("{{ demo_selected }}", demo_selected)
        .replace("{{ live_selected }}", live_selected)
        .replace("{{ motor_status_text }}", motor_status_text)
        .replace("{{ badge_class }}", badge_class)
        .replace("{{ badge_text }}", badge_text)
        .replace("{{ binance_api_key }}", binance_api_key)
        .replace("{{ binance_secret_key }}", binance_secret_key)
        .replace("{{ btn_disabled }}", btn_disabled)
        .replace("{{ btn_style }}", btn_style)
        .replace("{{ operations_rows }}", rows_html)
    )
    return HTMLResponse(content=html_output)

@app.post("/login")
async def login(email: str = Form(...), password: str = Form(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash, failed_attempts, is_blocked FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        conn.close()
        return RedirectResponse(url="/?msg=Correo%20o%20contraseña%20incorrectos", status_code=303)

    pwd_hash = user['password_hash']
    failed_attempts = user['failed_attempts']
    is_blocked = user['is_blocked']

    if is_blocked:
        cursor.close()
        conn.close()
        return RedirectResponse(url="/?msg=Cuenta%20bloqueada%20por%20intentos.%20Renueve%20su%20contraseña.", status_code=303)

    if pwd_hash != hash_password(password):
        failed_attempts += 1
        if failed_attempts >= 5:
            cursor.execute("UPDATE users SET failed_attempts = %s, is_blocked = 1 WHERE email = %s", (failed_attempts, email))
            conn.commit()
            cursor.close()
            conn.close()
            return RedirectResponse(url="/?msg=Superó%20los%205%20intentos.%20Cuenta%20bloqueada,%20renueve%20contraseña.", status_code=303)
        else:
            cursor.execute("UPDATE users SET failed_attempts = %s WHERE email = %s", (failed_attempts, email))
            conn.commit()
            cursor.close()
            conn.close()
            remaining = 5 - failed_attempts
            return RedirectResponse(url=f"/?msg=Contraseña%20incorrecta.%20Intentos%20restantes:%20{remaining}", status_code=303)

    cursor.execute("UPDATE users SET failed_attempts = 0 WHERE email = %s", (email,))
    session_token = hashlib.sha256(f"{email}{datetime.utcnow()}".encode()).hexdigest()
    cursor.execute("INSERT INTO sessions (session_token, email, created_at) VALUES (%s, %s, %s) ON CONFLICT (session_token) DO UPDATE SET email = EXCLUDED.email, created_at = EXCLUDED.created_at", 
                   (session_token, email, datetime.utcnow().isoformat()))
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

    cursor.execute("INSERT INTO users (email, password_hash, failed_attempts, is_blocked) VALUES (%s, %s, 0, 0)", 
                   (email, hash_password(password)))
    conn.commit()
    cursor.close()
    conn.close()

    return RedirectResponse(url="/?msg=Cuenta%20creada%20exitosamente.%20Inicie%20sesión.", status_code=303)

@app.post("/recovery")
async def recovery(email: str = Form(...), new_password: str = Form(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    if not user:
        cursor.close()
        conn.close()
        return RedirectResponse(url="/?msg=El%20correo%20no%20existe%20en%20el%20sistema&active_tab=recovery", status_code=303)

    cursor.execute("UPDATE users SET password_hash = %s, failed_attempts = 0, is_blocked = 0 WHERE email = %s", 
                   (hash_password(new_password), email))
    conn.commit()
    cursor.close()
    conn.close()

    return RedirectResponse(url="/?msg=Contraseña%20restablecida%20con%20éxito.%20Ya%20puede%20ingresar", status_code=303)

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="session_token")
    return response

@app.post("/update-capital")
async def update_capital(capital: str = Form(...), session_token: Optional[str] = Cookie(None)):
    user_email = get_current_user(session_token)
    if not user_email:
        return RedirectResponse(url="/", status_code=303)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET value = %s WHERE key = 'capital_ceiling'", (capital,))
    conn.commit()
    cursor.close()
    conn.close()
    return RedirectResponse(url="/?msg=Techo%20de%20capital%20actualizado", status_code=303)
