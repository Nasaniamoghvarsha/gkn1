import os
import httpx
import json
from typing import List, Dict, Any, TypedDict, Annotated, Optional
from langgraph.graph import StateGraph, END

from src.db import DatabaseConnection
from src.embedder import Embedder
from src.query import RAGQuery
from src.validators.code_validator import CodeValidator

class AgentState(TypedDict):
    question: str
    context_chunks: List[Dict[str, Any]]
    generated_code: str
    language: str
    validation_errors: List[Dict[str, Any]]
    iteration_count: int
    is_incomplete: bool

# Initialize components
# Note: In a real app, these might be passed in, but for the graph nodes we'll use state-based initialization or global refs
# or we'll pass the app.state refs during invocation.
# Since LangGraph nodes are usually top-level functions, we'll assume the environment provides access to DB/Embedder.

async def node_retrieve(state: AgentState):
    """Fetches relevant context from the RAG core."""
    # This node needs a DB connection and embedder.
    # For now, we'll initialize them within the node or use a global if necessary.
    # Better: Use the same logic as src/query.py
    
    # We'll re-instantiate for the node context, or assume the caller provides them.
    # Since we're running in FastAPI, we'll pass these via keys in the state or similar.
    # For simplicity here, we'll create a local connection.
    with DatabaseConnection() as conn:
        embedder = Embedder()
        rag = RAGQuery(conn, embedder)
        # We use retrieve directly to get metadata-rich chunks
        chunks = rag.retrieve(state["question"])
        return {"context_chunks": chunks}

async def node_generate(state: AgentState):
    """Generates code using Ollama with self-correction logic."""
    model_name = os.getenv("MODEL_NAME", "llama3.1:8b-instruct-q4_K_M")
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    
    # Format context
    context_text = "\n".join([f"Source: {c['filename']}\nContent: {c['content']}" for c in state["context_chunks"][:3]])
    
    # Construct Guardrailed Prompt
    system_prompt = (
        "You are an expert software engineer. "
        "Output ONLY the raw code. Do not include any explanations, apologies, or markdown formatting outside of the code block itself. "
        "If you are fixing prior errors, apply the fix and return the complete updated code."
    )
    
    user_prompt = f"Context:\n{context_text}\n\nLanguage: {state['language']}\nQuestion: {state['question']}\n\n"
    
    if state["validation_errors"]:
        user_prompt += "Your previous output had the following validation errors. Please fix them:\n"
        user_prompt += json.dumps(state["validation_errors"], indent=2)
        user_prompt += "\n\nUpdated Code:"

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False,
        "options": {"temperature": 0.2}
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{ollama_url}/api/chat", json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()
        raw_output = result['message']['content']
        
        return {
            "generated_code": raw_output,
            "iteration_count": state["iteration_count"] + 1
        }

async def node_validate(state: AgentState):
    """Validates the generated code."""
    validator = CodeValidator()
    result = await validator.validate(state["generated_code"], state["language"])
    
    # Keep the clean code in state for the final response
    return {
        "validation_errors": result["errors"],
        "generated_code": result.get("clean_code", state["generated_code"])
    }

def conditional_edge(state: AgentState):
    """Decides whether to loop back, end, or fail."""
    if not state["validation_errors"]:
        return END
    
    if state["iteration_count"] >= 5:
        # Mark as incomplete and end
        # Note: In LangGraph we update the state in the node.
        # But here we just return the next node name.
        return "mark_incomplete"
    
    return "generate"

async def node_mark_incomplete(state: AgentState):
    return {"is_incomplete": True}

# Build the Graph
workflow = StateGraph(AgentState)

workflow.add_node("retrieve", node_retrieve)
workflow.add_node("generate", node_generate)
workflow.add_node("validate", node_validate)
workflow.add_node("mark_incomplete", node_mark_incomplete)

workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", "validate")

workflow.add_conditional_edges(
    "validate",
    conditional_edge,
    {
        END: END,
        "generate": "generate",
        "mark_incomplete": "mark_incomplete"
    }
)
workflow.add_edge("mark_incomplete", END)

# Compile
app_graph = workflow.compile()
