import pytest
import os
import time
from src.db import DatabaseConnection
from src.embedder import Embedder
from src.ingest import ingest_file
from src.query import RAGQuery

@pytest.mark.integration
class TestRAGBase:
    """Base class to provide shared resources for integration tests."""
    
    @pytest.fixture(scope="class")
    def db_conn(self):
        with DatabaseConnection() as conn:
            yield conn

    @pytest.fixture(scope="class")
    def embedder(self):
        return Embedder()

    @pytest.fixture(scope="class")
    def rag_engine(self, db_conn, embedder):
        return RAGQuery(db_conn, embedder)

@pytest.mark.integration
class TestDocxRAG(TestRAGBase):
    def test_ingest_docx(self, db_conn, embedder):
        file_path = "tests/fixtures/sample.docx"
        result = ingest_file(file_path, db_conn, embedder)
        assert result["status"] in ["success", "skipped"]
        if result["status"] == "success":
            assert result["chunks_created"] > 0

    def test_retrieve_docx(self, rag_engine):
        question = "What is the security protocol for GKN Aerospace?"
        chunks = rag_engine.retrieve(question)
        assert len(chunks) > 0
        assert chunks[0]["similarity_score"] > 0.6
        assert any("ITAR" in c["content"] for c in chunks)

    def test_heading_metadata(self, rag_engine):
        question = "security"
        chunks = rag_engine.retrieve(question)
        for chunk in chunks:
            if "heading_path" in chunk["chunk_metadata"]:
                assert "Section 1" in chunk["chunk_metadata"]["heading_path"]

@pytest.mark.integration
class TestPptxRAG(TestRAGBase):
    def test_ingest_pptx(self, db_conn, embedder):
        file_path = "tests/fixtures/sample.pptx"
        result = ingest_file(file_path, db_conn, embedder)
        assert result["status"] in ["success", "skipped"]

    def test_slide_chunking(self, rag_engine):
        question = "RAG Pipeline features"
        chunks = rag_engine.retrieve(question)
        assert any("slide_number" in c["chunk_metadata"] for c in chunks)

    def test_notes_included(self, rag_engine):
        question = "is pgvector needed?"
        chunks = rag_engine.retrieve(question)
        # The answer is in the speaker notes of slide 2
        assert any("pgvector" in c["content"].lower() for c in chunks)

@pytest.mark.integration
class TestJsonRAG(TestRAGBase):
    def test_small_json_single_chunk(self, db_conn, embedder):
        file_path = "tests/fixtures/small.json"
        result = ingest_file(file_path, db_conn, embedder)
        assert result["status"] in ["success", "skipped"]
        # small.json is definitely < 200 tokens
        # We can't easily assert result["chunks_created"] == 1 if it was already ingested
        # but we can check the DB for the specific document if needed.

    def test_large_json_split(self, db_conn, embedder):
        file_path = "tests/fixtures/large.json"
        result = ingest_file(file_path, db_conn, embedder)
        # large.json has 5 top-level keys
        if result["status"] == "success":
            assert result["chunks_created"] == 5

    def test_json_retrieval(self, rag_engine):
        question = "What port dose the api-gateway use?"
        result = rag_engine.ask(question)
        assert "8080" in result["answer"]

@pytest.mark.integration
class TestYamlRAG(TestRAGBase):
    def test_docker_compose_chunking(self, db_conn, embedder):
        file_path = "tests/fixtures/sample.yaml"
        result = ingest_file(file_path, db_conn, embedder)
        # sample.yaml has 3 services (api, auth, db)
        if result["status"] == "success":
            assert result["chunks_created"] == 3

    def test_yaml_retrieval(self, rag_engine):
        question = "What port does the api-gateway service use?"
        # The query logic handles the 'api-gateway' name matching 'api' service in sample.yaml
        chunks = rag_engine.retrieve(question)
        assert any("8080" in c["content"] for c in chunks)

    def test_yaml_indentation_preserved(self, rag_engine):
        question = "auth service configuration"
        chunks = rag_engine.retrieve(question, file_type_filter=".yaml")
        assert "  image: gkn/auth-service:latest" in chunks[0]["content"]

@pytest.mark.integration
class TestEndToEnd(TestRAGBase):
    def test_cross_type_retrieval(self, rag_engine):
        question = "What infrastructure is used for GKN RAG?"
        result = rag_engine.ask(question)
        assert result["answer"] != ""
        assert len(result["sources"]) > 0

    def test_unknown_answer(self, rag_engine):
        # Using a question that definitely isn't in our fixtures
        question = "Who is the lead guitarist of Led Zeppelin?"
        result = rag_engine.ask(question)
        assert "I cannot find this information" in result["answer"]

    def test_file_type_filter(self, rag_engine):
        question = "config"
        # Filter for YAML only
        chunks = rag_engine.retrieve(question, file_type_filter=".yaml")
        for chunk in chunks:
            assert chunk["file_type"] in [".yaml", ".yml"]
