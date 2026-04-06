import os
import uuid
from datetime import datetime, timedelta

import bcrypt
import jwt
import psycopg2
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="auth_service")

REGION = os.getenv("REGION", "EU")
JWT_SECRET = os.getenv("JWT_SECRET", "secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
JWT_REFRESH_EXPIRY_DAYS = int(os.getenv("JWT_REFRESH_EXPIRY_DAYS", "7"))
DATABASE_URL = os.getenv("DATABASE_URL")


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email        TEXT UNIQUE NOT NULL,
            name         TEXT NOT NULL,
            password     TEXT NOT NULL,
            role         TEXT DEFAULT 'driver',
            vehicle_type TEXT DEFAULT 'STANDARD',
            region       TEXT NOT NULL,
            created_at   TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
            token      TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    conn.commit()
    cur.close()
    conn.close()


@app.on_event("startup")
def startup():
    init_db()


# ── Schemas ──────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str
    role: str = "driver"
    vehicle_type: str = "STANDARD"


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class SyncRequest(BaseModel):
    email: str
    name: str
    password_hash: str
    role: str
    vehicle_type: str


# ── JWT helpers ───────────────────────────────────────────────────────────────

def make_access_token(user: dict) -> str:
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "vehicle_type": user["vehicle_type"],
        "region": REGION,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def make_refresh_token(user_id: str) -> tuple[str, datetime]:
    token = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(days=JWT_REFRESH_EXPIRY_DAYS)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO refresh_tokens (user_id, token, expires_at) VALUES (%s, %s, %s)",
        (user_id, token, expires_at),
    )
    conn.commit()
    cur.close()
    conn.close()
    return token, expires_at


# ── Shared JWT validator (importable by other services) ───────────────────────

def verify_token(authorization: str = Header(...)) -> dict:
    token = authorization.replace("Bearer ", "")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


def require_role(*roles):
    def dep(user=Depends(verify_token)):
        if user.get("role") not in roles:
            raise HTTPException(403, "Insufficient role")
        return user
    return dep


def is_emergency(user=Depends(verify_token)) -> bool:
    return user.get("vehicle_type") == "EMERGENCY"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/auth/register", status_code=201)
def register(req: RegisterRequest):
    hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (email, name, password, role, vehicle_type, region) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, email, name, role, vehicle_type",
            (req.email, req.name, hashed, req.role, req.vehicle_type, REGION),
        )
        row = cur.fetchone()
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(409, "Email already registered")
    finally:
        cur.close()
        conn.close()

    user = {"id": row[0], "email": row[1], "name": row[2], "role": row[3], "vehicle_type": row[4]}
    access = make_access_token(user)
    refresh, _ = make_refresh_token(str(user["id"]))
    return {"access_token": access, "refresh_token": refresh, "user": user}


@app.post("/auth/login")
def login(req: LoginRequest):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, email, name, password, role, vehicle_type FROM users WHERE email = %s",
        (req.email,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row or not bcrypt.checkpw(req.password.encode(), row[3].encode()):
        raise HTTPException(401, "Invalid credentials")
    user = {"id": row[0], "email": row[1], "name": row[2], "role": row[4], "vehicle_type": row[5]}
    access = make_access_token(user)
    refresh, _ = make_refresh_token(str(user["id"]))
    return {"access_token": access, "refresh_token": refresh, "user": user}


@app.post("/auth/refresh")
def refresh(req: RefreshRequest):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, expires_at FROM refresh_tokens WHERE token = %s",
        (req.refresh_token,),
    )
    row = cur.fetchone()
    if not row or row[1] < datetime.utcnow():
        cur.close()
        conn.close()
        raise HTTPException(401, "Refresh token invalid or expired")
    cur.execute(
        "SELECT id, email, name, role, vehicle_type FROM users WHERE id = %s",
        (row[0],),
    )
    u = cur.fetchone()
    cur.close()
    conn.close()
    user = {"id": u[0], "email": u[1], "name": u[2], "role": u[3], "vehicle_type": u[4]}
    return {"access_token": make_access_token(user)}


@app.get("/auth/me")
def me(user: dict = Depends(verify_token)):
    return user


@app.post("/auth/sync", status_code=201)
def sync(req: SyncRequest):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (email, name, password, role, vehicle_type, region) "
        "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (email) DO NOTHING",
        (req.email, req.name, req.password_hash, req.role, req.vehicle_type, REGION),
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "synced"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "auth_service", "region": REGION}
