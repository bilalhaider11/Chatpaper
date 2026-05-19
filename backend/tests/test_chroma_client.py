"""Tests for core/chroma.py — client creation, singleton behavior, collection setup."""

from unittest.mock import MagicMock, patch, call

import pytest

import core.chroma as chroma_module
from core.chroma import (
    get_chroma_client,
    get_child_chunks_collection,
    get_document_summaries_collection,
    reset_chroma_client,
)
from core.config import settings


@pytest.fixture(autouse=True)
def clear_singleton():
    reset_chroma_client()
    yield
    reset_chroma_client()



class TestGetChromaClient:
    def test_creates_http_client_with_correct_host(self):
        with patch("core.chroma.chromadb.HttpClient") as mock_http:
            get_chroma_client()
            mock_http.assert_called_once()
            _, kwargs = mock_http.call_args
            assert kwargs.get("host") == settings.chroma_host

    def test_creates_http_client_with_correct_port(self):
        with patch("core.chroma.chromadb.HttpClient") as mock_http:
            get_chroma_client()
            _, kwargs = mock_http.call_args
            assert kwargs.get("port") == settings.chroma_port

    def test_singleton_returns_same_instance_on_second_call(self):
        with patch("core.chroma.chromadb.HttpClient") as mock_http:
            mock_instance = MagicMock()
            mock_http.return_value = mock_instance

            client1 = get_chroma_client()
            client2 = get_chroma_client()

            assert client1 is client2
            mock_http.assert_called_once()

    def test_http_client_constructed_exactly_once_on_multiple_calls(self):
        with patch("core.chroma.chromadb.HttpClient") as mock_http:
            for _ in range(5):
                get_chroma_client()
            assert mock_http.call_count == 1

    def test_connection_error_propagates_to_caller(self):
        with patch("core.chroma.chromadb.HttpClient", side_effect=Exception("connection refused")):
            with pytest.raises(Exception, match="connection refused"):
                get_chroma_client()

    def test_value_error_propagates_to_caller(self):
        with patch("core.chroma.chromadb.HttpClient", side_effect=ValueError("bad host")):
            with pytest.raises(ValueError, match="bad host"):
                get_chroma_client()



class TestResetChromaClient:
    def test_reset_clears_singleton(self):
        with patch("core.chroma.chromadb.HttpClient") as mock_http:
            mock_http.return_value = MagicMock()
            get_chroma_client()
            reset_chroma_client()
            get_chroma_client()
            assert mock_http.call_count == 2

    def test_reset_on_uninitialised_singleton_does_not_raise(self):
        reset_chroma_client()
        reset_chroma_client()

    def test_after_reset_new_instance_is_created(self):
        with patch("core.chroma.chromadb.HttpClient") as mock_http:
            instance_a = MagicMock(name="instance_a")
            instance_b = MagicMock(name="instance_b")
            mock_http.side_effect = [instance_a, instance_b]

            client1 = get_chroma_client()
            reset_chroma_client()
            client2 = get_chroma_client()

            assert client1 is instance_a
            assert client2 is instance_b
            assert client1 is not client2



class TestGetChildChunksCollection:
    def _mock_client(self):
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        return mock_client, mock_collection

    def test_calls_get_or_create_collection_with_correct_name(self):
        mock_client, _ = self._mock_client()
        with patch("core.chroma.get_chroma_client", return_value=mock_client):
            get_child_chunks_collection()
            mock_client.get_or_create_collection.assert_called_once()
            args, kwargs = mock_client.get_or_create_collection.call_args
            name = kwargs.get("name") or (args[0] if args else None)
            assert name == settings.chroma_collection_child_chunks

    def test_uses_cosine_distance_metric(self):
        mock_client, _ = self._mock_client()
        with patch("core.chroma.get_chroma_client", return_value=mock_client):
            get_child_chunks_collection()
            _, kwargs = mock_client.get_or_create_collection.call_args
            metadata = kwargs.get("metadata", {})
            assert metadata.get("hnsw:space") == "cosine"

    def test_returns_collection_object(self):
        mock_client, mock_collection = self._mock_client()
        with patch("core.chroma.get_chroma_client", return_value=mock_client):
            result = get_child_chunks_collection()
            assert result is mock_collection

    def test_collection_name_matches_settings(self):
        mock_client, _ = self._mock_client()
        with patch("core.chroma.get_chroma_client", return_value=mock_client):
            get_child_chunks_collection()
            _, kwargs = mock_client.get_or_create_collection.call_args
            name = kwargs.get("name")
            assert name == "child_chunks"



class TestGetDocumentSummariesCollection:
    def _mock_client(self):
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        return mock_client, mock_collection

    def test_calls_get_or_create_collection_with_correct_name(self):
        mock_client, _ = self._mock_client()
        with patch("core.chroma.get_chroma_client", return_value=mock_client):
            get_document_summaries_collection()
            mock_client.get_or_create_collection.assert_called_once()
            _, kwargs = mock_client.get_or_create_collection.call_args
            name = kwargs.get("name")
            assert name == settings.chroma_collection_summaries

    def test_uses_cosine_distance_metric(self):
        mock_client, _ = self._mock_client()
        with patch("core.chroma.get_chroma_client", return_value=mock_client):
            get_document_summaries_collection()
            _, kwargs = mock_client.get_or_create_collection.call_args
            metadata = kwargs.get("metadata", {})
            assert metadata.get("hnsw:space") == "cosine"

    def test_returns_collection_object(self):
        mock_client, mock_collection = self._mock_client()
        with patch("core.chroma.get_chroma_client", return_value=mock_client):
            result = get_document_summaries_collection()
            assert result is mock_collection

    def test_collection_name_matches_settings(self):
        mock_client, _ = self._mock_client()
        with patch("core.chroma.get_chroma_client", return_value=mock_client):
            get_document_summaries_collection()
            _, kwargs = mock_client.get_or_create_collection.call_args
            name = kwargs.get("name")
            assert name == "document_summaries"



class TestCollectionNamesAreDistinct:
    def test_child_chunks_and_summaries_have_different_names(self):
        assert (
            settings.chroma_collection_child_chunks
            != settings.chroma_collection_summaries
        )
