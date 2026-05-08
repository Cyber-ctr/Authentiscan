from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from sentence_transformers import SentenceTransformer, util
from pathlib import Path
import requests
import os
import socket
import logging
import re
import numpy as np
from typing import List
from urllib.parse import quote
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional HF token support
if "HF_TOKEN" not in os.environ:
    os.environ["HF_TOKEN"] = ""

# Constants
MAX_TEXT_LENGTH = 50000
MIN_TEXT_LENGTH = 10
WEB_SEARCH_TIMEOUT = 8
WEB_SEARCH_RETRIES = 2
SIMILARITY_THRESHOLD_HIGH = 75
SIMILARITY_THRESHOLD_MODERATE = 40

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL_NAME = "paraphrase-MiniLM-L3-v2"
model = None
db_embeddings = None

documents_db = [
    "Artificial intelligence is transforming education.",
    "Machine learning improves plagiarism detection systems.",
    "Natural language processing helps detect paraphrased content.",
]

def find_available_port(preferred_port: int = 10000, fallback_ports: List[int] = None) -> int:
    if fallback_ports is None:
        fallback_ports = [10001, 10002, 8000, 8080]

    ports_to_try = [preferred_port] + [p for p in fallback_ports if p != preferred_port]
    for port in ports_to_try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue

    raise RuntimeError("No available port found. Please free a port and try again.")

def get_start_port() -> int:
    requested_port = int(os.environ.get("PORT", 10000))
    return find_available_port(requested_port)

def get_model():
    global model
    if model is None:
        model = SentenceTransformer(MODEL_NAME)
    return model

def get_db_embeddings():
    global db_embeddings
    if db_embeddings is None:
        model_instance = get_model()
        db_embeddings = model_instance.encode(documents_db, convert_to_tensor=True)
        logger.info("Database embeddings loaded successfully")
    return db_embeddings

def split_sentences(text: str) -> List[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]

def web_search(query: str, retries: int = WEB_SEARCH_RETRIES) -> List[str]:
    query = (query or "").strip()
    if len(query) < 3:
        return []

    for attempt in range(retries):
        try:
            encoded_query = quote(query)
            url = f"https://duckduckgo.com/html/?q={encoded_query}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

            response = requests.get(url, headers=headers, timeout=WEB_SEARCH_TIMEOUT)
            response.raise_for_status()

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")

            results = soup.find_all("a", class_="result__a")
            urls = [r.get("href") for r in results[:5] if r.get("href")]

            if urls:
                return urls

        except requests.exceptions.Timeout:
            logger.warning(f"Web search timeout for query: {query} (attempt {attempt + 1})")
            if attempt < retries - 1:
                time.sleep(1)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Web search error for query: {query}: {e}")
            if attempt < retries - 1:
                time.sleep(1)
        except Exception as e:
            logger.error(f"Unexpected error in web_search: {e}")

    return []

class TextRequest(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, v):
        if not v or not v.strip():
            raise ValueError("Text cannot be empty")

        v = v.strip()

        if len(v) < MIN_TEXT_LENGTH:
            raise ValueError(f"Text must be at least {MIN_TEXT_LENGTH} characters")

        if len(v) > MAX_TEXT_LENGTH:
            raise ValueError(f"Text cannot exceed {MAX_TEXT_LENGTH} characters")

        return v

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "embeddings_loaded": db_embeddings is not None,
    }

@app.get("/")
def serve_frontend():
    frontend_path = BASE_DIR / "index.html"
    if not frontend_path.exists():
        raise HTTPException(status_code=500, detail="Frontend not available")
    return FileResponse(frontend_path)

@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)

@app.post("/scan")
def scan_text(request: TextRequest):
    try:
        text = request.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="Text is empty")

        model_instance = get_model()
        db_embeds = get_db_embeddings()

        sentences = split_sentences(text)
        if not sentences:
            raise HTTPException(status_code=400, detail="Text does not contain valid sentences")

        results = []
        web_matches = set()

        for sentence in sentences:
            emb = model_instance.encode(sentence, convert_to_tensor=True)
            scores = util.cos_sim(emb, db_embeds)

            max_score = float(scores.max())
            if np.isnan(max_score) or np.isinf(max_score):
                max_score = 0.0

            ai_score = max(0, min(100, max_score * 100))

            web_results = web_search(sentence)
            if web_results:
                web_matches.update(web_results)

            web_score = 20 if web_results else 0
            final_score = round((ai_score * 0.7) + (web_score * 0.3), 2)

            if final_score >= SIMILARITY_THRESHOLD_HIGH:
                status = "High similarity"
            elif final_score >= SIMILARITY_THRESHOLD_MODERATE:
                status = "Moderate similarity"
            else:
                status = "Low similarity"

            results.append(
                {
                    "sentence": sentence,
                    "ai_score": round(ai_score, 2),
                    "web_score": web_score,
                    "final_score": final_score,
                    "status": status,
                }
            )

        if not results:
            raise HTTPException(status_code=500, detail="Failed to process text")

        overall = round(sum(r["final_score"] for r in results) / len(results), 2)
        if np.isnan(overall) or np.isinf(overall):
            overall = 0.0

        return {
            "overall_similarity": overall,
            "details": results,
            "web_sources": list(web_matches)[:8],
            "sentence_count": len(results),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in scan_text: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during scan")

if __name__ == "__main__":
    import uvicorn
    port = get_start_port()
    logger.info(f"Starting Authentiscan on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")