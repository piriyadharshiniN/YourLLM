"""Central configuration. Secrets and model names come from .env."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = Path(os.getenv("KA_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"   # original files
DOC_DIR = DATA_DIR / "documents"    # one JSON per uploaded file
CHAT_DIR = DATA_DIR / "chats"       # one JSON per chat
CHROMA_DIR = str(DATA_DIR / "chroma")
for d in (UPLOAD_DIR, DOC_DIR, CHAT_DIR):
    d.mkdir(parents=True, exist_ok=True)
COLLECTION_NAME = "knowledge_ai"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-4-hydrogen")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

# bge models work best with this prefix on queries (not on documents)
QUERY_PREFIX = (
    "Represent this sentence for searching relevant passages: "
    if "bge" in EMBEDDING_MODEL.lower() else ""
)

# Moderate, accuracy-oriented defaults (no settings page)
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
TOP_K = 5
TEMPERATURE = 0.3
SUPPORTED_TYPES = ["pdf", "docx", "txt"]
