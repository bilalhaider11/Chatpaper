"""
Phase 0 — test_celery_app.py

Verifies that core/celery_app.py:
  - Creates a Celery app named "chatpaper"
  - Wires the broker URL from settings
  - Wires the result backend from settings
  - Applies the required task configuration (serialisation, acks, prefetch)
  - Declares the ingestion task module in its include list
"""

import pytest

from core.celery_app import celery_app
from core.config import settings


# ── Application identity ──────────────────────────────────────────────────────

class TestCeleryAppIdentity:
    def test_app_main_name_is_chatpaper(self):
        assert celery_app.main == "chatpaper"

    def test_app_is_celery_instance(self):
        from celery import Celery
        assert isinstance(celery_app, Celery)


# ── Broker and backend ────────────────────────────────────────────────────────

class TestCeleryBrokerAndBackend:
    def test_broker_url_matches_settings(self):
        assert celery_app.conf.broker_url == settings.celery_broker_url

    def test_result_backend_matches_settings(self):
        assert celery_app.conf.result_backend == settings.celery_result_backend

    def test_broker_and_result_backend_are_not_the_same(self):
        assert celery_app.conf.broker_url != celery_app.conf.result_backend


# ── Serialisation settings ────────────────────────────────────────────────────

class TestCelerySerialisation:
    def test_task_serializer_is_json(self):
        assert celery_app.conf.task_serializer == "json"

    def test_result_serializer_is_json(self):
        assert celery_app.conf.result_serializer == "json"

    def test_accept_content_includes_json(self):
        assert "json" in celery_app.conf.accept_content


# ── Reliability settings ──────────────────────────────────────────────────────

class TestCeleryReliabilitySettings:
    def test_task_acks_late_is_true(self):
        assert celery_app.conf.task_acks_late is True

    def test_task_reject_on_worker_lost_is_true(self):
        assert celery_app.conf.task_reject_on_worker_lost is True

    def test_worker_prefetch_multiplier_is_one(self):
        assert celery_app.conf.worker_prefetch_multiplier == 1


# ── Task module registration ──────────────────────────────────────────────────

class TestCeleryTaskIncludes:
    def test_ingestion_tasks_module_is_included(self):
        assert "tasks.ingestion_tasks" in celery_app.conf.include
