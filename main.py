from fastapi import FastAPI, Response, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from sentence_transformers import SentenceTransformer, util
from pathlib import Path
import requests
import os
import logging
import re
import numpy as np
from typing import List
from urllib.parse import quote
from io import BytesIO
import PyPDF2
from docx import Document

# ---------------------------
# CONFIG
# ---------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 50000
MIN_TEXT_LENGTH = 10

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent

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

# ---------------------------
# MODEL LOADING
# ---------------------------

def get_model():
    global model
    if model is None:
        logger.info("Loading AI model...")
        model = SentenceTransformer(MODEL_NAME)
    return model

def get_db_embeddings():
    global db_embeddings
    if db_embeddings is None:
        model_instance = get_model()
        db_embeddings = model_instance.encode(
            documents_db,
            convert_to_tensor=True
        )
    return db_embeddings

# ---------------------------
# HELPERS
# ---------------------------

def split_sentences(text: str) -> List[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [
        s.strip()
        for s in sentences
        if s.strip() and len(s.strip()) > 5
    ]

def web_search(query: str):
    try:
        encoded_query = quote(query)

        url = f"https://duckduckgo.com/html/?q={encoded_query}"

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=5
        )

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(response.text, "html.parser")

        results = soup.find_all("a", class_="result__a")

        return [
            r.get_text()
            for r in results[:5]
        ]

    except Exception as e:
        logger.warning(f"Web search failed: {e}")
        return []

# ---------------------------
# FILE EXTRACTION
# ---------------------------

def extract_pdf_text(file_bytes):
    text = ""

    reader = PyPDF2.PdfReader(BytesIO(file_bytes))

    for page in reader.pages:
        extracted = page.extract_text()

        if extracted:
            text += extracted + "\n"

    return text

def extract_docx_text(file_bytes):
    text = ""

    doc = Document(BytesIO(file_bytes))

    for para in doc.paragraphs:
        text += para.text + "\n"

    return text

# ---------------------------
# VALIDATION
# ---------------------------

class TextRequest(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, v):

        if not v or not v.strip():
            raise ValueError("Text cannot be empty")

        v = v.strip()

        if len(v) < MIN_TEXT_LENGTH:
            raise ValueError("Text too short")

        if len(v) > MAX_TEXT_LENGTH:
            raise ValueError("Text too long")

        return v

# ---------------------------
# ROUTES
# ---------------------------

@app.get("/")
def serve_frontend():

    frontend_path = BASE_DIR / "index.html"

    return FileResponse(frontend_path)

@app.get("/health")
def health():

    return {
        "status": "healthy"
    }

@app.get("/favicon.ico")
def favicon():

    return Response(status_code=204)

# ---------------------------
# CORE SCANNER
# ---------------------------

def analyze_text(text: str):

    model_instance = get_model()

    db_embeds = get_db_embeddings()

    sentences = split_sentences(text)

    results = []

    web_matches = set()

    for sentence in sentences:

        emb = model_instance.encode(
            sentence,
            convert_to_tensor=True
        )

        scores = util.cos_sim(emb, db_embeds)

        max_score = float(scores.max())

        ai_score = max(0, min(100, max_score * 100))

        web_results = web_search(sentence)

        if web_results:
            web_matches.update(web_results)

        web_score = 20 if web_results else 0

        final_score = round(
            (ai_score * 0.7) + (web_score * 0.3),
            2
        )

        if final_score >= 75:
            status = "High similarity"
        elif final_score >= 40:
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

    overall = round(
        sum(r["final_score"] for r in results) / len(results),
        2
    ) if results else 0

    return {
        "overall_similarity": overall,
        "details": results,
        "web_sources": list(web_matches)[:8],
        "sentence_count": len(results)
    }

# ---------------------------
# TEXT SCAN
# ---------------------------

@app.post("/scan")
def scan_text(request: TextRequest):

    return analyze_text(request.text)

# ---------------------------
# FILE SCAN
# ---------------------------

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):

    filename = file.filename.lower()

    file_bytes = await file.read()

    text = ""

    if filename.endswith(".pdf"):

        text = extract_pdf_text(file_bytes)

    elif filename.endswith(".docx"):

        text = extract_docx_text(file_bytes)

    elif filename.endswith(".txt"):

        text = file_bytes.decode("utf-8")

    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type"
        )

    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail="No readable text found"
        )

    return analyze_text(text)

# ---------------------------
# START SERVER
# ---------------------------

if __name__ == "__main__":

    import uvicorn

    port = int(os.environ.get("PORT", 10000))

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
    )