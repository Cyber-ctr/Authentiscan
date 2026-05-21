from fastapi import (
    FastAPI,
    Response,
    HTTPException,
    UploadFile,
    File,
    Request,
    Depends
)

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel, field_validator

from sentence_transformers import SentenceTransformer, util

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from pathlib import Path
from urllib.parse import quote
from io import BytesIO
from typing import List

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter

from docx import Document

from sqlalchemy.orm import Session

from database import engine, get_db, Base
from models import ScanHistory

import requests
import logging
import PyPDF2
import bleach
import magic
import uvicorn
import os
import re
import datetime

# ---------------------------
# CONFIG
# ---------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 50000
MIN_TEXT_LENGTH = 10
MAX_FILE_SIZE = 5 * 1024 * 1024

MODEL_NAME = "paraphrase-MiniLM-L3-v2"
BASE_DIR = Path(__file__).resolve().parent

# ---------------------------
# APP
# ---------------------------

app = FastAPI()
Base.metadata.create_all(bind=engine)

app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------------------------
# RATE LIMITER
# ---------------------------

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# ---------------------------
# CORS
# ---------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# SECURITY HEADERS
# ---------------------------


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com;"
    )
    return response

# ---------------------------
# EXCEPTION HANDLERS
# ---------------------------


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Too many requests. Please slow down."})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})

# ---------------------------
# AI MODEL
# ---------------------------

model = None
db_embeddings = None

documents_db = [
    "Artificial intelligence is transforming education.",
    "Machine learning improves plagiarism detection systems.",
    "Natural language processing helps detect paraphrased content."
]


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
        db_embeddings = model_instance.encode(documents_db, convert_to_tensor=True)
    return db_embeddings

# ---------------------------
# HELPERS
# ---------------------------


def sanitize_text(text: str) -> str:
    return bleach.clean(text, tags=[], strip=True)


def split_sentences(text: str) -> List[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]


def web_search(query: str) -> List[str]:
    try:
        encoded_query = quote(query)
        url = f"https://duckduckgo.com/html/?q={encoded_query}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")
        results = soup.find_all("a", class_="result__a")
        return [r.get_text() for r in results[:5]]
    except Exception as e:
        logger.warning(f"Web search failed: {e}")
        return []

# ---------------------------
# FILE SECURITY
# ---------------------------


def validate_file(filename: str, file_bytes: bytes):
    allowed_extensions = {".pdf", ".docx", ".txt"}
    extension = os.path.splitext(filename)[1].lower()
    if extension not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Invalid file type.")
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large.")
    mime = magic.from_buffer(file_bytes, mime=True)
    allowed_mimes = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain"
    }
    if mime not in allowed_mimes:
        raise HTTPException(status_code=400, detail="Suspicious file detected.")

# ---------------------------
# FILE EXTRACTION
# ---------------------------


def extract_pdf_text(file_bytes: bytes) -> str:
    text = ""
    reader = PyPDF2.PdfReader(BytesIO(file_bytes))
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    return text


def extract_docx_text(file_bytes: bytes) -> str:
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
# ANALYSIS ENGINE
# ---------------------------


def analyze_text(text: str) -> dict:
    text = sanitize_text(text)
    model_instance = get_model()
    db_embeds = get_db_embeddings()
    sentences = split_sentences(text)
    results = []
    web_matches = set()

    for sentence in sentences:
        emb = model_instance.encode(sentence, convert_to_tensor=True)
        scores = util.cos_sim(emb, db_embeds)
        max_score = float(scores.max())
        ai_score = max(0, min(100, max_score * 100))
        web_results = web_search(sentence)
        if web_results:
            web_matches.update(web_results)
        web_score = 20 if web_results else 0
        final_score = round((ai_score * 0.7) + (web_score * 0.3), 2)

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

    overall = round(sum(r["final_score"] for r in results) / len(results), 2) if results else 0

    return {
        "overall_similarity": overall,
        "details": results,
        "web_sources": list(web_matches)[:8],
        "sentence_count": len(results)
    }

# ---------------------------
# PDF REPORT
# ---------------------------


def generate_pdf_report(scan_result: dict) -> str:
    report_path = "authentiscan_report.pdf"
    doc = SimpleDocTemplate(report_path, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    title = Paragraph("<b>Authentiscan Plagiarism Report</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 20))

    overall = Paragraph(f"<b>Overall Similarity:</b> {scan_result['overall_similarity']}%", styles['BodyText'])
    elements.append(overall)
    elements.append(Spacer(1, 15))

    for item in scan_result["details"]:
        paragraph = Paragraph(
            f"""
            <b>Sentence:</b> {item['sentence']}<br/>
            <b>AI Score:</b> {item['ai_score']}%<br/>
            <b>Web Score:</b> {item['web_score']}%<br/>
            <b>Final Score:</b> {item['final_score']}%<br/>
            <b>Status:</b> {item['status']}
            """,
            styles['BodyText']
        )
        elements.append(paragraph)
        elements.append(Spacer(1, 15))

    doc.build(elements)
    return report_path

# ---------------------------
# ROUTES
# ---------------------------


@app.get("/")
def serve_frontend():
    frontend_path = BASE_DIR / "index.html"
    return FileResponse(frontend_path)


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)

# ---------------------------
# SCAN (text) ROUTE
# ---------------------------


@app.post("/scan")
@limiter.limit("10/minute")
def scan_text(request: Request, body: TextRequest, db: Session = Depends(get_db)):
    """
    Analyze provided text, save a ScanHistory record, and return analysis result.
    """
    # compute analysis result first
    result = analyze_text(body.text)

    # create and persist scan record
    try:
        scan_record = ScanHistory(
            submitted_text=body.text,
            overall_similarity=result.get("overall_similarity", 0),
            created_at=datetime.datetime.utcnow()
        )
        db.add(scan_record)
        db.commit()
        db.refresh(scan_record)
    except Exception as e:
        logger.error(f"Failed to save scan record: {e}")
        db.rollback()
        # still return analysis result even if DB save fails
    return result

# ---------------------------
# FILE SCAN
# ---------------------------


@app.post("/upload")
@limiter.limit("10/minute")
async def upload_file(request: Request, file: UploadFile = File(...)):
    filename = file.filename.lower()
    file_bytes = await file.read()
    validate_file(filename, file_bytes)

    text = ""
    if filename.endswith(".pdf"):
        text = extract_pdf_text(file_bytes)
    elif filename.endswith(".docx"):
        text = extract_docx_text(file_bytes)
    elif filename.endswith(".txt"):
        text = file_bytes.decode("utf-8", errors="ignore")
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    if not text.strip():
        raise HTTPException(status_code=400, detail="No readable text found")

    return analyze_text(text)

# ---------------------------
# REPORT ROUTE
# ---------------------------


@app.post("/generate-report")
@limiter.limit("10/minute")
def generate_report(request: Request, body: TextRequest):
    result = analyze_text(body.text)
    pdf_path = generate_pdf_report(result)
    return FileResponse(pdf_path, media_type="application/pdf", filename="Authentiscan_Report.pdf")

# ---------------------------
# START SERVER
# ---------------------------


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
