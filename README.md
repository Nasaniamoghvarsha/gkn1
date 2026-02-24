# GKN Aerospace RAG & Agentic Assistant

A production-grade RAG (Retrieval-Augmented Generation) system designed for GKN Aerospace infrastructure and configuration analysis. Features multi-format ingestion, agentic self-correcting code generation, and a dedicated VS Code extension.

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Python 3.9+**
- **Node.js 18+** (for IDE Extension)
- **PostgreSQL 15+** with the `pgvector` extension.
- **Ollama**: Required for local LLM inference.
  - Pull the model: `ollama pull llama3.1:8b-instruct-q4_K_M`

### 2. Backend Setup
```powershell
# Install dependencies
pip install -r requirements.txt

# Configure environment
# Ensure .env exists with your DB_URL and MODEL_NAME
cp .env.dev .env 

# Initialize Database Schema
$env:PYTHONPATH="."
python src/setup_db.py
```

### 3. Running the System
```powershell
# Start the FastAPI Gateway
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload
```

### 4. Developer CLI Usage
The `gkn.py` tool allows interaction via terminal:
```powershell
# Check Health
python gkn.py health

# Ingest Documents
python gkn.py ingest technical_docs.docx

# Ask Questions
python gkn.py ask "What is the ITAR policy?"

# Generate Validated Code
python gkn.py generate "Create a docker-compose for the RAG system" --lang yaml
```

### 5. IDE Extension Setup
1. Open the `gkn-ide-extension` folder in VS Code.
2. Run `npm install` followed by `npm run compile`.
3. Press **F5** to launch the Extension Development Host.
4. Open the **GKN AI** icon in the sidebar to start chatting.

## 🛠 Features
- **Smart Parsers**: DOCX, PPTX, YAML, and JSON with metadata preservation.
- **Agentic Loop**: Uses LangGraph to automatically fix syntax errors in generated code.
- **Hybrid Search**: Semantic search powered by `psycopg2` and `pgvector`.
- **Deduplication**: Content-hash based ingestion to prevent data bloat.

## 📁 Project Structure
- `src/api/`: FastAPI Gateway endpoints.
- `src/graph/`: LangGraph orchestrator for agentic loops.
- `src/parsers/`: Domain-specific document parsers.
- `gkn-ide-extension/`: TypeScript-based VS Code extension source.
- `gkn.py`: Unified Developer CLI.
