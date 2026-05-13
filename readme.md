# Authentiscan 🚀

## AI-Powered Plagiarism Detection for Academic & Professional Integrity

---

## 📌 Overview

Authentiscan is an AI-driven plagiarism detection platform designed to identify both direct copying and subtle paraphrasing in written content. Built using modern NLP techniques, it provides fast, accurate, and user-friendly similarity analysis for students, educators, and professionals.

This project represents the **MVP (Minimum Viable Product)** of a scalable SaaS platform aimed at transforming academic integrity and content authenticity.

---

## ✨ Features

* 🔍 **Semantic Similarity Detection**
  Detects paraphrased and reworded content using transformer-based embeddings.

* ⚡ **Fast Analysis**
  Returns results in seconds with lightweight AI models.

* 🧠 **Sentence-Level Breakdown**
  Provides similarity scores for each sentence.

* 🌐 **Basic Web Source Matching**
  Retrieves possible related content from online search results.

* 🎨 **Simple Web Interface**
  Clean UI with color-coded similarity indicators (High, Medium, Low).

* 📎 **File Upload Support**
  Upload PDF, DOCX, or TXT documents for analysis.

* 🔐 **Privacy-Friendly (MVP Level)**
  Processes text without permanent storage (no database yet).

---

## 🏗️ Architecture

Authentiscan follows a simple client-server architecture:

* **Frontend**: HTML, CSS, JavaScript
* **Backend**: Python (FastAPI)
* **AI Engine**: Sentence Transformers (NLP embeddings)
* **Deployment**: Cloud-hosted (e.g., Render)

---

## 🧰 Tech Stack

* **Backend Framework**: FastAPI
* **AI/NLP**: Sentence Transformers (Hugging Face)
* **Language**: Python
* **Frontend**: HTML, CSS, JavaScript
* **Deployment**: Render / Cloud platforms
* **Libraries**:

  * fastapi
  * uvicorn
  * sentence-transformers
  * torch
  * requests
  * beautifulsoup4

---

## ⚙️ Installation & Setup

### 1. Open the local workspace

This project is available locally at:

```bash
cd "c:\Users\PRINCE_E.K.E.N.U\Desktop\Authentiscan"
```

If you are working from a cloned repo, use the repo root instead.

### 2. Create a virtual environment (optional but recommended)

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the backend server

```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 10000
```

Then open your browser at:

```bash
http://localhost:10000
```

If you are using the provided virtual environment, activate it first:

```bash
.\.venv\Scripts\Activate.ps1
```

## 🚀 Usage

1. Paste or type text into the input box
2. Click **Scan**
3. View:

   * Overall similarity score
   * Sentence-level analysis
   * Detected similarity levels
   * Possible web matches

---

## 📊 Example Output

* **Overall Similarity**: 68%
* Sentence Breakdown:

  * “AI is transforming education” → 82% (High)
  * “Students benefit from new tools” → 35% (Low)

---

## ⚠️ Limitations (MVP)

* Uses a **small internal dataset**
* Web search is **basic and not fully reliable**
* File upload support is available for PDF, DOCX, and TXT
* No user accounts or saved history
* Not production-grade accuracy (yet)

---

## 🔮 Future Improvements

* 📂 Expanded file upload support and document parsing improvements
* 🧑‍💻 User authentication system
* 🗄️ Database for storing scans
* 🌍 Large-scale web & academic corpus integration
* 🤖 AI-generated content detection
* 🔗 LMS integrations (Moodle, Canvas, etc.)
* 📈 Advanced analytics dashboard

---

## 🎯 Vision

To evolve Authentiscan into a **global AI-powered academic integrity platform**, offering:

* Real-time plagiarism detection
* Cross-language analysis
* Institutional analytics
* Secure and privacy-first infrastructure

---

## 🤝 Contributing

This is an early-stage project. Contributions, feedback, and suggestions are welcome.

---

## 📄 License

This project is currently unlicensed (for development and testing purposes). A proper license will be added in future releases.

---

## 👤 Author

**EKENU STEVE MBAH**
**B-Tech in Software Engineering**
Founder, Authentiscan

---

## 💡 Final Note

Authentiscan is not just a plagiarism checker—
it is the foundation of a next-generation **AI integrity ecosystem**.
