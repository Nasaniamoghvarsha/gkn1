import os
import shutil
import uuid
import time
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager

from src.db import DatabaseConnection
from src.embedder import Embedder
from src.query import RAGQuery
from src.ingest import ingest_file

# Configuration
INGESTION_DIR = "data/ingestion"
os.makedirs(INGESTION_DIR, exist_ok=True)

class QueryRequest(BaseModel):
    question: str
    file_type_filter: Optional[str] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize shared resources
    db_conn = DatabaseConnection() # Managed as a context manager internally usually, but here we keep it open
    # Note: src.db.DatabaseConnection is designed as a context manager.
    # We will create an instance and keep it active if possible, or create a pool.
    # For this implementation, we'll instantiate the dependencies.
    
    app.state.embedder = Embedder()
    app.state.db_manager = db_conn
    
    # We need an active connection for RAGQuery
    # Since DatabaseConnection() returns an object that opens connection on __enter__
    # we will manually open it here for the app lifecycle.
    app.state.conn = app.state.db_manager.__enter__()
    app.state.rag = RAGQuery(app.state.conn, app.state.embedder)
    
    yield
    
    # Shutdown logic
    app.state.db_manager.__exit__(None, None, None)

app = FastAPI(
    title="GKN Aerospace RAG Gateway",
    description="API for multi-format document ingestion and RAG-based querying.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", include_in_schema=False)
async def root_redirect():
    """Redirects the root URL to the interactive API documentation."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")

@app.get("/health")
async def health_check():
    """Returns the health status of the API and its dependencies."""
    model_name = os.getenv("MODEL_NAME", "unknown")
    return {
        "status": "healthy",
        "db": "connected",
        "model": model_name,
        "timestamp": time.time()
    }

@app.post("/ingest")
async def ingest_document(file: UploadFile = File(...)):
    """Uploads and ingests a document into the RAG system."""
    file_path = os.path.join(INGESTION_DIR, file.filename)
    
    try:
        # Save file temporarily
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Call ingestion core
        result = ingest_file(
            file_path, 
            app.state.conn, 
            app.state.embedder
        )
        
        return {
            "filename": file.filename,
            "status": result["status"],
            "chunks_created": result.get("chunks_created", 0),
            "error": result.get("error")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # We keep the file in data/ingestion as a record/cache as per Phase 1 logic
        pass

@app.post("/query")
async def query_rag(request: QueryRequest):
    """Performs a non-streaming RAG query."""
    try:
        result = app.state.rag.ask(
            request.question, 
            file_type_filter=request.file_type_filter
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query/stream")
async def query_rag_stream(request: QueryRequest):
    """Performs a streaming RAG query."""
    try:
        def stream_generator():
            for chunk in app.state.rag.ask_streaming(
                request.question, 
                file_type_filter=request.file_type_filter
            ):
                import json
                if isinstance(chunk, str):
                    yield chunk
                else:
                    # Final metadata chunk
                    yield "\n\n" + json.dumps(chunk)

        return StreamingResponse(stream_generator(), media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from src.graph.orchestrator import app_graph

# ... (rest of imports)

class AgentRequest(BaseModel):
    question: str
    language: str

# ... (rest of config)

@app.post("/generate/agent")
async def generate_with_agent(request: AgentRequest):
    """
    Invokes the LangGraph orchestrator to generate validated code.
    """
    initial_state = {
        "question": request.question,
        "language": request.language,
        "context_chunks": [],
        "generated_code": "",
        "validation_errors": [],
        "iteration_count": 0,
        "is_incomplete": False
    }
    
    try:
        # Run the graph
        final_state = await app_graph.ainvoke(initial_state)
        
        return {
            "question": request.question,
            "generated_code": final_state["generated_code"],
            "iteration_count": final_state["iteration_count"],
            "is_incomplete": final_state["is_incomplete"],
            "errors": final_state["validation_errors"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
