"""Tests for the Interactive Chat Engine."""
import pytest
from app.ai.chat import ChatEngine

@pytest.mark.asyncio
async def test_chat_engine_fallback_streaming():
    engine = ChatEngine(api_key=None)
    tokens = []
    async for token in engine.stream_response("Explain Python generators."):
        tokens.append(token)
    response = "".join(tokens)
    assert len(tokens) > 0
    assert "Python generators" in response or len(response) > 20

@pytest.mark.asyncio
async def test_chat_engine_hello_prompt():
    engine = ChatEngine(api_key=None)
    tokens = []
    async for token in engine.stream_response("Hello"):
        tokens.append(token)
    response = "".join(tokens)
    assert "Hello" in response


def test_transcriber_singleton():
    import numpy as np
    from app.stt.transcriber import LocalTranscriber

    t1 = LocalTranscriber.get_instance()
    t2 = LocalTranscriber.get_instance()
    assert t1 is t2


def test_transcribe_silence():
    import numpy as np
    from app.stt.transcriber import LocalTranscriber

    transcriber = LocalTranscriber.get_instance()
    # 0.5s of silence
    silence = np.zeros(8000, dtype=np.float32)
    text = transcriber.transcribe(silence)
    assert isinstance(text, str)
    assert text == ""


def test_transcribe_short_audio_ignored():
    import numpy as np
    from app.stt.transcriber import LocalTranscriber

    transcriber = LocalTranscriber.get_instance()
    # Less than 0.1s
    short_audio = np.zeros(500, dtype=np.float32)
    assert transcriber.transcribe(short_audio) == ""


def test_knowledge_store_add_search_delete(tmp_path):
    from app.knowledge.store import KnowledgeStore

    test_db = tmp_path / "test_knowledge.db"
    store = KnowledgeStore(db_path=test_db)

    # 1. Add text document
    doc = store.add_text_document(
        title="Software Engineer Resume",
        content="Senior Python Developer with 6 years experience in FastAPI, React, Docker, and distributed AI systems.",
        doc_type="resume",
    )
    assert "id" in doc
    assert doc["title"] == "Software Engineer Resume"
    assert doc["word_count"] > 5

    # 2. Search
    results = store.search("FastAPI")
    assert len(results) > 0
    assert results[0]["title"] == "Software Engineer Resume"

    # Search non-matching
    no_results = store.search("astronomy")
    assert len(no_results) == 0

    # 3. List
    docs = store.list_documents()
    assert len(docs) == 1

    # 4. Delete
    deleted = store.delete_document(doc["id"])
    assert deleted is True
    assert len(store.list_documents()) == 0


@pytest.mark.asyncio
async def test_api_connection_empty_key():
    from app.ai.verifier import test_api_connection

    result = await test_api_connection(provider="claude", api_key="")
    assert result["success"] is False
    assert "empty" in result["message"]


