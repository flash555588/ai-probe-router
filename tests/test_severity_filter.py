"""Tests for severity filter state."""

from ai_probe_router.ui.severity_filter import SeverityFilterState


class TestSeverityFilterState:
    def test_allows_all_by_default(self):
        state = SeverityFilterState()
        assert state.allows("error")
        assert state.allows("warning")
        assert state.allows("info")

    def test_blocks_error_when_disabled(self):
        state = SeverityFilterState(show_error=False)
        assert not state.allows("error")
        assert state.allows("warning")
        assert state.allows("info")

    def test_blocks_warning_when_disabled(self):
        state = SeverityFilterState(show_warning=False)
        assert state.allows("error")
        assert not state.allows("warning")
        assert state.allows("info")

    def test_blocks_info_when_disabled(self):
        state = SeverityFilterState(show_info=False)
        assert state.allows("error")
        assert state.allows("warning")
        assert not state.allows("info")

    def test_allows_unknown_severity(self):
        state = SeverityFilterState()
        assert state.allows("unknown")
