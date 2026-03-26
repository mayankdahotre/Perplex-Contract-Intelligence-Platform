# ⬡ Perplex — Contract Intelligence Platform

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-black.svg)](https://flask.palletsprojects.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-green.svg)](https://openai.com/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An end-to-end LLM-powered contract analysis platform that extracts key clauses, identifies legal risks, and enables natural language Q&A over legal contracts. Built with Flask, OpenAI GPT-4, and FAISS vector search.

![Perplex Demo](https://via.placeholder.com/800x400/1e2330/ffffff?text=Perplex+Contract+Analysis+Demo)

## ✨ Features

- **📄 PDF Ingestion** — Advanced PDF parsing with layout-aware text extraction and semantic chunking
- **🤖 RAG Q&A** — Ask questions in plain English; get answers grounded in retrieved contract passages
- **📋 Clause Extraction** — Automated classification of 10+ clause types (termination, payment, confidentiality, IP, etc.)
- **⚠️ Risk Scoring** — Structured 0–100 risk score across 8 legal risk categories with detailed flag annotations
- **📊 Executive Summary** — LLM-generated plain-English contract overview
- **🔍 Vector Search** — FAISS-backed embedding index with cosine similarity retrieval and threshold calibration
- **🎨 Modern UI** — Clean, responsive web interface with real-time analysis progress
- **⚡ Fast Processing** — Background analysis pipeline with status polling

## 🏗️ Architecture

```
perplex/
├── app.py                          # Flask app factory + entry point
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment configuration template
├── README.md                       # This file
│
├── backend/
│   ├── routes/
│   │   ├── contract_routes.py      # Upload, list, get, delete contracts
│   │   ├── query_routes.py         # RAG Q&A + summarization
│   │   └── health_routes.py        # Health check endpoint
│   │
│   └── services/
│       ├── ingestion_service.py    # PDF parsing, cleaning, chunking
│       ├── embedding_service.py    # OpenAI embeddings + FAISS store
│       ├── clause_service.py       # Clause extraction & classification
│       ├── risk_service.py         # Risk scoring & flagging
│       ├── query_service.py        # RAG Q&A + summarization
│       └── contract_store.py       # JSON-based persistence layer
│
├── frontend/
│   ├── templates/index.html        # Single-page app shell
│   └── static/
│       ├── css/main.css            # Design system + component styles
│       └── js/app.js               # Frontend application logic
│
└── data/                           # Runtime data (created automatically)
    ├── uploads/                    # Uploaded PDF files
    ├── indexes/                    # FAISS vector indexes + metadata
    └── contracts.json              # Contract metadata store
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+**
- **OpenAI API Key** (for LLM features)
- **32MB+ RAM** (for embedding processing)

### 1. Clone & Install

```bash
# Clone the repository
git clone https://github.com/yourusername/perplex.git
cd perplex

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env
```

Edit `.env` and add your OpenAI API key:

```env
# Required: Your OpenAI API key
OPENAI_API_KEY=sk-your-actual-api-key-here

# Optional: Customize models and settings
OPENAI_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
SIMILARITY_THRESHOLD=0.35
RETRIEVAL_TOP_K=6
```

### 3. Run the Application

```bash
# Start the Flask development server
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser!

## 📖 Usage

### Basic Workflow

1. **Upload Contract** — Drag & drop or browse to upload PDF contracts
2. **Wait for Analysis** — Real-time progress tracking for ingestion, embedding, clause extraction, and risk scoring
3. **Explore Results** — View executive summary, extracted clauses, risk assessment, and ask questions
4. **Q&A** — Ask natural language questions about the contract

### Example Questions

- "What are the termination conditions?"
- "What is the payment schedule?"
- "Who owns the intellectual property?"
- "What happens in case of a dispute?"
- "Are there any unusual risk clauses?"

## 🔧 API Reference

### Health Check

```http
GET /health
```

Returns service status and configuration.

### Contracts

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/contracts/upload` | Upload PDF contract (multipart/form-data, field: `file`) |
| `GET` | `/api/contracts/` | List all uploaded contracts |
| `GET` | `/api/contracts/<doc_id>` | Get contract with full analysis results |
| `GET` | `/api/contracts/<doc_id>/status` | Poll analysis status during processing |
| `DELETE` | `/api/contracts/<doc_id>` | Delete contract and associated data |

### Query

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/query/<doc_id>` | Ask questions about a contract |
| `POST` | `/api/query/<doc_id>/summarize` | Regenerate contract summary |

#### Example: Upload Contract

```bash
curl -X POST -F "file=@contract.pdf" http://localhost:5000/api/contracts/upload
```

#### Example: Ask Question

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"question": "What are the payment terms?"}' \
  http://localhost:5000/api/query/abc123
```

## 🛠️ Technology Stack

- **Backend**: Python 3.8+, Flask 3.0+
- **AI/ML**: OpenAI GPT-4, text-embedding-3-small, FAISS
- **PDF Processing**: PyPDF2, pdfplumber, langchain-text-splitters
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **Data Storage**: JSON file-based (easily replaceable with PostgreSQL/Redis)
- **Deployment**: Gunicorn (production), Docker-ready

## 🔍 Supported Clause Types

Perplex automatically extracts and classifies:

- **Termination** — End conditions and procedures
- **Payment** — Terms, amounts, schedules, penalties
- **Confidentiality** — Non-disclosure obligations
- **Indemnification** — Liability and indemnity provisions
- **Limitation of Liability** — Damage caps and exclusions
- **Intellectual Property** — Ownership, licensing, assignments
- **Dispute Resolution** — Arbitration, litigation, mediation
- **Force Majeure** — Excused performance events
- **Renewal & Duration** — Term length and renewal conditions
- **Warranties** — Guarantees and representations

## ⚠️ Risk Categories

Comprehensive risk assessment across:

- **Termination Risk** — Exit and cancellation exposure
- **Financial Risk** — Payment and monetary exposure
- **IP Risk** — Intellectual property concerns
- **Liability Risk** — Indemnification and legal exposure
- **Compliance Risk** — Regulatory and legal compliance
- **Confidentiality Risk** — Information security exposure
- **Dispute Risk** — Litigation and arbitration exposure
- **Operational Risk** — Performance and delivery concerns

## 🐛 Troubleshooting

### Common Issues

**"ModuleNotFoundError"**
```bash
# Ensure virtual environment is activated
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux

# Reinstall dependencies
pip install -r requirements.txt
```

**"OpenAI API Key Error"**
- Verify your API key in `.env` file
- Check your OpenAI account has credits
- Ensure the key has proper permissions

**"PDF Processing Fails"**
- Ensure PDF is not password-protected
- Check PDF is not corrupted
- Try with a different PDF file

**"Port 5000 Already in Use"**
```bash
# Kill process using port 5000
# Windows:
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# macOS/Linux:
lsof -ti:5000 | xargs kill -9
```

### Performance Tips

- **Large PDFs**: Increase `CHUNK_SIZE` in `.env` for better processing
- **Memory Usage**: Monitor RAM usage during embedding (uses ~1GB per 100 pages)
- **API Costs**: Monitor OpenAI usage in your dashboard

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/amazing-feature`
3. **Commit** your changes: `git commit -m 'Add amazing feature'`
4. **Push** to the branch: `git push origin feature/amazing-feature`
5. **Open** a Pull Request

### Development Setup

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest

# Format code
black .
isort .
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **OpenAI** for GPT-4 and embedding models
- **FAISS** by Facebook Research for vector search
- **Flask** community for the excellent web framework
- **pdfplumber** for robust PDF text extraction

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/perplex/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/perplex/discussions)
- **Email**: your.email@example.com

