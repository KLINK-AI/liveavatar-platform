"""Groq LLM Provider — ultra-fast inference on LPU hardware.

Groq uses an OpenAI-compatible API, so we use the openai SDK
pointed at Groq's base URL. This gives us streaming support
with dramatically lower latency (Time-to-First-Token < 200ms).

Supported models:
  - llama-3.3-70b-versatile (best quality, still very fast)
  - llama-3.1-8b-instant (fastest, good for simple Q&A)
  - mixtral-8x7b-32768 (good balance)
"""

from typing import AsyncIterator, Optional
import openai
import structlog

from services.llm.base import BaseLLMProvider, LLMMessage, LLMResponse

logger = structlog.get_logger()

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider(BaseLLMProvider):
    """Groq API provider — OpenAI-compatible, runs on LPU hardware."""

    provider_name = "groq"

    def __init__(self, api_key: str, default_model: str = "llama-3.3-70b-versatile"):
        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=GROQ_BASE_URL,
        )
        self.default_model = default_model
        logger.info(
            "Groq provider initialized",
            model=default_model,
            base_url=GROQ_BASE_URL,
        )

    async def chat(
        self,
        messages: list[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        model = model or self.default_model

        response = await self.client.chat.completions.create(
            model=model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=model,
            provider=self.provider_name,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            finish_reason=choice.finish_reason,
        )

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        model = model or self.default_model

        stream = await self.client.chat.completions.create(
            model=model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def close(self):
        await self.client.close()
