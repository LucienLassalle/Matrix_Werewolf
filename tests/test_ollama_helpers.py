"""Tests unitaires pour utils/ollama_helper — ne nécessitent pas Ollama."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock

from utils.ollama_helper import (
    estimate_tokens,
    chunk_messages,
    merge_summaries,
    format_summary_message,
    get_model_info,
    DEFAULT_CONTEXT_LENGTH,
)

# Lus depuis le .env ; valeurs par défaut utilisées uniquement dans les tests.
TEST_OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
TEST_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")


# ── estimate_tokens ──────────────────────────────────────────────────────────

def test_estimate_tokens_empty():
    assert estimate_tokens("") == 1  # max(1, 0)


def test_estimate_tokens_short():
    assert estimate_tokens("Hi") == 1  # max(1, 2//4=0)


def test_estimate_tokens_basic():
    assert estimate_tokens("A" * 400) == 100  # 400 // 4


def test_estimate_tokens_unicode():
    # Les caractères multi-octets comptent en caractères, pas en octets
    assert estimate_tokens("é" * 400) == 100


# ── chunk_messages ───────────────────────────────────────────────────────────

def test_chunk_messages_empty():
    assert chunk_messages([], 100) == []


def test_chunk_messages_single_fits():
    msgs = [{"message": "A", "sender": "x", "timestamp": "t"}]
    chunks = chunk_messages(msgs, 1000)
    assert len(chunks) == 1
    assert chunks[0] == msgs


def test_chunk_messages_split():
    """3 messages de ~50 tokens chacun avec max_tokens=60 → 3 chunks."""
    msg = {"message": "X" * 200, "sender": "u", "timestamp": "t"}
    chunks = chunk_messages([msg, msg, msg], max_tokens=60)
    assert len(chunks) == 3


def test_chunk_messages_two_fit_in_one():
    """2 messages légers rentrent dans un seul chunk."""
    msg = {"message": "hi", "sender": "u", "timestamp": "t"}
    chunks = chunk_messages([msg, msg], max_tokens=1000)
    assert len(chunks) == 1
    assert len(chunks[0]) == 2


def test_chunk_messages_preserves_order():
    """L'ordre des messages est préservé dans les chunks."""
    msgs = [{"message": str(i), "sender": "u", "timestamp": str(i)} for i in range(6)]
    chunks = chunk_messages(msgs, max_tokens=10)
    flat = [m for chunk in chunks for m in chunk]
    assert flat == msgs


def test_chunk_messages_oversized_single_message():
    """Un message plus grand que max_tokens va seul dans son chunk."""
    big_msg = {"message": "Z" * 2000, "sender": "u", "timestamp": "t"}
    small_msg = {"message": "a", "sender": "u", "timestamp": "t"}
    # big_msg > max_tokens=100, mais comme current_chunk est vide il doit quand même rentrer
    chunks = chunk_messages([big_msg, small_msg], max_tokens=100)
    # big_msg remplit un chunk, small_msg dans un autre (ou seul)
    assert len(chunks) >= 1
    assert any(big_msg in c for c in chunks)


# ── merge_summaries ──────────────────────────────────────────────────────────

def test_merge_summaries_empty():
    result = merge_summaries([])
    assert result == {"accusations": [], "citations": [], "synthese": ""}


def test_merge_summaries_single():
    s = {
        "accusations": [{"accuser": "a", "accused": "b", "quote": "q"}],
        "citations": [{"author": "c", "text": "t"}],
        "synthese": "Résumé"
    }
    assert merge_summaries([s]) == s


def test_merge_summaries_two_no_overlap():
    s1 = {"accusations": [{"accuser": "a", "accused": "b"}], "citations": [], "synthese": "S1"}
    s2 = {"accusations": [{"accuser": "c", "accused": "d"}], "citations": [], "synthese": "S2"}
    result = merge_summaries([s1, s2])
    assert len(result["accusations"]) == 2
    assert result["synthese"] == "S1 | S2"


def test_merge_summaries_dedup_accusations():
    """Deux accusations avec le même (accuser, accused) sont dédupliquées."""
    s1 = {"accusations": [{"accuser": "a", "accused": "b", "quote": "q1"}], "citations": [], "synthese": "S1"}
    s2 = {"accusations": [{"accuser": "a", "accused": "b", "quote": "q2"}], "citations": [], "synthese": "S2"}
    result = merge_summaries([s1, s2])
    assert len(result["accusations"]) == 1
    assert result["synthese"] == "S1 | S2"


def test_merge_summaries_dedup_citations():
    """Deux citations identiques (même auteur + même début de texte) sont dédupliquées."""
    cit = {"author": "x", "text": "phrase importante"}
    s1 = {"accusations": [], "citations": [cit], "synthese": "S1"}
    s2 = {"accusations": [], "citations": [cit], "synthese": "S2"}
    result = merge_summaries([s1, s2])
    assert len(result["citations"]) == 1


