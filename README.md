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

* **Easy Swap-Ability:** Because the logic is modular, you can transition from "Free-Tier" to "Global-Scale" in minutes by simply updating your `.env` config:
    * **Vector Store:** Swap local **FAISS** for **Pinecone** or **Milvus** for managed, billion-scale vector search.
    * **LLM Provider:** Move from **Hugging Face Serverless** to **OpenAI (GPT-4o)**, **Anthropic (Claude 3.5)**, or **Azure OpenAI** with zero code changes in the core engine.
    * **Scalability:** FastAPI’s asynchronous nature allows the platform to handle high concurrency, making it ready to be containerized and deployed on Kubernetes or AWS Lambda.

> **Why this matters:** This project is a proof-of-concept for "Cost-First Development." Build and validate your business logic for $0, then scale to paid enterprise providers only when your traffic justifies the cost.

---

## 🧠 Advanced Retrieval Architecture

Standard RAG often fails due to poor relevance. This platform uses a multi-stage pipeline to ensure the LLM receives the most pertinent context:

* **Hybrid Search (Dense + Sparse):** Combines the semantic power of **FAISS** (Vector) with the keyword precision of **BM25**. 
* **Weighted RRF (Reciprocal Rank Fusion):** Merges search results using a tunable `alpha` parameter to balance "meaning" vs. "keyword" matching.
* **Multi-Query Expansion:** Generates multiple variations of the user's prompt to maximize recall.
* **State-of-the-Art Reranking:** Implements a **Cross-Encoder** (`ms-marco-TinyBERT`) to re-score documents, significantly reducing hallucinations.

---

## 🛡️ Enterprise-Grade Security & Guardrails

* **Zero-Trust Auth:** Secure API access via **JWT (JSON Web Tokens)** and **RBAC (Role-Based Access Control)**.
* **PII Redaction:** Automated input sanitization ensures sensitive data never hits the LLM provider.
* **Hallucination Detection:** Output validation layers to ensure factual grounding.

---

## 📊 Observability & Telemetry

Integrated with **LangSmith** for full-stack tracing:
* **Latency Tracking:** Monitor retrieval vs. generation time.
* **Cost Analysis:** Token usage logging to project future scale.
* **Quality Metrics:** Logs F1, Relevancy, and Faithfulness scores.

---

## 🛠️ Tech Stack

| Layer | Technology | Why? |
| :--- | :--- | :--- |
| **Backend** | FastAPI / Pydantic | Async performance and modular "Swap-ready" endpoints. |
| **Frontend** | Streamlit + Shadcn | Professional "Glassmorphism" UI with low dev overhead. |
| **Vector Engine**| FAISS | Disk-persisted, high-speed local search (Zero Cost). |
| **Inference** | Hugging Face Hub | Serverless, high-performance LLMs without API fees. |

---

## ⚡ Getting Started

Launch your own RAG platform in under 5 minutes.

### Prerequisites
*   Python 3.10+
*   Git

### 1. Clone & Setup
```bash
git clone https://github.com/srinath1505/free_tier-enterprise_grade-rag.git
cd free_tier-enterprise_grade-rag

# Create Virtual Environment (Recommended)
python -m venv venv
# Windows
.\venv\Scripts\Activate
# Linux/Mac
source venv/bin/activate

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

### 3. Ingest Your Data
Place your PDF, DOCX, or TXT files in the `data/` folder.
```bash
# Run the ingestion pipeline
python ingestion/ingest.py
```

### 4. Run the Platform
Open two terminals:

**Terminal 1 (Backend API)**
```bash
uvicorn backend.main:app --reload
```

**Terminal 2 (Frontend UI)**
```bash
streamlit run frontend/app.py
```
Visit `http://localhost:8501` and start chatting!

---

## 🗺️ Roadmap & Future Scope

This project is evolving. Our goal is to match the feature set of high-end enterprise platforms.

* **Evaluation Framework:** Integration of **RAGAS** or **Arize Phoenix** for automated, LLM-assisted quality scoring (Faithfulness, Answer Relevance).
* **Persistent Memory:** Implementing a **PostgreSQL/Redis** layer for long-term "User Memory" and chat history persistence beyond a single session.
* **Intelligent Document Parsing:** Moving beyond basic loaders to handle complex PDFs (multi-column text, tables, and images) using **Unstructured.io**.
* **Advanced Guardrails:** Deep integration with NeMo Guardrails for stricter conversational safety.

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1.  Fork the repository
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

---

## 👨‍💻 Built By

**Srinath Selvakumar**  
*Engineering accessible AI solutions.*

Crafted with intensity and engineered for scale. 🚀
