import os
import hmac
import hashlib
import time
import requests
from fastapi import FastAPI, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import sqlite3
import ccxt  # Librería para conectar con Binance y otros exchanges

app = FastAPI()

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base de datos SQLite local para la gestión de usuarios
DB_NAME = "boveda_users.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            api_key TEXT,
            api_secret TEXT,
            mode TEXT DEFAULT 'testnet'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

class RegistroRequest(BaseModel):
    email: str
    password: str

class TokenRequest(BaseModel):
    user_id: str
    api_key: str
    api_secret: str
    mode: str = "testnet"

class ForgotPasswordRequest(BaseModel):
    user_id: str

@app.get("/", response_class=HTMLResponse)
def serve_index():
    ruta_archivo = "estatica/index.html"
    if os.path.exists(ruta_archivo):
        with open(ruta_archivo, "r", encoding="utf-8") as f:
            return f.read()
    elif os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Bienvenido a La Bóveda</h1><p>Archivo index.html no encontrado en el servidor.</p>"

@app.post("/api/register")
def registrar_usuario(data: RegistroRequest):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT email FROM users WHERE email = ?", (data.email,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="El correo ya está registrado en La Bóveda.")
        
        cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)", (data.email, data.password))
        conn.commit()
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    
    return {"message": "Usuario registrado exitosamente"}

@app.post("/api/token")
def procesar_token(data: TokenRequest):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT password, api_key, api_secret FROM users WHERE email = ?", (data.user_id,))
        row = cursor.fetchone()

        if not row:
            cursor.execute("INSERT INTO users (email, password, api_key, api_secret, mode) VALUES (?, ?, ?, ?, ?)", 
                           (data.user_id, data.api_secret, data.api_key, data.api_secret, data.mode))
            conn.commit()
        else:
            stored_password, stored_key, stored_secret = row
            if data.api_secret == stored_password or data.api_secret == stored_secret:
                pass
            else:
                cursor.execute("UPDATE users SET api_key = ?, api_secret = ?, mode = ? WHERE email = ?", 
                               (data.api_key, data.api_secret, data.mode, data.user_id))
                conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    return {"access_token": f"mock-jwt-token-{data.user_id}", "token_type": "bearer"}

@app.post("/api/forgot-password")
def forgot_password(data: ForgotPasswordRequest):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE email = ?", (data.user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="El correo no está registrado.")
    
    return {"debug_token": f"RESET-PASS-TOKEN-SECURE-9941"}

@app.get("/api/estado-cuenta/{user_id}")
def estado_cuenta(user_id: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT api_key, api_secret, mode FROM users WHERE email = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")
        
        api_key, api_secret, mode = row
        
        if not api_key or not api_secret:
            return {
                "status": "Sin Credenciales",
                "balance_total": "0.00 USDT",
                "operaciones_activas": 0
            }
        
        # Conexión real a Binance usando CCXT
        is_testnet = (mode == "testnet")
        exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future'
            }
        })

        if is_testnet:
            exchange.set_sandbox_mode(True)

        # Consultar balance en la API de Binance
        balance = exchange.fetch_balance()
        free_usdt = balance['free'].get('USDT', 0.0)

        return {
            "status": f"Conectado ({mode.upper()})",
            "balance_total": f"{free_usdt:.2f} USDT",
            "operaciones_activas": 0
        }
        
    except ccxt.AuthenticationError:
        return {
            "status": "Error: Credenciales inválidas",
            "balance_total": "0.00 USDT",
            "operaciones_activas": 0
        }
    except Exception as e:
        return {
            "status": "Error de conexión con Binance",
            "balance_total": "0.00 USDT",
            "operaciones_activas": 0
        }
    finally:
        conn.close()
