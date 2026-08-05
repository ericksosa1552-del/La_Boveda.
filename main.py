import os
import requests
from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
import ccxt
import sqlite3

app = FastAPI()

DB_NAME = "boveda_users.db"

# CONFIGURACIÓN DE TELEGRAM (Puedes poner tus datos reales aquí cuando quieras)
TELEGRAM_BOT_TOKEN = "8610300157:AAG86zeR58BF-o42_ZyyJPYneZf3uzmBxes"
TELEGRAM_CHAT_ID = "8536842251"

def enviar_alerta_telegram(mensaje: str):
    """Envía una notificación al chat de Telegram configurado."""
    if TELEGRAM_BOT_TOKEN == "TU_BOT_TOKEN_AQUI" or not TELEGRAM_BOT_TOKEN:
        print(f"[TELEGRAM SIMULADO]: {mensaje}")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"[ERROR TELEGRAM]: {e}")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Tabla de usuarios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            api_key TEXT,
            api_secret TEXT,
            mode TEXT,
            techo_capital REAL DEFAULT 500.0
        )
    ''')
    # Tabla de operaciones / historial
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS operaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            par TEXT,
            tipo TEXT,
            monto REAL,
            estado TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>La Bóveda - Panel de Control</title>
        <style>
            body { font-family: Arial, sans-serif; background-color: #0b0e11; color: #ffffff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .card { background: #1e2329; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); width: 400px; text-align: center; }
            h2 { color: #f0b90b; }
            input, select { width: 100%; padding: 10px; margin: 10px 0; background: #2b313a; border: 1px solid #474d57; color: white; border-radius: 6px; box-sizing: border-box; }
            button { background: #f0b90b; color: #0b0e11; border: none; padding: 12px; width: 100%; font-weight: bold; border-radius: 6px; cursor: pointer; margin-top: 10px; }
            button:hover { background: #d9a406; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>LA BÓVEDA</h2>
            <p>Panel de Control y Gestión de Riesgo</p>
            <form action="/vincular" method="POST">
                <input type="email" name="email" placeholder="Correo electrónico" required>
                <input type="text" name="api_key" placeholder="API Key de Binance" required>
                <input type="password" name="api_secret" placeholder="Secret Key de Binance" required>
                <select name="mode">
                    <option value="testnet">Testnet / Demo (Pruebas)</option>
                    <option value="live">Live (Real)</option>
                </select>
                <button type="submit">Vincular y Guardar</button>
            </form>
        </div>
    </body>
    </html>
    """

@app.post("/vincular")
def vincular(email: str = Form(...), api_key: str = Form(...), api_secret: str = Form(...), mode: str = Form(...)):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (email, api_key, api_secret, mode, techo_capital)
        VALUES (?, ?, ?, ?, 500.0)
        ON CONFLICT(email) DO UPDATE SET
            api_key = excluded.api_key,
            api_secret = excluded.api_secret,
            mode = excluded.mode
    ''', (email, api_key, api_secret, mode))
    conn.commit()
    conn.close()
    
    # Notificar inicio de sesión por Telegram
    enviar_alerta_telegram(f"🚀 *La Bóveda Iniciada*\nUsuario vinculado: `{email}`\nModo: `{mode.upper()}`")
    
    return RedirectResponse(url=f"/panel?email={email}", status_code=303)

@app.post("/actualizar-techo")
def actualizar_techo(email: str = Form(...), nuevo_techo: float = Form(...)):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET techo_capital = ? WHERE email = ?', (nuevo_techo, email))
    conn.commit()
    conn.close()
    
    enviar_alerta_telegram(f"⚙️ *Techo de Capital Actualizado*\nNuevo límite: `{nuevo_techo} USDT`")
    return RedirectResponse(url=f"/panel?email={email}", status_code=303)

