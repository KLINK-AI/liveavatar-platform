"""
Conversation Memory — manages conversation history for context.

Keeps a sliding window of recent messages to include in the LLM prompt.
"""

from dataclasses import dataclass, field
from services.llm.base import LLMMessage


@dataclass
class ConversationMemory:
    """
    Manages conversation history for a single session.

    Keeps the last N message pairs (user + assistant) to provide
    context to the LLM without exceeding token limits.
    """

    max_messages: int = 20  # Max messages to keep in memory
    messages: list[LLMMessage] = field(default_factory=list)

    def add_user_message(self, content: str):
        """Add a user message to history."""
        self.messages.append(LLMMessage(role="user", content=content))
        self._trim()

    def add_assistant_message(self, content: str):
        """Add an assistant response to history."""
        self.messages.append(LLMMessage(role="assistant", content=content))
        self._trim()

    def get_history(self) -> list[LLMMessage]:
        """Get the current conversation history."""
        return self.messages.copy()

    def clear(self):
        """Clear all conversation history."""
        self.messages.clear()

    def _trim(self):
        """Keep only the most recent messages within the limit."""
        if len(self.messages) > self.max_messages:
            # Always keep pairs — trim from the start
            overflow = len(self.messages) - self.max_messages
            self.messages = self.messages[overflow:]
