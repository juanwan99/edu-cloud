"""Tests for the lightweight state machine registry."""

import pytest

from edu_cloud.core.state_machine import (
    STATE_MACHINES,
    validate_transition,
    get_terminal_states,
)
from edu_cloud.services.exceptions import StateError


# ── exam transitions ─────────────────────────────────────────────

class TestExamTransitions:
    def test_draft_to_scanning(self):
        validate_transition("exam", "draft", "scanning")

    def test_scanning_to_grading(self):
        validate_transition("exam", "scanning", "grading")

    def test_scanning_back_to_draft(self):
        validate_transition("exam", "scanning", "draft")

    def test_grading_to_reviewing(self):
        validate_transition("exam", "grading", "reviewing")

    def test_reviewing_to_completed(self):
        validate_transition("exam", "reviewing", "completed")

    def test_completed_to_published(self):
        validate_transition("exam", "completed", "published")

    def test_completed_to_archived(self):
        validate_transition("exam", "completed", "archived")

    def test_published_to_archived(self):
        validate_transition("exam", "published", "archived")

    def test_draft_to_completed_rejected(self):
        with pytest.raises(StateError, match="draft -> completed"):
            validate_transition("exam", "draft", "completed")

    def test_archived_is_terminal(self):
        with pytest.raises(StateError):
            validate_transition("exam", "archived", "draft")

    def test_exam_terminal_states(self):
        terminals = get_terminal_states("exam")
        assert "archived" in terminals


# ── grading_task transitions ──────────────────────────────────────

class TestGradingTaskTransitions:
    def test_pending_to_processing(self):
        validate_transition("grading_task", "pending", "processing")

    def test_pending_to_cancelled(self):
        validate_transition("grading_task", "pending", "cancelled")

    def test_processing_to_completed(self):
        validate_transition("grading_task", "processing", "completed")

    def test_processing_to_failed(self):
        validate_transition("grading_task", "processing", "failed")

    def test_processing_to_cancelled(self):
        validate_transition("grading_task", "processing", "cancelled")

    def test_failed_to_pending_retry(self):
        validate_transition("grading_task", "failed", "pending")

    def test_completed_is_terminal(self):
        terminals = get_terminal_states("grading_task")
        assert "completed" in terminals

    def test_cancelled_is_terminal(self):
        terminals = get_terminal_states("grading_task")
        assert "cancelled" in terminals

    def test_completed_to_processing_rejected(self):
        with pytest.raises(StateError):
            validate_transition("grading_task", "completed", "processing")

    def test_cancelled_to_pending_rejected(self):
        with pytest.raises(StateError):
            validate_transition("grading_task", "cancelled", "pending")


# ── grading_result transitions ────────────────────────────────────

class TestGradingResultTransitions:
    def test_ai_pending_to_ai_done(self):
        validate_transition("grading_result", "ai_pending", "ai_done")

    def test_ai_done_to_confirmed(self):
        validate_transition("grading_result", "ai_done", "confirmed")

    def test_ai_done_to_ai_pending_regrade(self):
        validate_transition("grading_result", "ai_done", "ai_pending")

    def test_confirmed_is_terminal(self):
        terminals = get_terminal_states("grading_result")
        assert "confirmed" in terminals

    def test_confirmed_to_ai_pending_rejected(self):
        with pytest.raises(StateError):
            validate_transition("grading_result", "confirmed", "ai_pending")

    def test_confirmed_to_ai_done_rejected(self):
        with pytest.raises(StateError):
            validate_transition("grading_result", "confirmed", "ai_done")


# ── document transitions ─────────────────────────────────────────

class TestDocumentTransitions:
    def test_draft_to_reviewed(self):
        validate_transition("document", "draft", "reviewed")

    def test_rejected_to_draft(self):
        validate_transition("document", "rejected", "draft")

    def test_approved_to_executed(self):
        validate_transition("document", "approved", "executed")

    def test_executed_is_terminal(self):
        terminals = get_terminal_states("document")
        assert "executed" in terminals


# ── backward compatibility ────────────────────────────────────────

class TestBackwardCompat:
    def test_unknown_entity_passes(self):
        # No error for unregistered entity types
        validate_transition("unknown_entity", "a", "b")

    def test_get_terminal_states_unknown(self):
        assert get_terminal_states("unknown_entity") == set()


# ── registry integrity ────────────────────────────────────────────

class TestRegistryIntegrity:
    @pytest.mark.parametrize("entity_type", list(STATE_MACHINES.keys()))
    def test_all_transition_sources_are_valid_states(self, entity_type):
        machine = STATE_MACHINES[entity_type]
        valid = set(machine["states"])
        for src in machine["transitions"]:
            assert src in valid, f"{entity_type}: transition source '{src}' not in states"

    @pytest.mark.parametrize("entity_type", list(STATE_MACHINES.keys()))
    def test_all_transition_targets_are_valid_states(self, entity_type):
        machine = STATE_MACHINES[entity_type]
        valid = set(machine["states"])
        for src, targets in machine["transitions"].items():
            for tgt in targets:
                assert tgt in valid, f"{entity_type}: {src} -> {tgt}: target not in states"
