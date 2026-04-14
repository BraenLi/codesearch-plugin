"""Tests for the hooks module."""

import pytest

from codesearch.hooks.triggers import (
    HookTrigger,
    TriggerConfig,
    TriggerMatch,
    TriggerType,
)


class TestTriggerMatch:
    """Tests for TriggerMatch dataclass."""

    def test_trigger_match_creation(self):
        """Test creating a TriggerMatch."""
        match = TriggerMatch(
            triggered=True,
            confidence=0.8,
            trigger_type=TriggerType.KEYWORD,
            matched_pattern="find",
            matched_text="find",
        )

        assert match.triggered is True
        assert match.confidence == 0.8
        assert match.trigger_type == TriggerType.KEYWORD

    def test_trigger_match_to_dict(self):
        """Test converting TriggerMatch to dictionary."""
        match = TriggerMatch(
            triggered=True,
            confidence=0.8,
            trigger_type=TriggerType.KEYWORD,
        )

        result = match.to_dict()

        assert result["triggered"] is True
        assert result["confidence"] == 0.8
        assert result["trigger_type"] == "keyword"


class TestTriggerConfig:
    """Tests for TriggerConfig dataclass."""

    def test_trigger_config_creation(self):
        """Test creating a TriggerConfig."""
        config = TriggerConfig(
            name="test_trigger",
            trigger_type=TriggerType.KEYWORD,
            keywords=["test", "example"],
            confidence=0.9,
            description="Test trigger",
        )

        assert config.name == "test_trigger"
        assert config.trigger_type == TriggerType.KEYWORD
        assert config.keywords == ["test", "example"]
        assert config.confidence == 0.9


class TestHookTrigger:
    """Tests for HookTrigger."""

    def test_default_triggers(self):
        """Test that default triggers are configured."""
        trigger = HookTrigger()

        assert len(trigger.triggers) > 0

        trigger_names = {t.name for t in trigger.triggers}
        assert "search_code" in trigger_names
        assert "find_symbol" in trigger_names
        assert "find_references" in trigger_names

    def test_keyword_trigger(self):
        """Test keyword-based triggering."""
        trigger = HookTrigger()

        result = trigger.should_trigger("find all memory allocation functions")

        assert result.triggered is True
        assert result.confidence >= 0.5
        assert result.trigger_type == TriggerType.KEYWORD

    def test_pattern_trigger(self):
        """Test pattern-based triggering."""
        trigger = HookTrigger()

        result = trigger.should_trigger("find function named malloc_wrapper")

        # Should match either keyword or pattern
        assert result.triggered is True
        assert result.confidence > 0

    def test_no_trigger(self):
        """Test that unrelated queries don't trigger."""
        trigger = HookTrigger(threshold=0.9)  # High threshold

        result = trigger.should_trigger("what is the weather today")

        # With high threshold, should not trigger
        assert result.triggered is False or result.confidence < 0.9

    def test_threshold_setting(self):
        """Test threshold configuration."""
        trigger = HookTrigger(threshold=0.3)

        result_low = trigger.should_trigger("maybe find something")
        assert result_low.triggered is True  # Low threshold

        trigger.set_threshold(0.9)
        result_high = trigger.should_trigger("maybe find something")
        assert result_high.triggered is False  # High threshold

    def test_custom_trigger(self):
        """Test adding custom triggers."""
        trigger = HookTrigger()

        def custom_check(text: str) -> TriggerMatch:
            if "custom_keyword" in text.lower():
                return TriggerMatch(
                    triggered=True,
                    confidence=0.95,
                    trigger_type=TriggerType.CUSTOM,
                    matched_text="custom_keyword",
                )
            return TriggerMatch(
                triggered=False,
                confidence=0.0,
                trigger_type=TriggerType.CUSTOM,
            )

        trigger.add_custom_trigger(custom_check)

        result = trigger.should_trigger("please use custom_keyword here")

        assert result.triggered is True
        assert result.confidence == 0.95
        assert result.trigger_type == TriggerType.CUSTOM

    def test_remove_trigger(self):
        """Test removing a trigger."""
        trigger = HookTrigger()

        # Remove a trigger
        removed = trigger.remove_trigger("search_code")
        assert removed is True

        # Verify it's removed
        trigger_names = {t.name for t in trigger.triggers}
        assert "search_code" not in trigger_names

        # Remove non-existent trigger
        removed = trigger.remove_trigger("nonexistent")
        assert removed is False

    def test_get_trigger_info(self):
        """Test getting trigger information."""
        trigger = HookTrigger()

        info = trigger.get_trigger_info()

        assert len(info) > 0
        assert all("name" in item for item in info)
        assert all("type" in item for item in info)

    def test_specific_triggers(self):
        """Test specific trigger scenarios."""
        trigger = HookTrigger()

        # Search trigger
        result = trigger.should_trigger("search for memory leaks")
        assert result.triggered is True

        # References trigger
        result = trigger.should_trigger("find references to malloc")
        assert result.triggered is True

        # Navigation trigger
        result = trigger.should_trigger("go to definition")
        assert result.triggered is True

        # Understanding trigger
        result = trigger.should_trigger("explain how this works")
        assert result.triggered is True


class TestTriggerTypes:
    """Tests for TriggerType enum."""

    def test_trigger_types(self):
        """Test all trigger types are defined."""
        assert TriggerType.KEYWORD.value == "keyword"
        assert TriggerType.PATTERN.value == "pattern"
        assert TriggerType.INTENT.value == "intent"
        assert TriggerType.CUSTOM.value == "custom"


class TestPatternMatching:
    """Tests for pattern-based matching."""

    def test_function_pattern(self):
        """Test function search pattern."""
        trigger = HookTrigger()

        patterns = [
            "find function named test_func",
            "show me the function 'process_data'",
            "where is the method handle_request",
        ]

        for pattern in patterns:
            result = trigger.should_trigger(pattern)
            # Should trigger with high confidence for function patterns
            assert result.triggered is True or result.confidence > 0.5

    def test_struct_pattern(self):
        """Test struct search pattern."""
        trigger = HookTrigger()

        result = trigger.should_trigger("find struct named Network")
        assert result.triggered is True

    def test_file_line_pattern(self):
        """Test file/line pattern."""
        trigger = HookTrigger()

        result = trigger.should_trigger("show me file utils.c line 42")
        assert result.triggered is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
