import os
from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
import ccxt
import sqlite3

app = FastAPI()

DB_NAME = "boveda_users.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Recreamos la tabla limpia para evitar conflictos con columnas antiguas
    cursor.execute('DROP TABLE IF EXISTS users')
    cursor.execute('''
        CREATE TABLE users (
            email TEXT PRIMARY KEY,
            api_key TEXT,
            api_secret TEXT,
            mode TEXT,
            techo_capital REAL DEFAULT 500.0
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
    return RedirectResponse(url=f"/panel?email={email}", status_code=303)

@app.get("/panel", response_class=HTMLResponse)
def panel(email: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT techo_capital FROM users WHERE email = ?', (email,))
    row = cursor.fetchone()
    conn.close()
    
    techo = row[0] if row else 500.0

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>La Bóveda - Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #0b0e11; color: #ffffff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
            .card {{ background: #1e2329; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); width: 420px; text-align: center; }}
            h2 {{ color: #f0b90b; margin-bottom: 5px; }}
            .status-box {{ background: #2b313a; padding: 15px; border-radius: 8px; margin: 15px 0; text-align: left; }}
            .badge {{ padding: 5px 10px; border-radius: 4px; font-weight: bold; font-size: 12px; float: right; }}
            .badge-loading {{ background: #f0b90b; color: black; }}
            .badge-error {{ background: #f6465d; color: white; }}
            .badge-ok {{ background: #0ecb81; color: black; }}
            .metric {{ font-size: 18px; font-weight: bold; color: #0ecb81; }}
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
            <p style="color: #848e9c; font-size: 14px;">Panel de Control y Gestión de Riesgo</p>
            
            <div class="status-box">
                <span style="font-size: 14px; color: #848e9c;">Estado:</span>
                <span id="status-badge" class="badge badge-loading">Cargando...</span>
                <div id="status-text" style="margin-top: 5px; font-weight: bold; font-size: 14px;">Verificando conexión...</div>
            </div>

            <div class="status-box">
                <span style="font-size: 14px; color: #848e9c;">Balance Disponible:</span>
                <div id="balance-text" class="metric">0.00 USDT</div>
            </div>

            <div style="display: flex; gap: 10px;">
                <div class="status-box" style="flex: 1; text-align: center;">
                    <span style="font-size: 12px; color: #848e9c;">Techo Actual</span>
                    <div style="font-size: 16px; font-weight: bold; color: #f0b90b;">{techo:.2f} USDT</div>
                </div>
                <div class="status-box" style="flex: 1; text-align: center;">
                    <span style="font-size: 12px; color: #848e9c;">Op. Activas</span>
                    <div id="op-text" style="font-size: 16px; font-weight: bold;">0</div>
                </div>
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

    try:
        # Configuración para usar Spot Testnet (testnet.binance.vision)
        exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot'
            }
        })

        if mode == "testnet":
            exchange.set_sandbox_mode(False)
            exchange.urls['api']['public'] = 'https://testnet.binance.vision/api/v3'
            exchange.urls['api']['private'] = 'https://testnet.binance.vision/api/v3'

        balance = exchange.fetch_balance()
        free_usdt = balance['free'].get('USDT', 0.0) if 'free' in balance else 0.0
        total_operaciones = 0

        return {
            "status": f"Conectado ({mode.upper()} - SPOT)",
            "balance_total": f"{free_usdt:.2f} USDT",
            "operaciones_activas": total_operaciones,
            "techo_capital": techo_capital
        }

    except ccxt.AuthenticationError as auth_err:
        print(f"[DEBUG AUTH ERROR]: {auth_err}")
        return {
            "status": "Error: Credenciales inválidas",
            "balance_total": "0.00 USDT",
            "operaciones_activas": 0,
            "techo_capital": techo_capital
        }
    except Exception as e:
        import traceback
        print("--- ERROR DETALLADO DE BINANCE ---")
        traceback.print_exc()
        print("-----------------------------------")
        return {
            "status": "Error de conexión con Binance",
            "balance_total": "0.00 USDT",
            "operaciones_activas": 0,
            "techo_capital": techo_capital
        }
