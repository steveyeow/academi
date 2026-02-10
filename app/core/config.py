from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", DATA_DIR / "uploads"))
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "chatbook.db"))

APP_NAME = os.getenv("APP_NAME", "Feynman")
APP_TITLE = os.getenv("APP_TITLE", "Feynman")

PROVIDER_ORDER = [p.strip().lower() for p in os.getenv("PROVIDER_ORDER", "gemini,openai,kimi").split(",") if p.strip()]

CHAT_PROVIDER = os.getenv("CHAT_PROVIDER", "auto").lower()
EMBED_PROVIDER = os.getenv("EMBED_PROVIDER", "auto").lower()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash")
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")

KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
KIMI_BASE_URL = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
KIMI_CHAT_MODEL = os.getenv("KIMI_CHAT_MODEL", "moonshot-v1-8k")
KIMI_EMBED_MODEL = os.getenv("KIMI_EMBED_MODEL", "")

MAX_CHUNK_CHARS = int(os.getenv("MAX_CHUNK_CHARS", "1200"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "120"))
TOP_K = int(os.getenv("TOP_K", "5"))
