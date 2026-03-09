"""
Conversation Engine — the core orchestrator.

This is the brain of the system. For each user message:
1. Retrieve relevant context from RAG
2. Build the full prompt (system + context + history + question)
3. Call the LLM for a response
4. Send the response text to the LiveAvatar for lip-sync speech
5. Store the message in conversation history
"""

from typing import Optional, AsyncIterator
import structlog

from models.tenant import Tenant
from services.llm.base import LLMMessage, LLMResponse
from services.llm.provider_factory import LLMProviderFactory
from services.rag.pipeline import RAGPipeline
from services.liveavatar_client import LiveAvatarClient
from services.conversation.context_builder import ContextBuilder
from services.conversation.memory import ConversationMemory

logger = structlog.get_logger()


class ConversationEngine:
    """
    Orchestrates the full conversation flow:
    User Question → RAG → LLM → Avatar Speech
    """

    def __init__(self):
        self.rag = RAGPipeline()
        self.liveavatar = LiveAvatarClient()
        self._memories: dict[str, ConversationMemory] = {}

    def _get_memory(self, session_id: str) -> ConversationMemory:
        """Get or create conversation memory for a session."""
        if session_id not in self._memories:
            self._memories[session_id] = ConversationMemory()
        return self._memories[session_id]

    async def process_message(
        self,
        tenant: Tenant,
        session_id: str,
        user_message: str,
        heygen_session_id: Optional[str] = None,
        send_to_avatar: bool = True,
    ) -> dict:
        """
        Process a user message through the full pipeline.

        Args:
            tenant: The tenant configuration
            session_id: Internal session ID
            user_message: User's question/input
            heygen_session_id: HeyGen session ID (for avatar)
            send_to_avatar: Whether to send response to avatar

        Returns:
            dict with 'response', 'context_used', 'sources'
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
            # Use the first (primary) knowledge base
            kb = tenant.knowledge_bases[0]
            rag_context = await self.rag.build_context(
                collection_name=kb.qdrant_collection,
                query=user_message,
                top_k=5,
                max_context_length=3000,
            )
            if rag_context:
                # Extract source info
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
            max_tokens=500,  # Keep avatar responses concise
        )

        response_text = llm_response.content

        # Step 4: Send to Avatar (if active session)
        avatar_result = None
        if send_to_avatar and heygen_session_id:
            try:
                avatar_result = await self.liveavatar.send_text_streaming(
                    session_id=heygen_session_id,
                    text=response_text,
                )
                logger.info("Response sent to avatar",
                            heygen_session=heygen_session_id)
            except Exception as e:
                logger.error("Failed to send to avatar", error=str(e))

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
            "avatar_sent": avatar_result is not None,
        }

    async def process_message_stream(
        self,
        tenant: Tenant,
        session_id: str,
        user_message: str,
        heygen_session_id: Optional[str] = None,
    ) -> AsyncIterator[dict]:
        """
        Stream-process a user message.

        Yields partial responses as they come in from the LLM,
        and sends completed sentences to the avatar in real-time.

        This creates a more natural conversation feel —
        the avatar starts speaking before the full response is generated.
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

                # Send completed sentence to avatar
                if heygen_session_id and sentence:
                    try:
                        await self.liveavatar.send_text(
                            heygen_session_id, sentence
                        )
                        yield {"type": "avatar_sent", "sentence": sentence}
                    except Exception as e:
                        logger.error("Avatar send error", error=str(e))

        # Send any remaining text
        if sentence_buffer.strip() and heygen_session_id:
            try:
                await self.liveavatar.send_text(
                    heygen_session_id, sentence_buffer.strip()
                )
            except Exception:
                pass

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
        await self.rag.close()
        await self.liveavatar.close()
