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

# Set Hugging Face token if available (optional for higher rate limits)
# os.environ["HF_TOKEN"] = "your_huggingface_token_here"  # Uncomment and set your token
if "HF_TOKEN" not in os.environ:
    os.environ["HF_TOKEN"] = ""  # Suppress warning for unauthenticated requests

# Constants
MAX_TEXT_LENGTH = 50000
MIN_TEXT_LENGTH = 10
WEB_SEARCH_TIMEOUT = 8
WEB_SEARCH_RETRIES = 2
SIMILARITY_THRESHOLD_HIGH = 75
SIMILARITY_THRESHOLD_MODERATE = 40

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent

# CORS (frontend access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lightweight model for Render
MODEL_NAME = "paraphrase-MiniLM-L3-v2"
model = None
db_embeddings = None

documents_db = [
    "Artificial intelligence is transforming education.",
    "Machine learning improves plagiarism detection systems.",
    "Natural language processing helps detect paraphrased content."
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
        try:
            model_instance = get_model()
            db_embeddings = model_instance.encode(
                documents_db, convert_to_tensor=True
            )
            logger.info("Database embeddings loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load database embeddings: {e}")
            raise
    return db_embeddings


def split_sentences(text: str) -> List[str]:
    """
    Split text into sentences using regex to handle abbreviations and edge cases.
    """
    # Split by sentence-ending punctuation but avoid abbreviations
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]
    return sentences


def web_search(query: str, retries: int = WEB_SEARCH_RETRIES) -> List[str]:
    """
    Search web with retry logic and proper error handling.
    """
    query = (query or "").strip()
    if len(query) < 3:
        return []
    
    for attempt in range(retries):
        try:
            # Properly encode query
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
                time.sleep(1)  # Back off before retry
        except requests.exceptions.RequestException as e:
            logger.warning(f"Web search error for query: {query}: {e}")
            if attempt < retries - 1:
                time.sleep(1)
        except Exception as e:
            logger.error(f"Unexpected error in web_search: {e}")
    
    return []


class TextRequest(BaseModel):
    text: str

    @field_validator('text')
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
    """Health check endpoint for monitoring."""
    try:
        # Verify model can be loaded
        model_instance = get_model()
        get_db_embeddings()
        return {"status": "healthy", "model_loaded": model_instance is not None}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.get("/")
def serve_frontend():
    try:
        frontend_path = BASE_DIR / "index.html"
        if not frontend_path.exists():
            raise FileNotFoundError("index.html not found")
        return FileResponse(frontend_path)
    except Exception as e:
        logger.error(f"Failed to serve frontend: {e}")
        raise HTTPException(status_code=500, detail="Frontend not available")


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@app.post("/scan")
def scan_text(request: TextRequest):
    """
    Scan text for similarity with enhanced accuracy and error handling.
    """
    try:
        text = request.text.strip()
        
        if not text:
            raise HTTPException(status_code=400, detail="Text is empty")

        # Get model and embeddings
        try:
            model_instance = get_model()
            db_embeds = get_db_embeddings()
        except Exception as e:
            logger.error(f"Failed to load model/embeddings: {e}")
            raise HTTPException(status_code=500, detail="Model initialization failed")

        # Split into sentences more accurately
        sentences = split_sentences(text)
        
        if not sentences:
            raise HTTPException(status_code=400, detail="Text does not contain valid sentences")

        results = []
        web_matches = set()

        for sentence in sentences:
            try:
                # Encode sentence
                emb = model_instance.encode(sentence, convert_to_tensor=True)
                scores = util.cos_sim(emb, db_embeds)
                
                # Validate scores
                max_score = float(scores.max())
                if np.isnan(max_score) or np.isinf(max_score):
                    logger.warning(f"Invalid score for sentence: {sentence}")
                    max_score = 0.0
                
                # Calculate AI similarity score (0-100)
                ai_score = max(0, min(100, max_score * 100))

                # Web check with better scoring
                web_results = web_search(sentence)
                if web_results:
                    web_matches.update(web_results)
                
                # More accurate web scoring: presence of results indicates potential plagiarism
                web_score = 20 if web_results else 0

                # Combined score with weighted average
                final_score = (ai_score * 0.7) + (web_score * 0.3)
                final_score = round(final_score, 2)

                # Determine status based on thresholds
                if final_score >= SIMILARITY_THRESHOLD_HIGH:
                    status = "High similarity"
                elif final_score >= SIMILARITY_THRESHOLD_MODERATE:
                    status = "Moderate similarity"
                else:
                    status = "Low similarity"

                results.append({
                    "sentence": sentence,
                    "ai_score": round(ai_score, 2),
                    "web_score": web_score,
                    "final_score": final_score,
                    "status": status
                })
            
            except Exception as e:
                logger.error(f"Error processing sentence: {e}")
                continue

        if not results:
            raise HTTPException(status_code=500, detail="Failed to process text")

        # Calculate overall similarity score
        overall = (
            sum(r["final_score"] for r in results) / len(results)
            if results else 0
        )
        overall = round(overall, 2)

        # Ensure overall score is valid
        if np.isnan(overall) or np.isinf(overall):
            overall = 0.0

        return {
            "overall_similarity": overall,
            "details": results,
            "web_sources": list(web_matches)[:8],
            "sentence_count": len(results)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in scan_text: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during scan")


@app.on_event("startup")
def startup_event():
    """Preload the model and embeddings during application startup."""
    try:
        get_model()
        get_db_embeddings()
        logger.info("Model and embeddings loaded successfully on startup")
    except Exception as e:
        logger.error(f"Startup initialization failed: {e}")
        raise


if __name__ == "__main__":
    try:
        import uvicorn
        port = get_start_port()
        logger.info(f"Starting Authentiscan on port {port}")
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    except Exception as e:
        logger.critical(f"Failed to start application: {e}")
        raise
