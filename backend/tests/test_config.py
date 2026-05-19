"""Tests for core/config.py — field types, defaults, and backward-compat."""

import pytest

from core.config import Settings, settings



def make_settings(**overrides) -> Settings:
    """Build a Settings instance with explicit values, bypassing os.getenv defaults."""
    defaults = {
        "secret_key": "test-secret",
        "algorithm": "HS256",
        "database": "postgresql://user:pass@localhost/db",
        "access_token_expire_minutes": 600,
        "openai_api_key": None,
        "openai_embedding_model": "text-embedding-3-small",
        "openai_chat_model": "gpt-4o-mini",
        "llm_summary_temperature": 0.1,
        "chroma_host": "localhost",
        "chroma_port": 8001,
        "chroma_collection_child_chunks": "child_chunks",
        "chroma_collection_summaries": "document_summaries",
        "redis_url": "redis://localhost:6379/0",
        "celery_broker_url": "redis://localhost:6379/0",
        "celery_result_backend": "redis://localhost:6379/1",
        "max_file_size_mb": 200,
        "max_pages_per_doc": 500,
        "parent_chunk_size": 1800,
        "parent_chunk_overlap": 200,
        "child_chunk_size": 400,
        "child_chunk_overlap": 60,
        "embedding_batch_size": 100,
    }
    defaults.update(overrides)
    return Settings(**defaults)



class TestSettingsSingleton:
    def test_settings_singleton_is_importable(self):
        assert settings is not None

    def test_settings_is_settings_instance(self):
        assert isinstance(settings, Settings)



class TestLegacyFields:
    def test_secret_key_field_exists(self):
        s = make_settings(secret_key="my-key")
        assert s.secret_key == "my-key"

    def test_algorithm_field_exists(self):
        s = make_settings(algorithm="HS256")
        assert s.algorithm == "HS256"

    def test_database_field_exists(self):
        s = make_settings(database="postgresql://x")
        assert s.database == "postgresql://x"

    def test_access_token_expire_minutes_is_int(self):
        s = make_settings(access_token_expire_minutes=30)
        assert isinstance(s.access_token_expire_minutes, int)
        assert s.access_token_expire_minutes == 30



class TestLLMSettings:
    def test_openai_api_key_is_none_by_default(self):
        s = make_settings(openai_api_key=None)
        assert s.openai_api_key is None

    def test_openai_api_key_accepts_string(self):
        s = make_settings(openai_api_key="sk-test")
        assert s.openai_api_key == "sk-test"

    def test_openai_embedding_model_default(self):
        s = make_settings()
        assert s.openai_embedding_model == "text-embedding-3-small"

    def test_openai_chat_model_default(self):
        s = make_settings()
        assert s.openai_chat_model == "gpt-4o-mini"

    def test_llm_summary_temperature_is_float(self):
        s = make_settings(llm_summary_temperature=0.1)
        assert isinstance(s.llm_summary_temperature, float)

    def test_llm_summary_temperature_default(self):
        s = make_settings()
        assert s.llm_summary_temperature == pytest.approx(0.1)

    def test_llm_summary_temperature_accepts_zero(self):
        s = make_settings(llm_summary_temperature=0.0)
        assert s.llm_summary_temperature == pytest.approx(0.0)

    def test_llm_summary_temperature_accepts_one(self):
        s = make_settings(llm_summary_temperature=1.0)
        assert s.llm_summary_temperature == pytest.approx(1.0)



class TestChromaSettings:
    def test_chroma_host_default(self):
        s = make_settings()
        assert s.chroma_host == "localhost"

    def test_chroma_port_is_int(self):
        s = make_settings(chroma_port=8001)
        assert isinstance(s.chroma_port, int)

    def test_chroma_port_default(self):
        s = make_settings()
        assert s.chroma_port == 8001

    def test_chroma_port_accepts_custom_value(self):
        s = make_settings(chroma_port=9000)
        assert s.chroma_port == 9000

    def test_chroma_collection_child_chunks_default(self):
        s = make_settings()
        assert s.chroma_collection_child_chunks == "child_chunks"

    def test_chroma_collection_summaries_default(self):
        s = make_settings()
        assert s.chroma_collection_summaries == "document_summaries"

    def test_chroma_collections_accept_custom_names(self):
        s = make_settings(
            chroma_collection_child_chunks="my_chunks",
            chroma_collection_summaries="my_summaries",
        )
        assert s.chroma_collection_child_chunks == "my_chunks"
        assert s.chroma_collection_summaries == "my_summaries"



