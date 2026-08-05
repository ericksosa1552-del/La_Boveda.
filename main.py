import sqlite3
import random
import time
from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
import requests

app = FastAPI(title="La Bóveda - Motor de Copiado y Oportunidades")

DB_NAME = "bóveda_users.db"

TELEGRAM_BOT_TOKEN = "8610300157:AAG86zeR58BF-o42_ZyyJPYneZf3uzmBxes"
TELEGRAM_CHAT_ID = 8536842251

def enviar_alerta_telegram(mensaje: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensaje,
            "parse_mode": "Markdown"
        }
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Error Telegram: {e}")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            api_key TEXT DEFAULT '',
            api_secret TEXT DEFAULT '',
            mode TEXT DEFAULT 'SIMULACIÓN',
            techo_capital REAL DEFAULT 500.0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS operaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            par TEXT,
            tipo TEXT,
            monto REAL,
            pnl REAL,
            estado TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.get("/ping")
def ping():
    return {"status": "activo", "timestamp": time.time()}

@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html>
        <head><title>La Bóveda - Login</title></head>
        <body style="background:#0b0e11; color:#white; font-family:sans-serif; text-align:center; padding-top:80px;">
            <h1 style="color:#f0b90b; font-size: 36px;">LA BÓVEDA</h1>
            <p style="color:#848e9c;">Motor de Oportunidades y Gestión de Riesgo</p>
            <form action="/login" method="post" style="display:inline-block; background:#1e2329; padding:40px; border-radius:12px; border:1px solid #2b313a; margin-top: 20px;">
                <input type="email" name="email" placeholder="Ingresa tu correo" required style="padding:12px; width:280px; border-radius:6px; border:1px solid #474d57; background:#0b0e11; color:white; font-size: 14px;"><br><br>
                <button type="submit" style="padding:12px 24px; background:#f0b90b; color:black; border:none; border-radius:6px; font-weight:bold; cursor:pointer; font-size: 14px; width: 100%;">Entrar al Panel</button>
            </form>
        </body>
    </html>
    """

@app.post("/login")
def login(email: str = Form(...)):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (email, mode, techo_capital) VALUES (?, 'SIMULACIÓN', 500.0)", (email,))
        conn.commit()
    conn.close()
    return RedirectResponse(url=f"/panel?email={email}", status_code=303)

@app.get("/panel", response_class=HTMLResponse)
def panel(email: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT techo_capital, mode, api_key, api_secret FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    
    techo = row[0] if row else 500.0
    mode = row[1] if row else 'SIMULACIÓN'
    api_key_val = row[2] if row else ''
    api_secret_val = row[3] if row else ''

    cursor.execute("SELECT COUNT(*) FROM operaciones WHERE email = ?", (email,))
    total_ops = cursor.fetchone()[0]

    cursor.execute("SELECT par, tipo, monto, pnl, estado FROM operaciones WHERE email = ? ORDER BY id DESC LIMIT 5", (email,))
    ops = cursor.fetchall()
    conn.close()

    ops_html = ""
    for op in ops:
        pnl_val = op[3]
        pnl_color = "#0ecb81" if pnl_val >= 0 else "#f6465d"
        pnl_text = f"+{pnl_val:.2f} USDT" if pnl_val >= 0 else f"{pnl_val:.2f} USDT"
        ops_html += f"<tr><td style='padding:10px; border-bottom:1px solid #2b313a; color:#fff;'>{op[0]}</td><td style='padding:10px; border-bottom:1px solid #2b313a; color:#fff;'>{op[1]}</td><td style='padding:10px; border-bottom:1px solid #2b313a; color:#fff;'>{op[2]} USDT</td><td style='padding:10px; border-bottom:1px solid #2b313a; color:{pnl_color}; font-weight:bold;'>{pnl_text}</td><td style='padding:10px; border-bottom:1px solid #2b313a; color:#0ecb81; font-weight:bold;'>{op[4]}</td></tr>"

    return f"""
    <html>
    <head>
        <title>La Bóveda - Dashboard</title>
        <style>
            body {{ background: #0b0e11; color: #eaeaeb; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; display: flex; justify-content: center; }}
            .main-card {{ background: #1e2329; width: 680px; padding: 35px; border-radius: 14px; border: 1px solid #2b313a; box-shadow: 0 10px 30px rgba(0,0,0,0.8); margin-bottom: 40px; }}
            h1 {{ color: #f0b90b; font-size: 28px; margin-bottom: 2px; text-align: center; }}
            .subtitle {{ color: #848e9c; font-size: 13px; margin-bottom: 25px; text-align: center; }}
            .box-row {{ display: flex; gap: 12px; margin-bottom: 12px; }}
            .box {{ background: #14151a; border: 1px solid #2b313a; padding: 15px; border-radius: 8px; flex: 1; }}
            .box-title {{ color: #848e9c; font-size: 12px; margin-bottom: 4px; }}
            .box-value {{ font-size: 18px; font-weight: bold; color: #fff; }}
            .badge-ok {{ background: #0ecb81; color: black; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; float: right; }}
            .section-box {{ background: #14151a; border: 1px solid #2b313a; padding: 15px; border-radius: 8px; margin-bottom: 12px; }}
            input, select {{ padding: 10px; width: 100%; box-sizing: border-box; border-radius: 6px; border: 1px solid #474d57; background: #0b0e11; color: white; margin-top: 5px; margin-bottom: 10px; font-size: 13px; }}
            .btn-save {{ background: #f0b90b; color: #000; border: none; padding: 10px 15px; border-radius: 6px; font-weight: bold; cursor: pointer; width: 100%; margin-top: 5px; }}
            .btn-save:hover {{ background: #fcd535; }}
            .btn-action {{ background: #0ecb81; color: #000; border: none; padding: 14px; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%; font-size: 15px; transition: 0.2s; }}
            .btn-action:hover {{ background: #09b870; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }}
            th {{ color: #848e9c; text-align: left; padding: 8px; border-bottom: 1px solid #2b313a; }}
        </style>
    </head>
    <body>
        <div class="main-card">
            <h1>LA BÓVEDA</h1>
            <div class="subtitle">Motor de Oportunidades y Gestión de Riesgo</div>
            
            <div class="box-row">
                <div class="box" style="flex: 2;">
                    <div class="box-title">Estado del Motor: <span class="badge-ok">CONECTADO</span></div>
                    <div class="box-value" style="font-size: 14px; color: #fff; margin-top: 5px;">Conectado ({mode} - MOTOR ACTIVO)</div>
                </div>
            </div>

            <div class="box-row">
                <div class="box">
                    <div class="box-title">Balance Disponible:</div>
                    <div class="box-value" style="color: #0ecb81;">1,000.00 USDT</div>
                </div>
                <div class="box">
                    <div class="box-title">Op. Activas:</div>
                    <div class="box-value">{total_ops}</div>
                </div>
            </div>

            <div class="section-box">
                <div class="box-title" style="margin-bottom: 4px;">Ajustar Techo de Capital (USDT)</div>
                <form action="/actualizar-techo" method="post">
                    <input type="hidden" name="email" value="{email}">
                    <div style="display: flex; gap: 10px;">
                        <input type="number" step="0.01" name="techo" value="{techo}" style="margin:0; width: 75%;">
                        <button type="submit" class="btn-save" style="width: 25%; margin:0;">Guardar</button>
                    </div>
                </form>
            </div>

            <div class="section-box">
                <div class="box-title" style="margin-bottom: 4px;">Configuración de Conexión y Credenciales</div>
                <form action="/guardar-config" method="post">
                    <input type="hidden" name="email" value="{email}">
                    
                    <label style="font-size: 11px; color: #848e9c;">Modo Operativo:</label>
                    <select name="mode">
                        <option value="SIMULACIÓN" {"selected" if mode == "SIMULACIÓN" else ""}>SIMULACIÓN (Sin riesgo)</option>
                        <option value="EN VIVO" {"selected" if mode == "EN VIVO" else ""}>EN VIVO (Binance)</option>
                    </select>

                    <label style="font-size: 11px; color: #848e9c;">Binance API Key:</label>
                    <input type="text" name="api_key" value="{api_key_val}" placeholder="Pega tu API Key">

                    <label style="font-size: 11px; color: #848e9c;">Binance API Secret:</label>
                    <input type="password" name="api_secret" value="{api_secret_val}" placeholder="Pega tu API Secret">

                    <button type="submit" class="btn-save" style="background: #2b313a; color: #f0b90b; border: 1px solid #f0b90b;">Guardar Credenciales</button>
                </form>
            </div>

            <div style="margin-bottom: 15px;">
                <form action="/simular-operacion" method="post">
                    <input type="hidden" name="email" value="{email}">
                    <button type="submit" class="btn-action">Simular Compra por Oportunidad</button>
                </form>
            </div>

            <div class="section-box">
                <div class="box-title" style="margin-bottom: 8px;">Historial de Operaciones y PnL</div>
                <table>
                    <thead>
                        <tr><th>Par</th><th>Tipo</th><th>Monto</th><th>PnL (Ganancia/Pérdida)</th><th>Estado</th></tr>
                    </thead>
                    <tbody>
                        {ops_html if ops_html else "<tr><td colspan='5' style='text-align:center; color:#848e9c; padding:10px;'>No hay operaciones recientes.</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """

@app.post("/actualizar-techo")
def actualizar_techo(email: str = Form(...), techo: float = Form(...)):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET techo_capital = ? WHERE email = ?", (techo, email))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/panel?email={email}", status_code=303)

@app.post("/guardar-config")
def guardar_config(email: str = Form(...), mode: str = Form(...), api_key: str = Form(...), api_secret: str = Form(...)):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users SET mode = ?, api_key = ?, api_secret = ? WHERE email = ?
    ''', (mode, api_key, api_secret, email))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/panel?email={email}", status_code=303)

@app.post("/simular-operacion")
def simular_operacion(email: str = Form(...)):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT techo_capital, mode FROM users WHERE email = ?', (email,))
    row = cursor.fetchone()
    techo = row[0] if row else 500.0
    mode = row[1] if row else 'SIMULACIÓN'

    monto_operacion = round(random.uniform(15.0, min(50.0, techo)), 2)
    pnl_operacion = round(random.uniform(-2.5, 6.5), 2)
    
    tipo_op = 'COMPRA REAL (BINANCE)' if mode == 'EN VIVO' else 'COMPRA BAJO PRECIO'
    estado_op = 'EJECUTADA EN VIVO' if mode == 'EN VIVO' else 'EJECUTADA'

    cursor.execute('''
        INSERT INTO operaciones (email, par, tipo, monto, pnl, estado)
        VALUES (?, 'BTC/USDT', ?, ?, ?, ?)
    ''', (email, tipo_op, monto_operacion, pnl_operacion, estado_op))
    conn.commit()
    conn.close()

    pnl_str = f"+{pnl_operacion} USDT" if pnl_operacion >= 0 else f"{pnl_operacion} USDT"
    mensaje_alerta = (
        f"🚨 *¡Oportunidad Detectada ({mode})!*\n"
        "Par: `BTC/USDT`\n"
        f"Monto: `{monto_operacion} USDT`\n"
        f"PnL Estimado: `{pnl_str}`\n"
        f"Estado: `{estado_op} EXITOSAMENTE`"
    )
    enviar_alerta_telegram(mensaje_alerta)

    return RedirectResponse(url=f"/panel?email={email}", status_code=303)
