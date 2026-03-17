"""
Conversation Engine — the core orchestrator.

This is the brain of the system. For each user message:
1. Retrieve relevant context from RAG
2. Build the full prompt (system + context + history + question)
3. Call the LLM for a response
4. Convert response text to audio via TTS (ElevenLabs)
5. Send PCM audio chunks via WebSocket to LiveAvatar for lip-sync
6. Store the message in conversation history

LITE Mode Audio Pipeline (NEW):
  LLM Text → ElevenLabs TTS → PCM 16Bit 24KHz → Base64 →
  WebSocket agent.speak → LiveAvatar renders lip-sync video

OLD (removed): Text → HeyGen streaming.task (text-based lip-sync)
"""

from typing import Optional, AsyncIterator
import asyncio
import time
import structlog

from config import get_settings
from models.tenant import Tenant
from services.llm.base import LLMMessage, LLMResponse
from services.llm.provider_factory import LLMProviderFactory
from services.rag.pipeline import RAGPipeline
from services.tts import TTSProviderFactory
from services.liveavatar_ws import LiveAvatarWSManager
from services.conversation.context_builder import ContextBuilder
from services.conversation.memory import ConversationMemory

logger = structlog.get_logger()
settings = get_settings()


class ConversationEngine:
    """
    Orchestrates the full conversation flow:
    User Question → RAG → LLM → TTS → Avatar Speech (audio)
    """

    def __init__(self):
        self.rag = RAGPipeline()
        self._memories: dict[str, ConversationMemory] = {}
        self._ws_managers: dict[str, LiveAvatarWSManager] = {}
        self._session_languages: dict[str, str] = {}  # session_id → language code
        self._greeting_audio_cache: dict[str, list[bytes]] = {}  # cache_key → audio chunks

    def _get_memory(self, session_id: str) -> ConversationMemory:
        """Get or create conversation memory for a session."""
        if session_id not in self._memories:
            self._memories[session_id] = ConversationMemory()
        return self._memories[session_id]

    def set_session_language(self, session_id: str, language: str):
        """Set the language for a session. Used by all subsequent LLM calls."""
        self._session_languages[session_id] = language
        logger.info("Session language set", session_id=session_id, language=language)

    def get_session_language(self, session_id: str) -> str:
        """Get the language for a session (defaults to 'de')."""
        return self._session_languages.get(session_id, "de")

    def register_ws_manager(self, session_id: str, ws_manager: LiveAvatarWSManager):
        """
        Register a WebSocket manager for a session.
        Called by the session creation route after connecting to LiveAvatar.
        """
        self._ws_managers[session_id] = ws_manager
        logger.info("WS manager registered for session", session_id=session_id)

    def unregister_ws_manager(self, session_id: str):
        """Remove WebSocket manager when session ends."""
        self._ws_managers.pop(session_id, None)

    def _get_tts_for_tenant(self, tenant: Tenant):
        """Get TTS provider for a tenant (per-tenant key or global)."""
        return TTSProviderFactory.get_provider(
            provider_name="elevenlabs",
            api_key=tenant.elevenlabs_api_key,
        )

    def _get_voice_id(self, tenant: Tenant) -> str:
        """Resolve the ElevenLabs voice ID for a tenant."""
        voice_id = (
            tenant.elevenlabs_voice_id
            or settings.elevenlabs_default_voice_id
        )
        if not voice_id:
            raise ValueError(
                f"No ElevenLabs voice_id configured for tenant {tenant.slug}. "
                "Set elevenlabs_voice_id on tenant or elevenlabs_default_voice_id in config."
            )
        return voice_id

    async def _send_audio_to_avatar(
        self,
        session_id: str,
        tenant: Tenant,
        text: str,
    ) -> bool:
        """
        Core LITE Mode pipeline: Text → TTS → Audio → WebSocket → Avatar.

        1. ElevenLabs converts text to PCM 16Bit 24KHz audio chunks
        2. Each chunk is sent via WebSocket `agent.speak` command
        3. LiveAvatar renders lip-sync video in real-time

        Returns True if audio was sent successfully.
        """
        ws_manager = self._ws_managers.get(session_id)
        if not ws_manager or not ws_manager.is_connected:
            logger.warning("No WebSocket connection for session", session_id=session_id)
            return False

        tts = self._get_tts_for_tenant(tenant)
        voice_id = self._get_voice_id(tenant)

        try:
            # Signal avatar: we're about to speak
            await ws_manager.send_start_listening()

            # Stream TTS audio chunks to avatar
            chunk_count = 0
            async for audio_chunk in tts.text_to_speech_stream(
                text=text,
                voice_id=voice_id,
                sample_rate=settings.tts_sample_rate,
            ):
                await ws_manager.send_speak_from_bytes(audio_chunk)
                chunk_count += 1

            # Signal: done speaking
            await ws_manager.send_speak_end()

            logger.info(
                "Audio sent to avatar",
                session_id=session_id,
                text_length=len(text),
                audio_chunks=chunk_count,
            )
            return True

        except Exception as e:
            logger.error("Failed to send audio to avatar", error=str(e), session_id=session_id)
            return False

    async def process_message(
        self,
        tenant: Tenant,
        session_id: str,
        user_message: str,
        send_to_avatar: bool = True,
        knowledge_bases: list | None = None,
    ) -> dict:
        """
        Process a user message through the full pipeline.

        Flow: Message → RAG → LLM → TTS → WebSocket → Avatar

        Args:
            tenant: The tenant configuration
            session_id: Internal session ID
            user_message: User's question/input
            send_to_avatar: Whether to send response to avatar via audio
            knowledge_bases: Optional explicit list of KBs (bypasses tenant.knowledge_bases)

        Returns:
            dict with 'response', 'context_used', 'sources', etc.
        """
        t_start = time.monotonic()
        logger.info("Processing message",
                     tenant=tenant.slug,
                     session=session_id,
                     message_length=len(user_message))

        memory = self._get_memory(session_id)

        # ── Step 1: RAG Retrieval (with timing) ──
        # Parallel search across ALL knowledge bases using asyncio.gather().
        # The embedding is cached after the first call, so parallel KB searches
        # re-use the same embedding vector (cache hit) — no extra API cost.
        t_rag_start = time.monotonic()
        kbs = knowledge_bases if knowledge_bases is not None else getattr(tenant, 'knowledge_bases', [])
        rag_context = ""
        sources = []
        if kbs:
            async def _search_kb(kb):
                """Search a single KB, return (context, sources, kb_name) or empty."""
                try:
                    ctx, srcs = await self.rag.build_context_with_sources(
                        collection_name=kb.qdrant_collection,
                        query=user_message,
                        top_k=5,
                        max_context_length=3000,
                    )
                    return ctx, srcs, kb.name
                except Exception as e:
                    logger.warning("RAG retrieval failed for KB",
                                   kb_name=kb.name,
                                   collection=kb.qdrant_collection,
                                   error=str(e))
                    return "", [], kb.name

            if len(kbs) == 1:
                # Single KB — direct call (no gather overhead)
                rag_context, sources, _ = await _search_kb(kbs[0])
            else:
                # Multiple KBs — search in parallel
                logger.info("Parallel RAG search", kb_count=len(kbs),
                            kbs=[kb.name for kb in kbs])
                results = await asyncio.gather(*[_search_kb(kb) for kb in kbs])
                # Pick the first result with context (prefer most relevant)
                for ctx, srcs, kb_name in results:
                    if ctx:
                        rag_context = ctx
                        sources = srcs
                        logger.info("RAG context found (parallel)",
                                    kb_name=kb_name,
                                    context_length=len(ctx),
                                    sources_count=len(srcs))
                        break
        t_rag_end = time.monotonic()
        duration_rag_ms = round((t_rag_end - t_rag_start) * 1000)

        # ── Step 2: Build prompt (with session language) ──
        session_language = self.get_session_language(session_id)
        messages = ContextBuilder.build_messages(
            system_prompt=tenant.system_prompt,
            user_message=user_message,
            rag_context=rag_context,
            history=memory.get_history(),
            language=session_language,
        )

        # ── Step 3: LLM Call (with timing) ──
        t_llm_start = time.monotonic()
        llm_provider = LLMProviderFactory.get_provider_for_tenant(tenant)
        llm_response = await llm_provider.chat(
            messages=messages,
            model=tenant.llm_model,
            temperature=0.7,
            max_tokens=500,
        )
        t_llm_end = time.monotonic()
        duration_llm_ms = round((t_llm_end - t_llm_start) * 1000)

        response_text = llm_response.content

        # ── Step 4: TTS → WebSocket → Avatar (with timing) ──
        t_tts_start = time.monotonic()
        avatar_sent = False
        if send_to_avatar:
            avatar_sent = await self._send_audio_to_avatar(
                session_id=session_id,
                tenant=tenant,
                text=response_text,
            )
        t_tts_end = time.monotonic()
        duration_tts_ms = round((t_tts_end - t_tts_start) * 1000)

        # ── Step 5: Update conversation memory ──
        memory.add_user_message(user_message)
        memory.add_assistant_message(response_text)

        duration_total_ms = round((time.monotonic() - t_start) * 1000)
        logger.info("Message processed — TIMING BREAKDOWN",
                     tenant=tenant.slug,
                     session=session_id,
                     rag_ms=duration_rag_ms,
                     llm_ms=duration_llm_ms,
                     tts_ms=duration_tts_ms,
                     total_ms=duration_total_ms,
                     rag_used=bool(rag_context),
                     llm_model=llm_response.model)

        return {
            "response": response_text,
            "context_used": bool(rag_context),
            "sources": sources,
            "llm_model": llm_response.model,
            "llm_provider": llm_response.provider,
            "usage": llm_response.usage,
            "avatar_sent": avatar_sent,
            "duration_rag_ms": duration_rag_ms,
            "duration_llm_ms": duration_llm_ms,
            "duration_tts_ms": duration_tts_ms,
        }

    async def process_message_stream(
        self,
        tenant: Tenant,
        session_id: str,
        user_message: str,
    ) -> AsyncIterator[dict]:
        """
        Stream-process a user message.

        Yields partial responses as they come in from the LLM,
        and sends completed sentences to the avatar via audio in real-time.

        Flow per sentence:
          LLM tokens → sentence complete → TTS → audio chunks → WebSocket → avatar

        This creates a natural conversation feel —
        the avatar starts speaking the first sentence before
        the full response is generated.
        """
        memory = self._get_memory(session_id)

        # RAG Retrieval — parallel search across all KBs
        rag_context = ""
        kbs = getattr(tenant, 'knowledge_bases', [])
        if kbs:
            async def _search_kb_stream(kb):
                try:
                    return await self.rag.build_context(kb.qdrant_collection, user_message), kb.name
                except Exception:
                    return "", kb.name

            if len(kbs) == 1:
                rag_context, _ = await _search_kb_stream(kbs[0])
            else:
                results = await asyncio.gather(*[_search_kb_stream(kb) for kb in kbs])
                for ctx, _ in results:
                    if ctx:
                        rag_context = ctx
                        break

        # Build prompt (with session language)
        session_language = self.get_session_language(session_id)
        messages = ContextBuilder.build_messages(
            system_prompt=tenant.system_prompt,
            user_message=user_message,
            rag_context=rag_context,
            history=memory.get_history(),
            language=session_language,
        )

        # Stream LLM response
        llm_provider = LLMProviderFactory.get_provider_for_tenant(tenant)
        full_response = ""
        sentence_buffer = ""

        async for token in llm_provider.chat_stream(messages=messages, max_tokens=500):
            full_response += token
            sentence_buffer += token

            # Yield token to frontend for live text display
            yield {"type": "token", "content": token}

            # Check if we have a complete sentence
            if any(sentence_buffer.rstrip().endswith(p) for p in ".!?"):
                sentence = sentence_buffer.strip()
                sentence_buffer = ""

                # Send completed sentence to avatar via TTS → audio → WebSocket
                if sentence:
                    sent = await self._send_audio_to_avatar(
                        session_id=session_id,
                        tenant=tenant,
                        text=sentence,
                    )
                    if sent:
                        yield {"type": "avatar_sent", "sentence": sentence}

        # Send any remaining text
        if sentence_buffer.strip():
            sent = await self._send_audio_to_avatar(
                session_id=session_id,
                tenant=tenant,
                text=sentence_buffer.strip(),
            )
            if sent:
                yield {"type": "avatar_sent", "sentence": sentence_buffer.strip()}

        # Update memory
        memory.add_user_message(user_message)
        memory.add_assistant_message(full_response)

        yield {"type": "done", "full_response": full_response}

    async def _send_cached_audio_to_avatar(
        self,
        session_id: str,
        audio_chunks: list[bytes],
    ) -> bool:
        """Send pre-cached audio chunks directly to avatar (skip TTS)."""
        t0 = time.monotonic()
        ws_manager = self._ws_managers.get(session_id)
        if not ws_manager or not ws_manager.is_connected:
            logger.warning("No WebSocket connection for cached audio", session_id=session_id)
            return False

        try:
            await ws_manager.send_start_listening()
            for chunk in audio_chunks:
                await ws_manager.send_speak_from_bytes(chunk)
            await ws_manager.send_speak_end()
            elapsed = (time.monotonic() - t0) * 1000
            total_bytes = sum(len(c) for c in audio_chunks)
            logger.info(
                "Cached audio sent to avatar — TIMING",
                session_id=session_id,
                chunks=len(audio_chunks),
                total_bytes=total_bytes,
                send_ms=round(elapsed),
            )
            return True
        except Exception as e:
            logger.error("Failed to send cached audio", error=str(e), session_id=session_id)
            return False

    async def pre_generate_greeting_audio(
        self,
        tenant: Tenant,
        greeting_text: str,
        language: str = "de",
    ):
        """
        Pre-generate and cache greeting audio WITHOUT sending it.
        Call this during session creation (before WS is ready) to
        eliminate TTS latency from the greeting pipeline.
        """
        if not greeting_text:
            return

        cache_key = f"{tenant.slug}:{language}:{hash(greeting_text)}"
        if cache_key in self._greeting_audio_cache:
            logger.info("Greeting audio already cached", cache_key=cache_key)
            return

        t0 = time.monotonic()
        # Use turbo model for faster greeting generation
        tts = TTSProviderFactory.get_provider(
            provider_name="elevenlabs",
            api_key=tenant.elevenlabs_api_key,
            model_id=settings.elevenlabs_turbo_model_id,
        )
        voice_id = self._get_voice_id(tenant)
        chunks: list[bytes] = []

        try:
            async for audio_chunk in tts.text_to_speech_stream(
                text=greeting_text,
                voice_id=voice_id,
                sample_rate=settings.tts_sample_rate,
            ):
                chunks.append(audio_chunk)

            if chunks:
                self._greeting_audio_cache[cache_key] = chunks
                elapsed = (time.monotonic() - t0) * 1000
                logger.info(
                    "Greeting audio PRE-GENERATED and cached",
                    cache_key=cache_key,
                    chunks=len(chunks),
                    elapsed_ms=round(elapsed),
                )
        except Exception as e:
            logger.warning("Failed to pre-generate greeting audio", error=str(e))

    async def send_greeting_direct(
        self,
        session_id: str,
        tenant: Tenant,
        greeting_text: str,
        language: str = "de",
    ) -> bool:
        """
        Send a pre-resolved greeting text directly to the avatar.
        Uses an in-memory audio cache: first call generates TTS, subsequent
        calls for the same tenant+language+text skip TTS entirely (~0ms).
        Uses turbo model for faster first-time generation.
        """
        t_start = time.monotonic()
        self.set_session_language(session_id, language)

        if not greeting_text:
            logger.info("No greeting text provided", session_id=session_id)
            return False

        # Check greeting audio cache (key = tenant_slug + language + text hash)
        cache_key = f"{tenant.slug}:{language}:{hash(greeting_text)}"
        cached_chunks = self._greeting_audio_cache.get(cache_key)

        if cached_chunks:
            t_cache = time.monotonic()
            logger.info(
                "Sending CACHED greeting audio (skip TTS)",
                language=language,
                cache_key=cache_key,
                chunks=len(cached_chunks),
                cache_lookup_ms=round((t_cache - t_start) * 1000),
            )
            sent = await self._send_cached_audio_to_avatar(session_id, cached_chunks)
            t_sent = time.monotonic()
            logger.info(
                "CACHED greeting send complete",
                sent=sent,
                send_ms=round((t_sent - t_cache) * 1000),
                total_ms=round((t_sent - t_start) * 1000),
            )
        else:
            logger.info(
                "Sending greeting (direct, first time — will cache, turbo model)",
                language=language,
                greeting_length=len(greeting_text),
            )
            # Generate TTS with TURBO model and cache the audio chunks
            sent, chunks = await self._send_audio_to_avatar_and_cache(
                session_id=session_id,
                tenant=tenant,
                text=greeting_text,
                use_turbo=True,
            )
            t_done = time.monotonic()
            if sent and chunks:
                self._greeting_audio_cache[cache_key] = chunks
                logger.info(
                    "Greeting audio generated + cached",
                    cache_key=cache_key,
                    chunks=len(chunks),
                    total_ms=round((t_done - t_start) * 1000),
                )

        if sent:
            memory = self._get_memory(session_id)
            memory.add_assistant_message(greeting_text)

        return sent

    async def _send_audio_to_avatar_and_cache(
        self,
        session_id: str,
        tenant: Tenant,
        text: str,
        use_turbo: bool = False,
    ) -> tuple[bool, list[bytes]]:
        """Like _send_audio_to_avatar but also returns the audio chunks for caching."""
        ws_manager = self._ws_managers.get(session_id)
        if not ws_manager or not ws_manager.is_connected:
            return False, []

        if use_turbo:
            tts = TTSProviderFactory.get_provider(
                provider_name="elevenlabs",
                api_key=tenant.elevenlabs_api_key,
                model_id=settings.elevenlabs_turbo_model_id,
            )
        else:
            tts = self._get_tts_for_tenant(tenant)
        voice_id = self._get_voice_id(tenant)
        cached_chunks: list[bytes] = []

        try:
            await ws_manager.send_start_listening()

            async for audio_chunk in tts.text_to_speech_stream(
                text=text,
                voice_id=voice_id,
                sample_rate=settings.tts_sample_rate,
            ):
                await ws_manager.send_speak_from_bytes(audio_chunk)
                cached_chunks.append(audio_chunk)

            await ws_manager.send_speak_end()
            return True, cached_chunks

        except Exception as e:
            logger.error("Failed to send audio (with cache)", error=str(e))
            return False, []

    async def send_greeting(
        self,
        session_id: str,
        tenant: Tenant,
        language: str = "de",
    ) -> bool:
        """
        Send the tenant's greeting message as avatar speech.

        Called after session start + language selection.
        Uses greeting_translations for non-default languages,
        falls back to greeting_text (default language).

        Returns True if greeting was spoken by the avatar.
        """
        # Also set the session language (in case it wasn't set via _setup_session_services yet)
        self.set_session_language(session_id, language)

        # Get greeting text for selected language
        greeting = None
        if language == tenant.default_language:
            greeting = tenant.greeting_text
        elif tenant.greeting_translations:
            greeting = tenant.greeting_translations.get(language)

        # Fallback to default greeting
        if not greeting:
            greeting = tenant.greeting_text

        if not greeting:
            logger.info("No greeting configured", tenant=tenant.slug, language=language)
            return False

        logger.info(
            "Sending greeting to avatar",
            tenant=tenant.slug,
            language=language,
            greeting_length=len(greeting),
        )

        # Send greeting as avatar speech (TTS → WebSocket → Avatar)
        sent = await self._send_audio_to_avatar(
            session_id=session_id,
            tenant=tenant,
            text=greeting,
        )

        # Store greeting in conversation memory
        if sent:
            memory = self._get_memory(session_id)
            memory.add_assistant_message(greeting)

        return sent

    def clear_memory(self, session_id: str):
        """Clear conversation history and language for a session."""
        if session_id in self._memories:
            self._memories[session_id].clear()
            del self._memories[session_id]
        self._session_languages.pop(session_id, None)

    async def close(self):
        """Release all resources."""
        await self.rag.close()
        await TTSProviderFactory.close_all()
        # Disconnect all WebSocket managers
        for ws in self._ws_managers.values():
            await ws.disconnect()
        self._ws_managers.clear()
