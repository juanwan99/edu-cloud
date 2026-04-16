import pytest
from edu_cloud.ai.shared_state import SharedState


class TestSharedState:
    def test_set_and_get(self):
        state = SharedState()
        state.set("topic", "深度学习")
        assert state.get("topic") == "深度学习"

    def test_get_missing_key_returns_default(self):
        state = SharedState()
        assert state.get("missing") is None
        assert state.get("missing", "fallback") == "fallback"

    def test_set_overwrite(self):
        state = SharedState()
        state.set("count", 1)
        state.set("count", 2)
        assert state.get("count") == 2

    def test_history_tracks_changes(self):
        state = SharedState()
        state.set("a", 1)
        state.set("b", 2)
        state.set("a", 3)
        history = state.get_history()
        assert len(history) == 3
        assert history[0] == ("a", 1)
        assert history[1] == ("b", 2)
        assert history[2] == ("a", 3)

    def test_checkpoint_and_restore(self):
        state = SharedState()
        state.set("x", 10)
        state.set("y", 20)
        snap = state.checkpoint()
        assert snap == {"x": 10, "y": 20}
        state2 = SharedState()
        state2.restore(snap)
        assert state2.get("x") == 10
        assert state2.get("y") == 20

    def test_as_dict(self):
        state = SharedState()
        state.set("a", 1)
        state.set("b", [2, 3])
        d = state.as_dict()
        assert d == {"a": 1, "b": [2, 3]}
        d["a"] = 999
        assert state.get("a") == 1

    def test_stage_tracking(self):
        state = SharedState()
        assert state.current_stage is None
        state.set_stage("research")
        assert state.current_stage == "research"
        state.set_stage("writing")
        assert state.current_stage == "writing"
