"""Auth Service — Simple JWT authentication replacing Keycloak."""

import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, DateTime, Enum, String, create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ.get("JWT_SECRET", "changeme")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))
JWT_REFRESH_EXPIRY_DAYS = int(os.environ.get("JWT_REFRESH_EXPIRY_DAYS", "7"))
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://trafficbook:trafficbook@postgres:5432/trafficbook"
)
REGION = os.environ.get("REGION", "EU")

# SQLAlchemy needs sync driver — swap asyncpg if present
SYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

engine = create_engine(SYNC_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(
        Enum("driver", "traffic_authority", "admin", name="user_role", create_type=False),
        nullable=False,
        default="driver",
    )
    vehicle_type = Column(
        Enum("STANDARD", "EMERGENCY", "AUTHORITY", name="vehicle_type_enum", create_type=False),
        nullable=False,
        default="STANDARD",
    )
    region = Column(String, nullable=False, default=REGION)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    token = Column(String, unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

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


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    vehicle_type: str
    region: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_ROLES = {"driver", "traffic_authority", "admin"}
VALID_VEHICLE_TYPES = {"STANDARD", "EMERGENCY", "AUTHORITY"}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "vehicle_type": user.vehicle_type,
        "region": user.region,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": now,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str, db: Session) -> str:
    token_str = str(uuid.uuid4())
    expires = datetime.now(timezone.utc) + timedelta(days=JWT_REFRESH_EXPIRY_DAYS)
    rt = RefreshToken(user_id=user_id, token=token_str, expires_at=expires)
    db.add(rt)
    db.commit()
    return token_str


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    token = authorization.removeprefix("Bearer ")
    return decode_access_token(token)


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(title="TrafficBook Auth Service", version="1.0.0")


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/auth/register", response_model=TokenResponse, status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if req.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {VALID_ROLES}")
    if req.vehicle_type not in VALID_VEHICLE_TYPES:
        raise HTTPException(
            status_code=400, detail=f"Invalid vehicle_type. Must be one of: {VALID_VEHICLE_TYPES}"
        )

    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=req.email,
        name=req.name,
        hashed_password=hash_password(req.password),
        role=req.role,
        vehicle_type=req.vehicle_type,
        region=REGION,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access = create_access_token(user)
    refresh = create_refresh_token(user.id, db)
    return TokenResponse(access_token=access, refresh_token=refresh)


@app.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access = create_access_token(user)
    refresh = create_refresh_token(user.id, db)
    return TokenResponse(access_token=access, refresh_token=refresh)


@app.post("/auth/refresh", response_model=TokenResponse)
def refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    rt = db.query(RefreshToken).filter(RefreshToken.token == req.refresh_token).first()
    if not rt:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    expires_at = rt.expires_at if rt.expires_at.tzinfo else rt.expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        db.delete(rt)
        db.commit()
        raise HTTPException(status_code=401, detail="Refresh token expired")

    user = db.query(User).filter(User.id == rt.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Rotate refresh token
    db.delete(rt)
    db.commit()

    access = create_access_token(user)
    new_refresh = create_refresh_token(user.id, db)
    return TokenResponse(access_token=access, refresh_token=new_refresh)


@app.get("/auth/me", response_model=UserResponse)
def me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == current_user["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        vehicle_type=user.vehicle_type,
        region=user.region,
    )


@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "service": "auth_service"}
    except Exception:
        return {"status": "unhealthy", "service": "auth_service", "error": "Database connection failed"}
