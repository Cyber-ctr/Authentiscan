from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer, util
import requests
import os

# Set Hugging Face token if available (optional for higher rate limits)
# os.environ["HF_TOKEN"] = "your_huggingface_token_here"  # Uncomment and set your token
if "HF_TOKEN" not in os.environ:
    os.environ["HF_TOKEN"] = ""  # Suppress warning for unauthenticated requests

app = FastAPI()

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


def get_model():
    global model
    if model is None:
        model = SentenceTransformer(MODEL_NAME)
    return model


def get_db_embeddings():
    global db_embeddings
    if db_embeddings is None:
        model_instance = get_model()
        db_embeddings = model_instance.encode(
            documents_db, convert_to_tensor=True
        )
    return db_embeddings


# ----------------------------
# 🌍 SIMPLE WEB CHECKING (MVP SAFE)
# ----------------------------
def web_search(query):
    try:
        url = f"https://duckduckgo.com/html/?q={query}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(res.text, "html.parser")

        results = soup.find_all("a", class_="result__a")
        return [r.get_text() for r in results[:5]]
    except Exception:
        return []


class TextRequest(BaseModel):
    text: str


@app.get("/")
def serve_frontend():
    return FileResponse("index.html")


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@app.post("/scan")
def scan_text(request: TextRequest):
    text = request.text.strip()

    model_instance = get_model()
    db_embeds = get_db_embeddings()

    sentences = [s.strip() for s in text.split(".") if s.strip()]

    results = []
    web_matches = []

    for sentence in sentences:
        emb = model_instance.encode(sentence, convert_to_tensor=True)
        scores = util.cos_sim(emb, db_embeds)

        ai_score = float(scores.max()) * 100

        # 🌍 Web check (light)
        web_results = web_search(sentence)
        web_matches.extend(web_results)

        # Simple keyword overlap boost
        web_score = min(len(web_results) * 10, 40)

        final_score = min(ai_score + web_score, 100)

        if final_score > 75:
            status = "High similarity"
        elif final_score > 40:
            status = "Moderate similarity"
        else:
            status = "Low similarity"

        results.append({
            "sentence": sentence,
            "ai_score": round(ai_score, 2),
            "web_score": web_score,
            "final_score": round(final_score, 2),
            "status": status
        })

    overall = (
        sum(r["final_score"] for r in results) / len(results)
        if results else 0
    )

    return {
        "overall_similarity": round(overall, 2),
        "details": results,
        "web_sources": list(set(web_matches))[:8]
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
