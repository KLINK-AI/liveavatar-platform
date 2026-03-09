"""Anthropic Claude LLM Provider."""

from typing import AsyncIterator, Optional
import anthropic
import structlog

from services.llm.base import BaseLLMProvider, LLMMessage, LLMResponse

logger = structlog.get_logger()


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API provider."""

    provider_name = "anthropic"

    def __init__(self, api_key: str, default_model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.default_model = default_model

    async def chat(
        self,
        messages: list[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        model = model or self.default_model

        # Anthropic uses system prompt separately
        system_prompt = ""
        chat_messages = []
        for msg in messages:
            if msg.role == "system":
                system_prompt += msg.content + "\n"
            else:
                chat_messages.append({"role": msg.role, "content": msg.content})

        # Ensure messages alternate user/assistant
        if not chat_messages or chat_messages[0]["role"] != "user":
            chat_messages.insert(0, {"role": "user", "content": "Hallo"})

        response = await self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt.strip(),
            messages=chat_messages,
            temperature=temperature,
        )

        content = response.content[0].text if response.content else ""
        return LLMResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            finish_reason=response.stop_reason,
        )

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        model = model or self.default_model

        system_prompt = ""
        chat_messages = []
        for msg in messages:
            if msg.role == "system":
                system_prompt += msg.content + "\n"
            else:
                chat_messages.append({"role": msg.role, "content": msg.content})

        if not chat_messages or chat_messages[0]["role"] != "user":
            chat_messages.insert(0, {"role": "user", "content": "Hallo"})

        async with self.client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt.strip(),
            messages=chat_messages,
            temperature=temperature,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def close(self):
        await self.client.close()
