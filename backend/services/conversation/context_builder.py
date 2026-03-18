"""
Context Builder — assembles the full prompt for the LLM.

Combines:
- System prompt (avatar personality, per tenant)
- RAG context (retrieved knowledge)
- Conversation history
- User's current question

Supports multi-language responses via language parameter.
"""

from services.llm.base import LLMMessage


# Language instructions for the LLM — tells it which language to respond in
LANGUAGE_INSTRUCTIONS = {
    "de": "Antworte immer auf Deutsch, es sei denn, der Nutzer fragt explizit in einer anderen Sprache.",
    "en": "Always respond in English unless the user explicitly asks in a different language.",
    "fr": "Réponds toujours en français, sauf si l'utilisateur pose explicitement sa question dans une autre langue.",
    "es": "Responde siempre en español, a menos que el usuario pregunte explícitamente en otro idioma.",
    "it": "Rispondi sempre in italiano, a meno che l'utente non chieda esplicitamente in un'altra lingua.",
    "nl": "Antwoord altijd in het Nederlands, tenzij de gebruiker expliciet in een andere taal vraagt.",
    "pt": "Responda sempre em português, a menos que o usuário pergunte explicitamente em outro idioma.",
    "pl": "Zawsze odpowiadaj po polsku, chyba że użytkownik wyraźnie zapyta w innym języku.",
    "ru": "Всегда отвечай на русском языке, если пользователь не попросит явно на другом языке.",
    "uk": "Завжди відповідай українською мовою, якщо користувач не попросить явно іншою мовою.",
    "tr": "Her zaman Türkçe yanıt ver, kullanıcı açıkça başka bir dilde sormadığı sürece.",
    "ar": "أجب دائماً باللغة العربية، إلا إذا طلب المستخدم صراحةً لغة أخرى.",
    "zh": "请始终用中文回答，除非用户明确要求使用其他语言。",
    "ja": "ユーザーが明示的に他の言語で質問しない限り、常に日本語で回答してください。",
    "ko": "사용자가 명시적으로 다른 언어로 질문하지 않는 한 항상 한국어로 답변하세요.",
    "hi": "हमेशा हिंदी में जवाब दें, जब तक कि उपयोगकर्ता स्पष्ट रूप से किसी अन्य भाषा में न पूछे।",
    "sv": "Svara alltid på svenska om inte användaren uttryckligen frågar på ett annat språk.",
    "no": "Svar alltid på norsk med mindre brukeren uttrykkelig spør på et annet språk.",
    "da": "Svar altid på dansk, medmindre brugeren udtrykkeligt spørger på et andet sprog.",
    "fi": "Vastaa aina suomeksi, ellei käyttäjä nimenomaisesti kysy toisella kielellä.",
    "el": "Απάντησε πάντα στα ελληνικά, εκτός αν ο χρήστης ρωτήσει ρητά σε άλλη γλώσσα.",
    "cs": "Vždy odpovídej česky, pokud uživatel výslovně nepožádá v jiném jazyce.",
    "ro": "Răspunde întotdeauna în română, cu excepția cazului în care utilizatorul întreabă explicit într-o altă limbă.",
    "hu": "Mindig magyarul válaszolj, kivéve, ha a felhasználó kifejezetten más nyelven kérdez.",
    "bg": "Винаги отговаряй на български, освен ако потребителят изрично не попита на друг език.",
    "hr": "Uvijek odgovaraj na hrvatskom, osim ako korisnik izričito ne pita na drugom jeziku.",
    "sk": "Vždy odpovedaj po slovensky, pokiaľ používateľ výslovne nepožiada v inom jazyku.",
    "sl": "Vedno odgovarjaj v slovenščini, razen če uporabnik izrecno vpraša v drugem jeziku.",
}

# Avatar-style conversation instructions per language
AVATAR_STYLE_INSTRUCTIONS = {
    "de": (
        "\n\nWichtig: Deine Antworten werden von einem Video-Avatar gesprochen. "
        "Halte deine Antworten kurz, direkt und natürlich. "
        "Verwende keine Markdown-Formatierung, Aufzählungszeichen oder Sonderzeichen. "
        "Antworte in 1-2 klaren Sätzen, die die Frage direkt beantworten. "
        "Nur bei komplexen Themen maximal 3 Sätze. Kein Smalltalk, keine Wiederholungen."
    ),
    "en": (
        "\n\nImportant: Your responses will be spoken by a video avatar. "
        "Keep your answers short, direct and natural. "
        "Do not use markdown formatting, bullet points, or special characters. "
        "Respond in 1-2 clear sentences that directly answer the question. "
        "Only use up to 3 sentences for complex topics. No filler, no repetition."
    ),
}


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
            language: Response language (ISO 639-1 code)

        Returns:
            Complete list of LLMMessages ready for the provider
        """
        messages = []

        # 1. System prompt — defines avatar personality
        full_system = system_prompt.strip()

        # Add language instruction
        lang_instruction = LANGUAGE_INSTRUCTIONS.get(language)
        if lang_instruction:
            full_system += f"\n\n{lang_instruction}"

        # Add conversation style for avatar (use language-specific or fall back to German)
        avatar_style = AVATAR_STYLE_INSTRUCTIONS.get(
            language, AVATAR_STYLE_INSTRUCTIONS["de"]
        )
        full_system += avatar_style

        messages.append(LLMMessage(role="system", content=full_system))

        # 2. RAG context (if available)
        if rag_context:
            # RAG instructions in target language
            if language == "de":
                rag_instruction = (
                    "Nutze den folgenden Kontext aus der Wissensdatenbank, "
                    "um die Frage des Nutzers zu beantworten. "
                    "Wenn der Kontext die Frage nicht beantwortet, "
                    "sage ehrlich, dass du dazu keine Informationen hast.\n\n"
                )
            else:
                rag_instruction = (
                    "Use the following context from the knowledge base "
                    "to answer the user's question. "
                    "If the context doesn't answer the question, "
                    "honestly say you don't have information about it.\n\n"
                )
            messages.append(LLMMessage(
                role="system",
                content=f"{rag_instruction}KONTEXT:\n{rag_context}",
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
