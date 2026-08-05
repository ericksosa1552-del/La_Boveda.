import sqlite3
import random
from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
import requests

app = FastAPI(title="La Bóveda - Motor de Copiado y Oportunidades")

DB_NAME = "bóveda_users.db"

# CREDENCIALES DE TELEGRAM
TELEGRAM_BOT_TOKEN = "8610300157:AAG86zeR58BF-o42_ZyyJPYneZf3uzmBxes"
TELEGRAM_CHAT_ID = 8536842251

def enviar_alerta_telegram(mensaje: str):
    """Envía una notificación al chat de Telegram configurado."""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensaje,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload, timeout=5)
        print(f">>> TELEGRAM STATUS: {response.status_code}")
        print(f">>> TELEGRAM BODY: {response.text}")
    except Exception as e:
        print(f">>> ERROR CRITICO TELEGRAM: {e}")

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
            techo_capital REAL DEFAULT 100.0
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
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html>
        <head><title>La Bóveda - Login</title></head>
        <body style="background:#0b0e11; color:#white; font-family:sans-serif; text-align:center; padding-top:50px;">
            <h1 style="color:#f0b90b;">LA BÓVEDA</h1>
            <p style="color:#848e9c;">Sistema automatizado de oportunidades y copy-trading</p>
            <form action="/login" method="post" style="display:inline-block; background:#1e2329; padding:30px; border-radius:10px; border:1px solid #2b313a;">
                <input type="email" name="email" placeholder="Ingresa tu correo" required style="padding:10px; width:250px; border-radius:5px; border:1px solid #474d57; background:#0b0e11; color:white;"><br><br>
                <button type="submit" style="padding:10px 20px; background:#f0b90b; color:black; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">Entrar al Panel</button>
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
        cursor.execute("INSERT INTO users (email, mode, techo_capital) VALUES (?, 'SIMULACIÓN', 100.0)", (email,))
        conn.commit()
    conn.close()
    return RedirectResponse(url=f"/panel?email={email}", status_code=303)

@app.get("/panel", response_class=HTMLResponse)
def panel(email: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT techo_capital FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    techo = row[0] if row else 100.0

    cursor.execute("SELECT par, tipo, monto, estado, timestamp FROM operaciones WHERE email = ? ORDER BY id DESC LIMIT 10", (email,))
    ops = cursor.fetchall()
    conn.close()

    ops_html = ""
    for op in ops:
        ops_html += f"<tr><td>{op[0]}</td><td>{op[1]}</td><td>{op[2]} USDT</td><td style='color:#0ecb81;'>{op[3]}</td><td style='font-size:12px; color:#848e9c;'>{op[4]}</td></tr>"

    return f"""
    <html>
    <head>
        <title>La Bóveda - Dashboard</title>
        <style>
            body {{ background: #0b0e11; color: #eaeaeb; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; }}
            .container {{ max-width: 900px; margin: auto; background: #1e2329; padding: 30px; border-radius: 12px; border: 1px solid #2b313a; box-shadow: 0 8px 24px rgba(0,0,0,0.5); }}
            h1 {{ color: #f0b90b; font-size: 28px; margin-bottom: 5px; }}
            .subtitle {{ color: #848e9c; font-size: 14px; margin-bottom: 25px; }}
            .card {{ background: #14151a; border: 1px solid #2b313a; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
            button {{ background: #f0b90b; color: #000; border: none; padding: 12px 20px; border-radius: 6px; font-weight: bold; cursor: pointer; transition: 0.2s; }}
            button:hover {{ background: #fcd535; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #2b313a; font-size: 14px; }}
            th {{ color: #848e9c; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>LA BÓVEDA</h1>
            <div class="subtitle">Usuario activo: {email} | Modo Operativo: En Vivo / Oportunidades</div>
            
            <div class="card">
                <h3 style="margin-top:0; color:#f0b90b;">Panel de Control y Techo de Capital</h3>
                <p>Techo actual configurado: <b>{techo} USDT</b></p>
                <form action="/simular-operacion" method="post">
                    <input type="hidden" name="email" value="{email}">
                    <button type="submit">⚡ Simular Compra por Oportunidad</button>
                </form>
            </div>

            <div class="card">
                <h3 style="margin-top:0; color:#f0b90b;">Historial de Operaciones Recientes</h3>
                <table>
                    <thead>
                        <tr><th>Par</th><th>Tipo</th><th>Monto</th><th>Estado</th><th>Fecha/Hora</th></tr>
                    </thead>
                    <tbody>
                        {ops_html if ops_html else "<tr><td colspan='5' style='text-align:center; color:#848e9c;'>No hay operaciones registradas aún.</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """

@app.post("/simular-operacion")
def simular_operacion(email: str = Form(...)):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT techo_capital FROM users WHERE email = ?', (email,))
    row = cursor.fetchone()
    techo = row[0] if row else 100.0

    monto_operacion = round(random.uniform(15.0, min(50.0, techo)), 2)
    
    cursor.execute('''
        INSERT INTO operaciones (email, par, tipo, monto, estado)
        VALUES (?, 'BTC/USDT', 'COMPRA BAJO PRECIO', ?, 'EJECUTADA')
    ''', (email, monto_operacion))
    conn.commit()
    conn.close()

    # DISPARAR ALERTA A TELEGRAM CON FORMATO LIMPIO
    mensaje_alerta = (
        "🚨 *¡Oportunidad Detectada y Comprada!*\n"
        "Par: `BTC/USDT`\n"
        f"Monto: `{monto_operacion} USDT`\n"
        "Estado: `EJECUTADA EXITOSAMENTE`"
    )
    enviar_alerta_telegram(mensaje_alerta)

    return RedirectResponse(url=f"/panel?email={email}", status_code=303)
