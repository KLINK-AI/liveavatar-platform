"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional


@dataclass
class LLMMessage:
    """A single message in the conversation."""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str
    model: str
    provider: str
    usage: dict = field(default_factory=dict)
    finish_reason: Optional[str] = None


class BaseLLMProvider(ABC):
    """
    Abstract interface for LLM providers.

    All LLM implementations must conform to this interface,
    making them interchangeable per tenant.
    """

    provider_name: str = "base"

    @abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """
        Send a chat completion request and return the full response.

        Args:
            messages: Conversation history (system + user + assistant messages)
            model: Model override (uses default if not set)
            temperature: Creativity parameter (0.0 = deterministic, 1.0 = creative)
            max_tokens: Maximum response length
        """
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        """
        Stream a chat completion response token by token.
        Yields text chunks as they arrive.

        This is important for real-time avatar interaction:
        we can start sending sentences to the avatar while
        the LLM is still generating.
        """
        ...

    async def chat_with_context(
        self,
        system_prompt: str,
        user_message: str,
        context: str = "",
        history: list[LLMMessage] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Convenience method: Build messages from system prompt,
        RAG context, and user message, then call chat().

        Args:
            system_prompt: The tenant's system prompt (avatar personality)
            user_message: The user's current question
            context: RAG-retrieved context to include
            history: Previous conversation messages
        """
        messages = [LLMMessage(role="system", content=system_prompt)]

        if context:
            messages.append(LLMMessage(
                role="system",
                content=f"Nutze den folgenden Kontext, um die Frage zu beantworten. "
                        f"Wenn der Kontext die Frage nicht beantwortet, sage das ehrlich.\n\n"
                        f"KONTEXT:\n{context}"
            ))

        if history:
            messages.extend(history)

        messages.append(LLMMessage(role="user", content=user_message))

        return await self.chat(messages, **kwargs)

    async def close(self):
        """Clean up resources."""
        pass
