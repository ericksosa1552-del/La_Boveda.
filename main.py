import sqlite3
import random
import requests
from datetime import datetime
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="La Bóveda", version="3.8")

DB_NAME = "boveda_memory.db"

# Tus credenciales directas de Telegram
TELEGRAM_BOT_TOKEN = "8610300157:AAG86zeR58BF-o42_ZyyJPYneZf3uzmBxes"
TELEGRAM_CHAT_ID = "8536842251"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('capital_ceiling', '100.0')")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_learning_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_hash TEXT UNIQUE,
            success_count INTEGER,
            failure_count INTEGER,
            last_updated TEXT,
            weight_adjustment REAL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Plantilla HTML con el diseño original conservado y flechas numéricas nativas
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>La Bóveda - Dashboard</title>
    <style>
        body {
            background-color: #0b0f19;
            color: #e6edf3;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
            align-items: flex-start;
            min-height: 100vh;
        }
        .dashboard-container {
            background-color: #111827;
            border: 1px solid #374151;
            border-radius: 14px;
            padding: 30px;
            width: 650px;
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.7);
        }
        h1 { font-size: 24px; color: #fbbf24; text-align: center; margin-bottom: 5px; }
        .subtitle { text-align: center; color: #9ca3af; font-size: 13px; margin-bottom: 25px; }
        
        .card {
            background-color: #1f2937;
            border: 1px solid #374151;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
        }
        .row { display: flex; gap: 15px; }
        .col { flex: 1; }
        
        label { display: block; font-size: 12px; color: #9ca3af; margin-bottom: 5px; font-weight: 600; text-transform: uppercase; }
        .value-text { font-size: 15px; font-weight: bold; color: white; }
        .badge-connected { background-color: #059669; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
        .balance-text { color: #34d399; font-size: 18px; font-weight: bold; }
        
        input {
            width: 100%;
            padding: 10px;
            background: #111827;
            border: 1px solid #4b5563;
            color: white;
            border-radius: 6px;
            box-sizing: border-box;
            font-size: 14px;
        }
        
        .btn-gold {
            background-color: #fbbf24;
            color: #111827;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            font-weight: bold;
            cursor: pointer;
            transition: background 0.2s;
            white-space: nowrap;
        }
        .btn-gold:hover { background-color: #f59e0b; }

        .btn-sim {
            width: 100%;
            background-color: #10b981;
            color: white;
            border: none;
            padding: 14px;
            border-radius: 8px;
            font-weight: bold;
            font-size: 15px;
            cursor: pointer;
            transition: background 0.2s;
            text-align: center;
        }
        .btn-sim:hover { background-color: #059669; }

        h3 { font-size: 14px; color: #9ca3af; margin-top: 25px; margin-bottom: 10px; border-bottom: 1px solid #374151; padding-bottom: 5px; }
        
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            margin-top: 10px;
        }
        th { text-align: left; color: #9ca3af; padding: 8px; border-bottom: 1px solid #374151; font-size: 11px; text-transform: uppercase; }
        td { padding: 10px 8px; border-bottom: 1px solid #1f2937; color: #e6edf3; }
        .pnl-pos { color: #34d399; font-weight: bold; }
        .pnl-neg { color: #f87171; font-weight: bold; }
    </style>
</head>
<body>
    <div class="dashboard-container">
        <h1>LA BÓVEDA</h1>
        <div class="subtitle">Motor de Oportunidades, IA y Gestión de Riesgo</div>
        
        <!-- Estado del Motor -->
        <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <label>Estado del Motor:</label>
                    <div class="value-text" style="margin-top: 4px;">Conectado (TESTNET - IA ACTIVA)</div>
                </div>
                <div>
                    <span class="badge-connected">CONECTADO</span>
                </div>
            </div>
        </div>

        <!-- Balance y Operaciones Activas -->
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

        <!-- Ajustar Techo de Capital con el diseño original y flechas numéricas -->
        <div class="card">
            <form action="/update-capital" method="post">
                <label for="capital">Ajustar Techo de Capital (USDT)</label>
                <div class="row" style="align-items: center; margin-top: 5px;">
                    <div class="col" style="flex: 3;">
                        <input type="number" step="0.1" id="capital" name="capital" value="{{ capital_ceiling }}">
                    </div>
                    <div class="col" style="flex: 1;">
                        <button type="submit" class="btn-gold" style="width: 100%;">Guardar</button>
                    </div>
                </div>
            </form>
        </div>

        <!-- Simular Detección de Oferta (IA) -->
        <div class="card" style="background: transparent; border: none; padding: 0; margin-bottom: 20px;">
            <form action="/run-bot" method="post">
                <button type="submit" class="btn-sim">Simular Compra por Oportunidad (IA)</button>
            </form>
        </div>

        <!-- Historial de Operaciones -->
        <h3>Historial de Operaciones</h3>
        <table>
            <thead>
                <tr>
                    <th>Par</th>
                    <th>Tipo</th>
                    <th>Monto</th>
                    <th>Estado / PnL</th>
                </tr>
            </thead>
            <tbody>
                {{ operations_rows }}
            </tbody>
        </table>
    </div>
</body>
</html>
"""

def send_telegram_alert(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception:
        pass

def evaluate_market_with_ai(pattern_hash: str) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT profit_loss FROM operations ORDER BY id DESC LIMIT 5")
    recent_ops = cursor.fetchall()
    conn.close()
    
    if len(recent_ops) >= 3:
        losses_count = sum(1 for op in recent_ops if op[0] < 0)
        if losses_count >= 3:
            return False
            
    return True

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*), SUM(profit_loss) FROM operations")
    row_stats = cursor.fetchone()
    total_ops = row_stats[0] if row_stats[0] is not None else 0
    total_pnl = round(row_stats[1], 2) if row_stats[1] is not None else 0.00
    
    cursor.execute("SELECT value FROM settings WHERE key = 'capital_ceiling'")
    cap_row = cursor.fetchone()
    capital_ceiling = cap_row[0] if cap_row else "100.0"
    
    cursor.execute("SELECT symbol, action, amount, status, profit_loss FROM operations ORDER BY id DESC LIMIT 5")
    ops = cursor.fetchall()
    conn.close()
    
    rows_html = ""
    if not ops:
        rows_html = "<tr><td colspan='4' style='text-align: center; color: #6b7280;'>No hay operaciones registradas aún. Presiona simular.</td></tr>"
    else:
        for op in ops:
            symbol, action, amount, status, pnl = op
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
            
    html_output = (
        HTML_TEMPLATE
        .replace("{{ total_ops }}", str(total_ops))
        .replace("{{ total_pnl }}", str(total_pnl))
        .replace("{{ capital_ceiling }}", str(capital_ceiling))
        .replace("{{ operations_rows }}", rows_html)
    )
    return HTMLResponse(content=html_output)

@app.post("/update-capital")
async def update_capital(capital: str = Form(...)):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('capital_ceiling', ?)", (capital,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/", status_code=303)

@app.post("/run-bot")
async def run_bot():
    pattern_hash = "pattern_market_low_volatility"
    should_trade = evaluate_market_with_ai(pattern_hash)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT value FROM settings WHERE key = 'capital_ceiling'")
    cap_row = cursor.fetchone()
    max_capital = float(cap_row[0]) if cap_row else 100.0
    
    amount_sim = round(random.uniform(10.0, min(50.0, max_capital)), 2)
    
    if should_trade:
        profit_loss = round(random.uniform(-3.50, 6.50), 2)
        action = "COMPRA BAJO PRECIO"
        status = "EJECUTADA EXITOSAMENTE"
        
        pnl_sign_str = f"+{profit_loss:.2f}" if profit_loss >= 0 else f"{profit_loss:.2f}"
        msg = (
            "🚨 *¡Oportunidad Detectada (SIMULACIÓN)!*\n"
            "Par: `BTC/USDT`\n"
            f"Monto: `{amount_sim} USDT`\n"
            f"PnL Estimado: `{pnl_sign_str} USDT`\n"
            f"Estado: *{status}*"
        )
    else:
        action = "BLOQUEO RIESGO"
        status = "EVITADO POR IA"
        profit_loss = 0.00
        msg = (
            "🛡️ *¡Mala Racha Detectada / Riesgo Evitado!*\n"
            "Par: `BTC/USDT`\n"
            "La IA pausó operaciones debido a pérdidas consecutivas recientes.\n"
            f"Estado: *{status}*"
        )

    cursor.execute(
        "INSERT INTO operations (timestamp, mode, symbol, action, price, amount, status, profit_loss, market_pattern_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (datetime.utcnow().isoformat(), "demo", "BTC/USDT", action, 65000.0, amount_sim, status, profit_loss, pattern_hash)
    )
    conn.commit()
    conn.close()

    send_telegram_alert(msg)

    return RedirectResponse(url="/", status_code=303)
