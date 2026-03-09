"""
Context Builder — assembles the full prompt for the LLM.

Combines:
- System prompt (avatar personality, per tenant)
- RAG context (retrieved knowledge)
- Conversation history
- User's current question
"""

from services.llm.base import LLMMessage


class ContextBuilder:
    """Builds the complete message list for LLM calls."""

    @staticmethod
    def build_messages(
        system_prompt: str,
        user_message: str,
        rag_context: str = "",
        history: list[LLMMessage] | None = None,
        language: str = "de",
    ) -> list[LLMMessage]:
        """
        Assemble the complete message list for an LLM call.

        Args:
            system_prompt: Tenant's system prompt (avatar personality)
            user_message: User's current question
            rag_context: Retrieved context from RAG pipeline
            history: Previous conversation messages
            language: Response language

        Returns:
            Complete list of LLMMessages ready for the provider
        """
        messages = []

        # 1. System prompt — defines avatar personality
        full_system = system_prompt.strip()

        # Add language instruction if needed
        if language == "de":
            full_system += "\n\nAntworte immer auf Deutsch, es sei denn, der Nutzer fragt explizit in einer anderen Sprache."

        # Add conversation style for avatar
        full_system += (
            "\n\nWichtig: Deine Antworten werden von einem Video-Avatar gesprochen. "
            "Halte deine Antworten daher natürlich und gesprächsnah. "
            "Verwende keine Markdown-Formatierung, Aufzählungszeichen oder Sonderzeichen. "
            "Antworte in ganzen, fließenden Sätzen, die sich gut vorlesen lassen. "
            "Halte die Antworten prägnant — idealerweise 2-4 Sätze."
        )

        messages.append(LLMMessage(role="system", content=full_system))

        # 2. RAG context (if available)
        if rag_context:
            messages.append(LLMMessage(
                role="system",
                content=(
                    "Nutze den folgenden Kontext aus der Wissensdatenbank, "
                    "um die Frage des Nutzers zu beantworten. "
                    "Wenn der Kontext die Frage nicht beantwortet, "
                    "sage ehrlich, dass du dazu keine Informationen hast.\n\n"
                    f"KONTEXT:\n{rag_context}"
                ),
            ))

        # 3. Conversation history
        if history:
            for msg in history:
                messages.append(msg)

        # 4. Current user message
        messages.append(LLMMessage(role="user", content=user_message))

        return messages

    @staticmethod
    def estimate_tokens(messages: list[LLMMessage]) -> int:
        """Rough token estimate (4 chars ≈ 1 token)."""
        total_chars = sum(len(m.content) for m in messages)
        return total_chars // 4