class TestCeleryRedisSettings:
    def test_redis_url_default(self):
        s = make_settings()
        assert s.redis_url == "redis://localhost:6379/0"

    def test_celery_broker_url_default(self):
        s = make_settings()
        assert s.celery_broker_url == "redis://localhost:6379/0"

    def test_celery_result_backend_default(self):
        s = make_settings()
        assert s.celery_result_backend == "redis://localhost:6379/1"

    def test_broker_and_result_backend_are_different_dbs_by_default(self):
        s = make_settings()
        assert s.celery_broker_url != s.celery_result_backend

    def test_redis_url_accepts_custom_value(self):
        s = make_settings(redis_url="redis://myhost:6380/2")
        assert s.redis_url == "redis://myhost:6380/2"



class TestIngestionLimitSettings:
    @pytest.mark.parametrize("field,expected", [
        ("max_file_size_mb", 200),
        ("max_pages_per_doc", 500),
        ("parent_chunk_size", 1800),
        ("parent_chunk_overlap", 200),
        ("child_chunk_size", 400),
        ("child_chunk_overlap", 60),
        ("embedding_batch_size", 100),
    ])
    def test_default_value(self, field, expected):
        s = make_settings()
        assert getattr(s, field) == expected

    @pytest.mark.parametrize("field", [
        "max_file_size_mb",
        "max_pages_per_doc",
        "parent_chunk_size",
        "parent_chunk_overlap",
        "child_chunk_size",
        "child_chunk_overlap",
        "embedding_batch_size",
    ])
    def test_all_ingestion_limits_are_int(self, field):
        s = make_settings()
        assert isinstance(getattr(s, field), int)

    def test_child_chunk_size_less_than_parent_chunk_size(self):
        s = make_settings()
        assert s.child_chunk_size < s.parent_chunk_size

    def test_child_overlap_less_than_child_chunk_size(self):
        s = make_settings()
        assert s.child_chunk_overlap < s.child_chunk_size

    def test_parent_overlap_less_than_parent_chunk_size(self):
        s = make_settings()
        assert s.parent_chunk_overlap < s.parent_chunk_size

    def test_embedding_batch_size_is_positive(self):
        s = make_settings()
        assert s.embedding_batch_size > 0

    def test_max_file_size_mb_accepts_custom_value(self):
        s = make_settings(max_file_size_mb=50)
        assert s.max_file_size_mb == 50



class TestSettingsEdgeCases:
    def test_settings_instances_are_independent(self):
        s1 = make_settings(chroma_port=8001)
        s2 = make_settings(chroma_port=9999)
        assert s1.chroma_port != s2.chroma_port

    def test_all_required_fields_present_on_singleton(self):
        required_fields = [
            "secret_key", "algorithm", "database", "access_token_expire_minutes",
            "openai_api_key", "openai_embedding_model", "openai_chat_model",
            "llm_summary_temperature", "chroma_host", "chroma_port",
            "chroma_collection_child_chunks", "chroma_collection_summaries",
            "redis_url", "celery_broker_url", "celery_result_backend",
            "max_file_size_mb", "max_pages_per_doc", "parent_chunk_size",
            "parent_chunk_overlap", "child_chunk_size", "child_chunk_overlap",
            "embedding_batch_size",
        ]
        for field in required_fields:
            assert hasattr(settings, field), f"settings missing field: {field}"

    def test_settings_field_count(self):
        expected_count = 22
        actual_count = len(Settings.model_fields)
        assert actual_count == expected_count, (
            f"Expected {expected_count} settings fields, got {actual_count}. "
            "Update this assertion if you intentionally added or removed a field."
        )
