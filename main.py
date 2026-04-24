from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer, util
import os

app = FastAPI()

# Enable CORS (allow frontend to talk to backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Use a LIGHTWEIGHT model (important for Render free tier)
MODEL_NAME = "paraphrase-MiniLM-L3-v2"

model = None
db_embeddings = None

# Small internal dataset (can expand later)
documents_db = [
    "Artificial intelligence is transforming education.",
    "Machine learning improves plagiarism detection systems.",
    "Natural language processing helps detect paraphrased content."
]


# Lazy load model (prevents startup crash)
def get_model():
    global model
    if model is None:
        model = SentenceTransformer(MODEL_NAME)
    return model


# Precompute embeddings only when needed
def get_db_embeddings():
    global db_embeddings
    if db_embeddings is None:
        model_instance = get_model()
        db_embeddings = model_instance.encode(
            documents_db, convert_to_tensor=True
        )
    return db_embeddings


class TextRequest(BaseModel):
    text: str


@app.get("/")
def home():
    return {"message": "Authentiscan API is LIVE"}


@app.post("/scan")
def scan_text(request: TextRequest):
    text = request.text.strip()

    if not text:
        return {"error": "No text provided"}

    model_instance = get_model()
    db_embeds = get_db_embeddings()

    sentences = [s.strip() for s in text.split(".") if s.strip()]

    results = []

    for sentence in sentences:
        input_embedding = model_instance.encode(
            sentence, convert_to_tensor=True
        )
        scores = util.cos_sim(input_embedding, db_embeds)

        max_score = float(scores.max()) * 100

        if max_score > 75:
            status = "High similarity"
        elif max_score > 40:
            status = "Moderate similarity"
        else:
            status = "Low similarity"

        results.append({
            "sentence": sentence,
            "score": round(max_score, 2),
            "status": status
        })

    overall_score = (
        sum(r["score"] for r in results) / len(results)
        if results else 0
    )

    return {
        "overall_similarity": round(overall_score, 2),
        "details": results
    }


# Required for Render to bind correctly
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
