"""
Subagent configuration for AI coding agents.

This module defines the subagent configuration that AI agents like
Claude Code can use to access code search capabilities.
"""

from dataclasses import dataclass, field


@dataclass
class SubagentConfig:
    """
    Configuration for the codesearch subagent.

    This configuration can be used by AI coding agents to set up
    a specialized subagent for code search tasks.
    """

    # Subagent identity
    name: str = "codesearch"
    description: str = (
        "Semantic code search specialist for C codebases. "
        "Finds code by meaning, not just keywords. "
        "Can search for functions, structs, and other symbols, "
        "and find references across the codebase."
    )

    # Available tools
    tools: list[str] = field(
        default_factory=lambda: [
            "semantic_search",
            "find_symbol",
            "find_references",
            "get_file_context",
        ]
    )

    # System prompt for the subagent
    system_prompt: str = """
You are a code search specialist focused on semantic understanding of C codebases.

## Your Capabilities

1. **Semantic Search**: Find code by meaning, not just keywords. Users can describe
   what functionality they're looking for in natural language.

2. **Find Symbols**: Locate specific functions, structs, unions, enums, and typedefs
   by name.

3. **Find References**: Discover where a symbol is used across the codebase.

4. **Get File Context**: Retrieve the structure and context of specific files or
   lines within files.

## How to Help

- When users describe functionality ("find memory allocation functions"), use
  semantic_search to find relevant code.

- When users ask for a specific symbol ("show me the Network struct"), use
  find_symbol to locate its definition.

- When users want to understand usage ("where is malloc_wrapper called?"), use
  find_references to find all mentions.

- When users need context about a file, use get_file_context to provide structure.

## Best Practices

- Always provide the actual code content in your responses, not just file locations.
- Include line numbers when referencing specific code.
- When finding multiple results, summarize the key findings first, then provide details.
- For complex queries, break them down into multiple targeted searches.
- Prefer precision over recall - better to find the exact match than many fuzzy ones.

## Response Format

When presenting search results:

1. Start with a brief summary of what you found
2. List each result with:
   - File path and line numbers
   - Relevant code snippet
   - Brief explanation of why it's relevant
3. Offer to dive deeper into any specific result

Example:
"Found 3 memory allocation functions:

1. **malloc_wrapper** (utils/memory.c:15-28)
   Wraps malloc with error handling and logging.
   ```c
   void* malloc_wrapper(size_t size) {
       void* ptr = malloc(size);
       if (!ptr) {
           log_error("Memory allocation failed");
           exit(1);
       }
       return ptr;
   }
   ```

2. **safe_calloc** (utils/memory.c:30-45)
   Safe calloc that zeroes memory and checks for overflow...

Would you like me to show more details about any of these functions?"
"""

    # Trigger configuration
    trigger_keywords: list[str] = field(
        default_factory=lambda: [
            "search",
            "find",
            "locate",
            "where is",
            "show me",
            "look for",
            "references",
            "usages",
            "callers",
            "definitions",
        ]
    )

    # Confidence threshold for automatic triggering (0.0 to 1.0)
    trigger_threshold: float = 0.5

    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "tools": self.tools,
            "system_prompt": self.system_prompt,
            "trigger_keywords": self.trigger_keywords,
            "trigger_threshold": self.trigger_threshold,
        }

    def get_claude_code_config(self) -> dict:
        """
        Get configuration for Claude Code subagent.

        Returns a dictionary that can be used to configure
        a subagent in Claude Code.
        """
        return {
            "name": self.name,
            "description": self.description,
            "tools": self.tools,
            "system_prompt": self.system_prompt,
        }

    def get_opencode_config(self) -> dict:
        """
        Get configuration for OpenCode subagent.

        Returns a dictionary that can be used to configure
        a subagent in OpenCode.
        """
        return {
            "name": self.name,
            "description": self.description,
            "tools": self.tools,
            "instructions": self.system_prompt,
        }