---

**Built with ❤️ for legal professionals and contract analysts**

*Transform complex contracts into actionable insights with the power of AI.*

### Query

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/query/<doc_id>` | Ask a question (body: `{ question, chat_history? }`) |
| `POST` | `/api/query/<doc_id>/summarize` | Re-generate summary |

### Analysis Pipeline Status Values

| Status | Meaning |
|--------|---------|
| `indexing` | Building FAISS vector index |
| `extracting_clauses` | LLM clause extraction |
| `scoring_risk` | LLM risk scoring |
| `summarizing` | Generating executive summary |
| `ready` | All analysis complete |
| `error` | Pipeline failed |

---

## Configuration

All tunable parameters via `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_MODEL` | `gpt-4o` | LLM for analysis |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `CHUNK_SIZE` | `1000` | Characters per chunk |
| `CHUNK_OVERLAP` | `200` | Overlap between chunks |
| `RETRIEVAL_TOP_K` | `6` | Chunks retrieved per query |
| `SIMILARITY_THRESHOLD` | `0.35` | Min cosine similarity for retrieval |
| `RISK_SCORE_HIGH_THRESHOLD` | `70` | Score above = high risk |
| `RISK_SCORE_MEDIUM_THRESHOLD` | `40` | Score above = medium risk |

---

## Supported Clause Types

| Type | Description |
|------|-------------|
| Termination | Exit conditions and notice requirements |
| Payment | Fees, schedules, late penalties |
| Confidentiality | NDA and data protection obligations |
| Indemnification | Liability and hold-harmless clauses |
| Limitation of Liability | Damage caps and exclusions |
| Intellectual Property | Ownership, licensing, work-for-hire |
| Dispute Resolution | Arbitration, jurisdiction, governing law |
| Force Majeure | Extraordinary event excuses |
| Renewal & Duration | Contract term, auto-renewal |
| Warranties | Guarantees and representations |

---

## Production Deployment

```bash
# Using Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

**Production checklist:**
- Replace JSON store (`contract_store.py`) with PostgreSQL
- Use Redis for background task queue instead of threads
- Store uploaded PDFs in S3 / GCS
- Set `SECRET_KEY` to a strong random value
- Enable HTTPS

---

## Tech Stack

- **Backend**: Flask 3, Python 3.11+
- **LLM**: OpenAI GPT-4o (chat completions + structured JSON outputs)
- **Embeddings**: OpenAI `text-embedding-3-small` (1536-dim)
- **Vector Store**: FAISS (IndexFlatIP with L2 normalization for cosine similarity)
- **PDF Parsing**: pdfplumber + PyPDF2
- **Chunking**: LangChain RecursiveCharacterTextSplitter
- **Frontend**: Vanilla JS + CSS custom properties, no build step required
