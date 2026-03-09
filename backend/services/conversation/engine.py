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

    def _get_memory(self, session_id: str) -> ConversationMemory:
        """Get or create conversation memory for a session."""
        if session_id not in self._memories:
            self._memories[session_id] = ConversationMemory()
        return self._memories[session_id]

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
    ) -> dict:
        """
        Process a user message through the full pipeline.

        Flow: Message → RAG → LLM → TTS → WebSocket → Avatar

        Args:
            tenant: The tenant configuration
            session_id: Internal session ID
            user_message: User's question/input
            send_to_avatar: Whether to send response to avatar via audio

        Returns:
            dict with 'response', 'context_used', 'sources', etc.
        """
        logger.info("Processing message",
                     tenant=tenant.slug,
                     session=session_id,
                     message_length=len(user_message))

        memory = self._get_memory(session_id)

        # Step 1: RAG Retrieval
        rag_context = ""
        sources = []
        if tenant.knowledge_bases:
            kb = tenant.knowledge_bases[0]
            rag_context = await self.rag.build_context(
                collection_name=kb.qdrant_collection,
                query=user_message,
                top_k=5,
                max_context_length=3000,
            )
            if rag_context:
                results = await self.rag.retrieve(
                    kb.qdrant_collection, user_message, top_k=3
                )
                sources = [{"source": r["source"], "score": r["score"]} for r in results]

        # Step 2: Build prompt
        messages = ContextBuilder.build_messages(
            system_prompt=tenant.system_prompt,
            user_message=user_message,
            rag_context=rag_context,
            history=memory.get_history(),
        )

        # Step 3: LLM Call
        llm_provider = LLMProviderFactory.get_provider_for_tenant(tenant)
        llm_response = await llm_provider.chat(
            messages=messages,
            model=tenant.llm_model,
            temperature=0.7,
            max_tokens=500,
        )

        response_text = llm_response.content

        # Step 4: TTS → WebSocket → Avatar (LITE Mode audio pipeline)
        avatar_sent = False
        if send_to_avatar:
            avatar_sent = await self._send_audio_to_avatar(
                session_id=session_id,
                tenant=tenant,
                text=response_text,
            )

        # Step 5: Update conversation memory
        memory.add_user_message(user_message)
        memory.add_assistant_message(response_text)

        return {
            "response": response_text,
            "context_used": bool(rag_context),
            "sources": sources,
            "llm_model": llm_response.model,
            "llm_provider": llm_response.provider,
            "usage": llm_response.usage,
            "avatar_sent": avatar_sent,
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

        # RAG Retrieval
        rag_context = ""
        if tenant.knowledge_bases:
            kb = tenant.knowledge_bases[0]
            rag_context = await self.rag.build_context(
                kb.qdrant_collection, user_message
            )

        # Build prompt
        messages = ContextBuilder.build_messages(
            system_prompt=tenant.system_prompt,
            user_message=user_message,
            rag_context=rag_context,
            history=memory.get_history(),
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

    def clear_memory(self, session_id: str):
        """Clear conversation history for a session."""
        if session_id in self._memories:
            self._memories[session_id].clear()
            del self._memories[session_id]

    async def close(self):
        """Release all resources."""
        await self.rag.close()
        await TTSProviderFactory.close_all()
        # Disconnect all WebSocket managers
        for ws in self._ws_managers.values():
            await ws.disconnect()
        self._ws_managers.clear()