@app.get("/panel", response_class=HTMLResponse)
def panel(email: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT techo_capital FROM users WHERE email = ?', (email,))
    row = cursor.fetchone()
    
    # Obtener historial de operaciones
    cursor.execute('SELECT par, tipo, monto, estado, fecha FROM operaciones WHERE email = ? ORDER BY id DESC LIMIT 5', (email,))
    ops = cursor.fetchall()
    conn.close()
    
    techo = row[0] if row else 500.0

    # Construir filas de la tabla de operaciones
    ops_html = ""
    if ops:
        for op in ops:
            ops_html += f"<tr><td>{op[0]}</td><td>{op[1]}</td><td>{op[2]} USDT</td><td>{op[3]}</td></tr>"
    else:
        ops_html = "<tr><td colspan='4' style='color: #848e9c; text-align: center;'>No hay operaciones registradas aún.</td></tr>"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>La Bóveda - Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #0b0e11; color: #ffffff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
            .card {{ background: #1e2329; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); width: 480px; text-align: center; }}
            h2 {{ color: #f0b90b; margin-bottom: 5px; }}
            .status-box {{ background: #2b313a; padding: 12px; border-radius: 8px; margin: 10px 0; text-align: left; }}
            .badge {{ padding: 5px 10px; border-radius: 4px; font-weight: bold; font-size: 12px; float: right; }}
            .badge-loading {{ background: #f0b90b; color: black; }}
            .badge-error {{ background: #f6465d; color: white; }}
            .badge-ok {{ background: #0ecb81; color: black; }}
            .metric {{ font-size: 16px; font-weight: bold; color: #0ecb81; }}
            input {{ width: 60%; padding: 6px; background: #1e2329; border: 1px solid #474d57; color: white; border-radius: 4px; }}
            button {{ background: #f0b90b; color: #0b0e11; border: none; padding: 7px 12px; font-weight: bold; border-radius: 4px; cursor: pointer; }}
            button:hover {{ background: #d9a406; }}
            table {{ width: 100%; font-size: 12px; margin-top: 5px; border-collapse: collapse; text-align: left; }}
            th, td {{ padding: 6px; border-bottom: 1px solid #2b313a; }}
            th {{ color: #848e9c; }}
        </style>
        <script>
            async function actualizarEstado() {{
                try {{
                    let response = await fetch('/api/estado-cuenta/{email}');
                    let data = await response.json();
                    document.getElementById('status-text').innerText = data.status;
                    document.getElementById('balance-text').innerText = data.balance_total;
                    document.getElementById('op-text').innerText = data.operaciones_activas;
                    
                    let badge = document.getElementById('status-badge');
                    badge.innerText = data.status.includes("Conectado") ? "CONECTADO" : "ERROR";
                    badge.className = data.status.includes("Conectado") ? "badge badge-ok" : "badge badge-error";
                }} catch (e) {{
                    console.error("Error al actualizar estado", e);
                }}
            }}
            setInterval(actualizarEstado, 4000);
            window.onload = actualizarEstado;
        </script>
    </head>
    <body>
        <div class="card">
            <h2>LA BÓVEDA</h2>
            <p style="color: #848e9c; font-size: 13px;">Panel de Control y Gestión de Riesgo</p>
            
            <div class="status-box">
                <span style="font-size: 13px; color: #848e9c;">Estado:</span>
                <span id="status-badge" class="badge badge-loading">Cargando...</span>
                <div id="status-text" style="margin-top: 5px; font-weight: bold; font-size: 13px;">Verificando conexión...</div>
            </div>

            <div style="display: flex; gap: 10px;">
                <div class="status-box" style="flex: 1; text-align: left;">
                    <span style="font-size: 12px; color: #848e9c;">Balance Disponible</span>
                    <div id="balance-text" class="metric">0.00 USDT</div>
                </div>
                <div class="status-box" style="flex: 1; text-align: left;">
                    <span style="font-size: 12px; color: #848e9c;">Op. Activas</span>
                    <div id="op-text" style="font-size: 16px; font-weight: bold; color: white;">0</div>
                </div>
            </div>

            <div class="status-box">
                <span style="font-size: 12px; color: #848e9c;">Ajustar Techo de Capital (USDT)</span>
                <form action="/actualizar-techo" method="POST" style="margin-top: 5px; display: flex; gap: 5px;">
                    <input type="hidden" name="email" value="{email}">
                    <input type="number" step="10" name="nuevo_techo" value="{techo}" required>
                    <button type="submit">Guardar</button>
                </form>
            </div>

            <div class="status-box" style="text-align: left;">
                <span style="font-size: 12px; color: #848e9c;">Historial de Operaciones</span>
                <table>
                    <thead>
                        <tr><th>Par</th><th>Tipo</th><th>Monto</th><th>Estado</th></tr>
                    </thead>
                    <tbody>
                        {ops_html}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """

@app.get("/api/estado-cuenta/{user_id}")
def estado_cuenta(user_id: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT api_key, api_secret, mode, techo_capital FROM users WHERE email = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return {
            "status": "Usuario no encontrado",
            "balance_total": "0.00 USDT",
            "operaciones_activas": 0,
            "techo_capital": 500.0
        }

    api_key, api_secret, mode, techo_capital = user

    # Simulación inteligente conectada al panel
    if mode == "testnet" or len(api_key) > 5:
        return {
            "status": f"Conectado ({mode.upper()} - SIMULACIÓN)",
            "balance_total": "1,000.00 USDT",
            "operaciones_activas": 0,
            "techo_capital": techo_capital
        }

    try:
        exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
        })
        balance = exchange.fetch_balance()
        free_usdt = balance['free'].get('USDT', 0.0) if 'free' in balance else 0.0

        return {
            "status": f"Conectado ({mode.upper()})",
            "balance_total": f"{free_usdt:.2f} USDT",
            "operaciones_activas": 0,
            "techo_capital": techo_capital
        }
    except Exception as e:
        return {
            "status": "Error de conexión con Binance",
            "balance_total": "0.00 USDT",
            "operaciones_activas": 0,
            "techo_capital": techo_capital
        }