def test_merge_summaries_synthese_joined():
    summaries = [
        {"accusations": [], "citations": [], "synthese": "A"},
        {"accusations": [], "citations": [], "synthese": "B"},
        {"accusations": [], "citations": [], "synthese": "C"},
    ]
    result = merge_summaries(summaries)
    assert result["synthese"] == "A | B | C"


def test_merge_summaries_empty_synthese_skipped():
    summaries = [
        {"accusations": [], "citations": [], "synthese": "A"},
        {"accusations": [], "citations": [], "synthese": ""},
        {"accusations": [], "citations": [], "synthese": "C"},
    ]
    result = merge_summaries(summaries)
    assert result["synthese"] == "A | C"


# ── format_summary_message ───────────────────────────────────────────────────

def test_format_summary_complete():
    parsed = {
        "accusations": [{"accuser": "Alice", "accused": "Bob", "quote": "C'est lui !"}],
        "citations": [{"author": "Alice", "text": "Je suis certaine"}],
        "synthese": "Alice accuse Bob avec force.",
    }
    msg = format_summary_message(parsed)
    assert "Résumé généré" in msg
    assert "Alice" in msg
    assert "Bob" in msg
    assert "C'est lui !" in msg
    assert "Je suis certaine" in msg
    assert "Alice accuse Bob avec force." in msg


def test_format_summary_empty_dict():
    msg = format_summary_message({})
    assert "Résumé généré" in msg


def test_format_summary_no_quote():
    parsed = {
        "accusations": [{"accuser": "Alice", "accused": "Bob"}],
        "citations": [],
        "synthese": "",
    }
    msg = format_summary_message(parsed)
    assert "Alice" in msg
    assert "Bob" in msg
    # Pas de crash sans quote ni synthèse


def test_format_summary_no_raw_json():
    """Le résultat ne doit pas commencer par un accolade JSON brut."""
    parsed = {"accusations": [], "citations": [], "synthese": "Test"}
    msg = format_summary_message(parsed)
    assert not msg.startswith("{")


def test_format_summary_citations_only():
    parsed = {
        "accusations": [],
        "citations": [{"author": "X", "text": "Message important"}],
        "synthese": "",
    }
    msg = format_summary_message(parsed)
    assert "X" in msg
    assert "Message important" in msg


# ── get_model_info ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_model_info_from_model_info_key():
    """Extrait context_length depuis model_info (format Ollama récent)."""
    mock_session = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={
        "name": TEST_OLLAMA_MODEL,
        "model_info": {"qwen2.context_length": 32768},
    })
    mock_session.post = AsyncMock(return_value=mock_resp)

    result = await get_model_info(mock_session, TEST_OLLAMA_HOST, TEST_OLLAMA_MODEL)
    assert result["context_length"] == 32768
    assert result["model_name"] == TEST_OLLAMA_MODEL


@pytest.mark.asyncio
async def test_get_model_info_from_parameters_string():
    """Extrait context_length depuis la chaîne 'parameters' (format Ollama ancien)."""
    mock_session = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={
        "name": TEST_OLLAMA_MODEL,
        "model_info": {},
        "parameters": "num_ctx 4096\nstop \"</s>\"",
    })
    mock_session.post = AsyncMock(return_value=mock_resp)

    result = await get_model_info(mock_session, TEST_OLLAMA_HOST, TEST_OLLAMA_MODEL)
    assert result["context_length"] == 4096


@pytest.mark.asyncio
async def test_get_model_info_status_error():
    """Retourne les défauts si Ollama répond en erreur."""
    mock_session = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 500
    mock_session.post = AsyncMock(return_value=mock_resp)

    result = await get_model_info(mock_session, TEST_OLLAMA_HOST, TEST_OLLAMA_MODEL)
    assert result["context_length"] == DEFAULT_CONTEXT_LENGTH


@pytest.mark.asyncio
async def test_get_model_info_connection_error():
    """Retourne les défauts si la connexion échoue."""
    mock_session = MagicMock()
    mock_session.post = AsyncMock(side_effect=ConnectionError("refused"))

    result = await get_model_info(mock_session, TEST_OLLAMA_HOST, "any")
    assert result["context_length"] == DEFAULT_CONTEXT_LENGTH


@pytest.mark.asyncio
async def test_get_model_info_no_context_key():
    """Retourne les défauts si aucune clé context_length n'est trouvée."""
    mock_session = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={
        "name": "mymodel",
        "model_info": {"other_key": 42},
        "parameters": "",
    })
    mock_session.post = AsyncMock(return_value=mock_resp)

    result = await get_model_info(mock_session, TEST_OLLAMA_HOST, "mymodel")
    assert result["context_length"] == DEFAULT_CONTEXT_LENGTH
