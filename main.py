import os
import hmac
import hashlib
import time
import requests
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import sqlite3

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
    if os.path.exists("index.html"):
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
            # Si el usuario no existe al intentar hacer login con credenciales estilo token directo
            cursor.execute("INSERT INTO users (email, password, api_key, api_secret, mode) VALUES (?, ?, ?, ?, ?)", 
                           (data.user_id, data.api_secret, data.api_key, data.api_secret, data.mode))
            conn.commit()
        else:
            stored_password, stored_key, stored_secret = row
            # Si se está autenticando desde el login con contraseña
            if data.api_secret == stored_password or data.api_secret == stored_secret:
                pass
            else:
                # Actualizar API keys si se guardan desde el panel interno
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
