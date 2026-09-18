import sqlite3
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import passlib.hash as _hash
import jwt
import os

SECRET_KEY = "chave_secreta_financeiro_compartilhado"
ALGORITHM = "HS256"

app = FastAPI()

def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id TEXT,
        creditor TEXT NOT NULL,
        entity TEXT NOT NULL,
        total_amount REAL NOT NULL,
        installment_number INT NOT NULL,
        total_installments INT NOT NULL,
        installment_amount REAL NOT NULL,
        due_date TEXT NOT NULL,
        is_paid INTEGER DEFAULT 0,
        is_recurrent INTEGER DEFAULT 0,
        created_by_user_name TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()

init_db()

@app.get("/")
def read_root():
    return FileResponse("templates/index.html")

app.mount("/static", StaticFiles(directory="templates"), name="static")