"""
Hook system for intelligent triggering.

This module implements pattern-based triggers with confidence scoring
for automatically activating the codesearch subagent.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


class TriggerType(Enum):
    """Types of triggers."""

    KEYWORD = "keyword"  # Simple keyword matching
    PATTERN = "pattern"  # Regex pattern matching
    INTENT = "intent"  # Intent-based matching
    CUSTOM = "custom"  # Custom function-based


@dataclass
class TriggerMatch:
    """Result of a trigger match."""

    triggered: bool
    confidence: float
    trigger_type: TriggerType
    matched_pattern: Optional[str] = None
    matched_text: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "triggered": self.triggered,
            "confidence": self.confidence,
            "trigger_type": self.trigger_type.value,
            "matched_pattern": self.matched_pattern,
            "matched_text": self.matched_text,
        }


@dataclass
class TriggerConfig:
    """Configuration for a single trigger."""

    name: str
    trigger_type: TriggerType
    pattern: Optional[str] = None  # For regex patterns
    keywords: Optional[list[str]] = None  # For keyword matching
    confidence: float = 1.0  # Base confidence score
    description: str = ""


class HookTrigger:
    """
    Hook system for triggering codesearch subagent.

    Usage:
        trigger = HookTrigger()
        result = trigger.should_trigger("find all memory allocation functions")
        if result.triggered:
            # Activate subagent
    """

    # Default trigger configurations
    DEFAULT_TRIGGERS: list[TriggerConfig] = [
        # Search-related triggers
        TriggerConfig(
            name="search_code",
            trigger_type=TriggerType.KEYWORD,
            keywords=["search for", "search code", "code search"],
            confidence=0.9,
            description="Explicit code search requests",
        ),
        TriggerConfig(
            name="find_symbol",
            trigger_type=TriggerType.KEYWORD,
            keywords=["find", "locate", "show me", "where is"],
            confidence=0.8,
            description="Finding symbols or code",
        ),
        TriggerConfig(
            name="find_references",
            trigger_type=TriggerType.KEYWORD,
            keywords=["references", "usages", "callers", "where.*used", "who calls"],
            confidence=0.85,
            description="Finding references to symbols",
        ),
        TriggerConfig(
            name="understand_code",
            trigger_type=TriggerType.KEYWORD,
            keywords=["understand", "explain", "what does", "how does"],
            confidence=0.7,
            description="Understanding code functionality",
        ),
        TriggerConfig(
            name="navigate_code",
            trigger_type=TriggerType.KEYWORD,
            keywords=["go to", "navigate to", "jump to", "open"],
            confidence=0.75,
            description="Code navigation requests",
        ),
        # Pattern-based triggers
        TriggerConfig(
            name="function_search",
            trigger_type=TriggerType.PATTERN,
            pattern=r"(?:function|method|routine)\s+(?:named?\s+)?['\"]?(\w+)['\"]?",
            confidence=0.85,
            description="Searching for specific functions",
        ),
        TriggerConfig(
            name="struct_search",
            trigger_type=TriggerType.PATTERN,
            pattern=r"(?:struct|class|type)\s+(?:named?\s+)?['\"]?(\w+)['\"]?",
            confidence=0.85,
            description="Searching for structs or types",
        ),
        TriggerConfig(
            name="file_context",
            trigger_type=TriggerType.PATTERN,
            pattern=r"(?:file|line)\s+(\d+)",
            confidence=0.8,
            description="File or line-specific queries",
        ),
    ]

    def __init__(
        self,
        triggers: Optional[list[TriggerConfig]] = None,
        threshold: float = 0.5,
    ):
        """
        Initialize the hook trigger system.

        Args:
            triggers: Custom trigger configurations. If None, uses defaults.
            threshold: Minimum confidence threshold for triggering (0.0 to 1.0)
        """
        self.triggers = triggers or self.DEFAULT_TRIGGERS.copy()
        self.threshold = threshold

        # Compile regex patterns
        self._compiled_patterns: dict[str, re.Pattern] = {}
        for trigger in self.triggers:
            if trigger.trigger_type == TriggerType.PATTERN and trigger.pattern:
                try:
                    self._compiled_patterns[trigger.name] = re.compile(
                        trigger.pattern, re.IGNORECASE
                    )
                except re.error:
                    pass  # Invalid pattern, skip

        # Custom trigger functions
        self._custom_triggers: list[Callable[[str], TriggerMatch]] = []

    def should_trigger(self, text: str) -> TriggerMatch:
        """
        Check if the given text should trigger the subagent.

        Args:
            text: The text to analyze (e.g., user query)

        Returns:
            TriggerMatch with the result
        """
        best_match = TriggerMatch(
            triggered=False,
            confidence=0.0,
            trigger_type=TriggerType.KEYWORD,
        )

        # Check all triggers
        for trigger in self.triggers:
            match = self._check_trigger(trigger, text)
            if match.triggered and match.confidence > best_match.confidence:
                best_match = match

        # Check custom triggers
        for custom_trigger in self._custom_triggers:
            try:
                match = custom_trigger(text)
                if match.triggered and match.confidence > best_match.confidence:
                    best_match = match
            except Exception:
                pass

        # Apply threshold
        best_match.triggered = best_match.confidence >= self.threshold

        return best_match

    def _check_trigger(self, trigger: TriggerConfig, text: str) -> TriggerMatch:
        """Check a single trigger against the text."""
        if trigger.trigger_type == TriggerType.KEYWORD:
            return self._check_keywords(trigger, text)
        elif trigger.trigger_type == TriggerType.PATTERN:
            return self._check_pattern(trigger, text)
        elif trigger.trigger_type == TriggerType.INTENT:
            return self._check_intent(trigger, text)
        else:
            return TriggerMatch(
                triggered=False,
                confidence=0.0,
                trigger_type=trigger.trigger_type,
            )

    def _check_keywords(
        self, trigger: TriggerConfig, text: str
    ) -> TriggerMatch:
        """Check keyword-based trigger."""
        if not trigger.keywords:
            return TriggerMatch(
                triggered=False,
                confidence=0.0,
                trigger_type=trigger.trigger_type,
            )

        text_lower = text.lower()
        for keyword in trigger.keywords:
            if keyword.lower() in text_lower:
                return TriggerMatch(
                    triggered=True,
                    confidence=trigger.confidence,
                    trigger_type=trigger.trigger_type,
                    matched_pattern=keyword,
                    matched_text=keyword,
                )

        return TriggerMatch(
            triggered=False,
            confidence=0.0,
            trigger_type=trigger.trigger_type,
        )

    def _check_pattern(
        self, trigger: TriggerConfig, text: str
    ) -> TriggerMatch:
        """Check regex pattern-based trigger."""
        if trigger.name not in self._compiled_patterns:
            return TriggerMatch(
                triggered=False,
                confidence=0.0,
                trigger_type=trigger.trigger_type,
            )

        pattern = self._compiled_patterns[trigger.name]
        match = pattern.search(text)

        if match:
            matched_text = match.group(0)
            return TriggerMatch(
                triggered=True,
                confidence=trigger.confidence,
                trigger_type=trigger.trigger_type,
                matched_pattern=trigger.pattern,
                matched_text=matched_text,
            )

        return TriggerMatch(
            triggered=False,
            confidence=0.0,
            trigger_type=trigger.trigger_type,
        )

    def _check_intent(
        self, trigger: TriggerConfig, text: str
    ) -> TriggerMatch:
        """Check intent-based trigger (simplified implementation)."""
        # This is a placeholder for more sophisticated intent detection
        # In a full implementation, this could use ML-based classification
        return self._check_keywords(trigger, text)

    def add_custom_trigger(
        self, func: Callable[[str], TriggerMatch]
    ) -> None:
        """
        Add a custom trigger function.

        Args:
            func: Function that takes text and returns TriggerMatch
        """
        self._custom_triggers.append(func)

    def remove_trigger(self, name: str) -> bool:
        """
        Remove a trigger by name.

        Args:
            name: Name of the trigger to remove

        Returns:
            True if trigger was removed, False if not found
        """
        for i, trigger in enumerate(self.triggers):
            if trigger.name == name:
                self.triggers.pop(i)
                if name in self._compiled_patterns:
                    del self._compiled_patterns[name]
                return True
        return False

    def set_threshold(self, threshold: float) -> None:
        """Set the confidence threshold."""
        self.threshold = max(0.0, min(1.0, threshold))

    def get_trigger_info(self) -> list[dict]:
        """Get information about all configured triggers."""
        return [
            {
                "name": trigger.name,
                "type": trigger.trigger_type.value,
                "confidence": trigger.confidence,
                "description": trigger.description,
            }
            for trigger in self.triggers
        ]
