"""
Fast local Knowledge Base using SQLite FTS5 (Full-Text Search).
Provides sub-5ms BM25 ranking and search over personal details, notes, and PDFs (resumes, projects).
"""

import os
import re
import uuid

try:
    import sqlite3
except (ImportError, ModuleNotFoundError):
    try:
        import pysqlite3 as sqlite3
    except ImportError:
        sqlite3 = None

from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

try:
    import fitz  # PyMuPDF for fast PDF parsing
except ImportError:
    fitz = None

from app.logging.logger import get_logger

logger = get_logger(__name__)

DB_DIR = Path.home() / ".ai-teleprompter"
KNOWLEDGE_DB_PATH = DB_DIR / "knowledge.db"


class KnowledgeStore:
    """Fast local SQLite FTS5 knowledge store for resume, notes, and PDF context."""

    _instance: Optional["KnowledgeStore"] = None

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or KNOWLEDGE_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @classmethod
    def get_instance(cls) -> "KnowledgeStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_connection(self):
        if sqlite3 is None:
            return None
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create tables for documents and FTS5 full-text search index."""
        if sqlite3 is None:
            logger.warning("sqlite3 is not available in this environment")
            return
        with self._get_connection() as conn:
            cur = conn.cursor()
            # Metadata table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    doc_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    word_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    source_filename TEXT
                )
            """)

            # FTS5 virtual table for lightning-fast full text search
            cur.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                    id UNINDEXED,
                    title,
                    content,
                    tokenize = 'porter unicode61'
                )
            """)
            conn.commit()
            logger.info("KnowledgeStore database initialized", db=str(self.db_path))

    def add_text_document(self, title: str, content: str, doc_type: str = "note", source_filename: Optional[str] = None) -> Dict[str, Any]:
        """Add text content / note to the knowledge base."""
        clean_title = title.strip() or "Untitled Note"
        clean_content = content.strip()
        if not clean_content:
            raise ValueError("Document content cannot be empty.")

        doc_id = f"doc_{uuid.uuid4().hex[:10]}"
        words = len(clean_content.split())
        now = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO documents (id, title, doc_type, content, word_count, created_at, source_filename)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (doc_id, clean_title, doc_type, clean_content, words, now, source_filename),
            )
            cur.execute(
                """
                INSERT INTO knowledge_fts (id, title, content)
                VALUES (?, ?, ?)
                """,
                (doc_id, clean_title, clean_content),
            )
            conn.commit()

        logger.info("Added document to knowledge base", doc_id=doc_id, title=clean_title, words=words)
        return {
            "id": doc_id,
            "title": clean_title,
            "doc_type": doc_type,
            "word_count": words,
            "created_at": now,
            "source_filename": source_filename,
        }

    def add_pdf_document(self, filename: str, file_bytes: bytes) -> Dict[str, Any]:
        """Extract text from PDF using PyMuPDF and index in knowledge base."""
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            extracted_pages = []
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text("text").strip()
                if text:
                    extracted_pages.append(f"--- Page {page_num + 1} ---\n{text}")

            full_text = "\n\n".join(extracted_pages).strip()
            if not full_text:
                raise ValueError("No extractable text found in PDF.")

            title = Path(filename).stem.replace("_", " ").title()
            return self.add_text_document(
                title=title,
                content=full_text,
                doc_type="pdf",
                source_filename=filename,
            )
        except Exception as e:
            logger.error("Failed to parse PDF document", filename=filename, error=str(e))
            raise

    def list_documents(self) -> List[Dict[str, Any]]:
        """List all indexed documents without loading full text content."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, title, doc_type, word_count, created_at, source_filename
                FROM documents
                ORDER BY created_at DESC
            """)
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID including full content."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def delete_document(self, doc_id: str) -> bool:
        """Delete document from database and FTS5 index."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            cur.execute("DELETE FROM knowledge_fts WHERE id = ?", (doc_id,))
            conn.commit()
            deleted = cur.rowcount > 0
            if deleted:
                logger.info("Deleted document from knowledge base", doc_id=doc_id)
            return deleted

    def search(self, query: str, limit: int = 4) -> List[Dict[str, Any]]:
        """
        Fast full-text search using SQLite FTS5 BM25 relevance ranking.
        Falls back to token LIKE search if query contains special syntax.
        """
        clean_q = query.strip()
        if not clean_q:
            return []

        # Sanitize query words for FTS5 (keep alphanumeric only)
        tokens = re.findall(r"\w+", clean_q)
        if not tokens:
            return []

        # Filter out common stop words to keep search focused
        stopwords = {
            "a", "an", "the", "in", "on", "of", "and", "or", "to", "for",
            "is", "are", "was", "were", "what", "how", "why", "who", "which",
            "can", "could", "would", "tell", "me", "about", "your", "my", "you", "i"
        }
        filtered_tokens = [t for t in tokens if t.lower() not in stopwords]
        search_tokens = filtered_tokens if filtered_tokens else tokens

        # Build FTS5 query: token1* OR token2*
        fts_query = " OR ".join([f'"{t}"*' for t in search_tokens[:8]])

        results = []
        with self._get_connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    SELECT d.id, d.title, d.doc_type, d.content, d.source_filename,
                           bm25(knowledge_fts) as rank,
                           snippet(knowledge_fts, 2, '<b>', '</b>', '...', 32) as snippet
                    FROM knowledge_fts f
                    JOIN documents d ON f.id = d.id
                    WHERE knowledge_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (fts_query, limit),
                )
                rows = cur.fetchall()
                for r in rows:
                    content = r["content"]
                    # If snippet is short or not found, take the first 400 characters
                    snippet = r["snippet"] or (content[:400] + "..." if len(content) > 400 else content)
                    results.append({
                        "id": r["id"],
                        "title": r["title"],
                        "doc_type": r["doc_type"],
                        "source_filename": r["source_filename"],
                        "snippet": snippet,
                        "content_chunk": content[:800],
                        "score": float(r["rank"]),
                    })
            except Exception as err:
                logger.warning("FTS MATCH query failed, trying fallback substring search", error=str(err))
                # Fallback to LIKE matching
                like_clauses = " OR ".join(["content LIKE ?" for _ in search_tokens[:3]])
                params = [f"%{t}%" for t in search_tokens[:3]] + [limit]
                cur.execute(
                    f"""
                    SELECT id, title, doc_type, content, source_filename
                    FROM documents
                    WHERE {like_clauses}
                    LIMIT ?
                    """,
                    tuple(params),
                )
                for r in cur.fetchall():
                    results.append({
                        "id": r["id"],
                        "title": r["title"],
                        "doc_type": r["doc_type"],
                        "source_filename": r["source_filename"],
                        "snippet": r["content"][:300] + "...",
                        "content_chunk": r["content"][:800],
                        "score": 1.0,
                    })

        return results
