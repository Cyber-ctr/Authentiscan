from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer, util

app = FastAPI()

# Allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Sample database
documents_db = [
    "Artificial intelligence is transforming education.",
    "Machine learning improves plagiarism detection systems.",
    "Natural language processing helps detect paraphrased content."
]

db_embeddings = model.encode(documents_db, convert_to_tensor=True)


class TextRequest(BaseModel):
    text: str


@app.get("/")
def home():
    return {"message": "Authentiscan API running"}


@app.post("/scan")
def scan_text(request: TextRequest):
    input_text = request.text

    sentences = input_text.split(".")
    results = []

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        input_embedding = model.encode(sentence, convert_to_tensor=True)
        scores = util.cos_sim(input_embedding, db_embeddings)

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
