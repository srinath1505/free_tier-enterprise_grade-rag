# 🚀 Enterprise RAG Platform (Zero-Cost & Secure)

A production-grade, highly accurate **Retrieval Augmented Generation (RAG)** system designed to run entirely on **free-tier infrastructure** while delivering enterprise features like security, observability, and advanced retrieval techniques.

## ✨ Key Features

### 🧠 Advanced RAG Engine
*   **Hybrid Search**: Combines **Vector Search** (FAISS) and **Keyword Search** (BM25) using **Weighted Reciprocal Rank Fusion (RRF)**. Tunable `alpha` parameter.
*   **Query Expansion**: Automatically generates multiple variations of user queries to maximize recall (Multi-Query Retrieval).
*   **Reranking**: Uses a Cross-Encoder (`ms-marco-TinyBERT-L-2-v2`) to re-score retrieved documents for high precision.
*   **Zero-Cost LLM**: Powered by **Hugging Face Inference API** (Serverless) using models like `Phi-3` or `Mistral-7B`.

### 🛡️ Enterprise Security
*   **Zero Trust Architecture**: JWT-based Authentication.
*   **RBAC**: Role-Based Access Control (Admin/User).
*   **Guardrails**: Input sanitization (PII redaction) and Output validation (Hallucination detection).

### 📊 Observability
*   **Full Telemetry**: Integrated with **LangSmith** for deep tracing.
*   **Custom Metrics**: Logs latency, token usage, and retrieval quality (`f1`, `relevance`).
*   **Alerting**: Automated alerts for high latency or hallucination spikes.

### 💻 Modern Frontend
*   **Streamlit + Shadcn UI**: A stunning, glassmorphism-styled chat interface.
*   **Interactive Controls**: Adjustable sliders for `Top-K` and `Hybrid Alpha`.

## 🛠️ Tech Stack

*   **Backend**: FastAPI, Pydantic, Python 3.10
*   **Frontend**: Streamlit, Streamlit-Shadcn-UI
*   **Vector DB**: FAISS (Local/Disk-persisted)
*   **LLM Orchestration**: LangChain, HuggingFace Hub
*   **Deployment**: Docker (Render), Hugging Face Spaces

## 🚀 Getting Started

### Prerequisites
*   Python 3.10+
*   Hugging Face API Token
*   (Optional) LangSmith API Key

### Local Installation

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/srinath1505/free_tier-enterprise_grade-rag.git
    cd free_tier-enterprise_grade-rag
    ```

2.  **Install Backend Dependencies**
    ```bash
    python -m venv venv
    source venv/bin/activate  # or venv\Scripts\activate on Windows
    pip install -r requirements.txt
    ```

3.  **Configure Environment**
    Copy `.env.example` to `.env` and fill in your keys:
    ```ini
    HF_TOKEN=hf_...
    LLM_PROVIDER=hf
    ```

4.  **Run Backend**
    ```bash
    uvicorn backend.main:app --reload
    ```

5.  **Run Frontend**
    ```bash
    cd frontend
    pip install -r requirements.txt
    streamlit run app.py
    ```

## ☁️ Deployment Guide

### 1. Backend (Render)
1.  Fork/Clone this repo.
2.  Create a **New Web Service** on [Render](https://render.com/).
3.  Select your repo.
4.  **Runtime**: Docker.
5.  **Environment Variables**: Add `HF_TOKEN`, `LLM_PROVIDER=hf`.
6.  Deploy! Copy the URL (e.g., `https://my-rag.onrender.com`).

### 2. Frontend (Hugging Face Spaces)
1.  Create a new **Streamlit Space** on Hugging Face.
2.  Upload the contents of the `frontend/` folder to the root of the Space.
3.  Go to **Settings** > **Variables and secrets**.
4.  Add Secret `BACKEND_URL` = `https://my-rag.onrender.com/api/v1`.

---
*Built by [Srinath](https://github.com/srinath1505)*
