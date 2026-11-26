import json
import os
import socket
import urllib.request
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./learn2lead.db")


def _resolve_via_doh(host: str) -> str | None:
    """Resolves hostname via Google DNS-over-HTTPS (works even when ISP DNS fails)."""
    try:
        url = f"https://dns.google/resolve?name={host}&type=A"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for ans in data.get("Answer", []):
                if ans.get("type") == 1 and ans.get("data"):
                    return ans["data"].strip()
    except Exception:
        pass
    return None


def _resolve_connect_args(db_url: str) -> dict:
    """Connects to Neon PostgreSQL even when local Wi-Fi router DNS fails."""
    if not db_url.startswith("postgresql"):
        return {}
    try:
        parsed = make_url(db_url)
        host = parsed.host
        if host:
            try:
                socket.gethostbyname(host)
            except OSError:
                ip = _resolve_via_doh(host)
                if ip:
                    return {"hostaddr": ip}
    except Exception:
        pass
    return {}


engine = create_engine(
    DATABASE_URL,
    connect_args=_resolve_connect_args(DATABASE_URL),
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()