# 🚀 Enterprise RAG Platform: Zero-Cost & Production-Ready

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-FF4B4B.svg)](https://streamlit.io/)

### **Democratizing Enterprise-Grade AI**
Most "Enterprise" RAG solutions require massive cloud budgets. This platform proves that you can deliver **highly accurate, secure, and observable** AI systems using entirely **free-tier infrastructure**. 

By orchestrating **Hybrid Search**, **Cross-Encoder Reranking**, and **Zero-Trust Security**, this project bridges the gap between a simple prototype and a production microservice.

---

## 🏗️ Scalability & Vendor-Agnostic Design

A core philosophy of this project is **Architectural Flexibility**. While it currently runs on 100% free-tier services to showcase cost-efficiency, the backend is built using a **Decoupled FastAPI Architecture**.

* **Easy Swap-Ability:** Because the logic is modular, you can transition from "Free-Tier" to "Global-Scale" in minutes by simply updating your `.env` config.
* **Scalability:** FastAPI’s asynchronous nature allows the platform to handle high concurrency, ready for containerization and K8s deployment.

> **Why this matters:** This project is a proof-of-concept for "Cost-First Development." Build and validate your business logic for $0, then scale to paid enterprise providers only when your traffic justifies the cost.

---

## ⭐ Key Features (V2.0)

### 1. Self-Service Knowledge Base 📂
*   **Drag-Drop Ingestion:** Admins can upload PDF/DOCX/TXT files directly from the UI.
*   **Instant Indexing:** Files are processed, chunked, and embedded into the Vector DB immediately.
*   **Management:** View list of documents and delete outdated files with one click.

### 2. Enterprise Authentication 🔐
*   **Persistent User Accounts:** User data is securely stored in `users.json`, surviving server restarts.
*   **Role-Based Access Control (RBAC):**
    *   **Admin:** Full access to Knowledge Base and System Settings.
    *   **Viewer:** Chat-only access.
*   **Self-Registration:** New users can sign up instantly via the login screen.

### 3. Advanced Retrieval Engine 🧠
*   **Hybrid Search (Dense + Sparse):** Combines **FAISS** (Vector) with **BM25** (Keyword).
*   **Weighted RRF:** Merges results for maximum relevance.
*   **Multi-Query Expansion:** Generates prompt variations to capture user intent.
*   **Cross-Encoder Reranking:** Re-scores documents using `ms-marco-TinyBERT` to reduce hallucinations.

---

## 🛠️ Tech Stack

| Layer | Technology | Why? |
| :--- | :--- | :--- |
| **Backend** | FastAPI / Pydantic | Async performance and modular endpoints. |
| **Frontend** | Streamlit + Shadcn | Professional "Glassmorphism" UI with Admin/Chat tabs. |
| **Vector Engine**| FAISS | High-speed local search (Zero Cost). |
| **Inference** | Hugging Face Hub | Serverless, high-performance LLMs. |
| **Auth** | JWT + OAuth2 | Secure, industry-standard authentication. |

---

## ⚡ Getting Started

Launch your own RAG platform in under 5 minutes.

### 1. Clone & Setup
```bash
git clone https://github.com/srinath1505/free_tier-enterprise_grade-rag.git
cd free_tier-enterprise_grade-rag

# Create Virtual Environment (Recommended)
python -m venv venv
.\venv\Scripts\Activate  # Windows
source venv/bin/activate # Linux/Mac

# Install Dependencies
pip install -r requirements.txt
```

### 2. Configuration
Copy the example environment file:
```bash
cp .env.example .env
```
Edit `.env` and add your **Hugging Face Token** (Get one [here](https://huggingface.co/settings/tokens)):
```ini
HF_TOKEN=hf_your_token_here
LLM_PROVIDER=hf
```

### 3. Run the Platform
Open two terminals:

**Terminal 1 (Backend API)**
```bash
uvicorn backend.main:app --reload
```

**Terminal 2 (Frontend UI)**
```bash
streamlit run frontend/app.py
```
Visit `http://localhost:8501` to login.

*   **Default Admin:** `admin` / `password`
*   **Or Register:** create a new account in the UI.

---

## 🗺️ Roadmap

* **Evaluation Framework:** Integration of **RAGAS** for automated scoring.
* **Persistent Memory:** PostgreSQL/Redis layer for chat history.
* **Intelligent Parsing:** Handling complex tables/images via Unstructured.io.

---

## 👨‍💻 Built By

**Srinath Selvakumar**  
*Engineering accessible AI solutions.*
