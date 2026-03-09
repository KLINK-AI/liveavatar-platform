# Migration: HeyGen Streaming API → LiveAvatar LITE Mode

## Datum: 2026-03-09

## Warum?

Die alte HeyGen Streaming API (`/v1/streaming.*`) wird abgeschaltet.
Der gesamte Code musste auf die neue LiveAvatar LITE Mode API migriert werden.

## Was hat sich geändert?

### Grundlegende Architekturänderung

**ALT (HeyGen Streaming):**
```
LLM Text → HeyGen streaming.task(text) → HeyGen macht TTS + Lip-Sync
```

**NEU (LiveAvatar LITE Mode):**
```
LLM Text → ElevenLabs TTS → PCM Audio → WebSocket agent.speak → LiveAvatar Lip-Sync
```

Im alten System hat HeyGen sowohl TTS als auch Lip-Sync gemacht.
Im neuen LITE Mode müssen wir das Audio selbst generieren und per WebSocket an LiveAvatar senden.

### Neue Services

| Service | Datei | Aufgabe |
|---|---|---|
| ElevenLabs TTS | `services/tts/elevenlabs_provider.py` | Text → PCM 16Bit 24KHz Audio |
| Deepgram STT | `services/stt/deepgram_provider.py` | Echtzeit Speech-to-Text |
| OpenAI Whisper STT | `services/stt/openai_whisper_provider.py` | Batch STT Fallback |
| WebSocket Manager | `services/liveavatar_ws.py` | LITE Mode Command Events |
| LiveKit Agent | `services/livekit_agent.py` | User-Audio capturen → STT |

### Geänderte Services

| Service | Was | Vorher | Nachher |
|---|---|---|---|
| LiveAvatar Client | REST API | `/v1/streaming.*` (HeyGen) | `/v1/sessions/*` (LiveAvatar) |
| ConversationEngine | Avatar-Ausgabe | `send_text_streaming()` | TTS → WebSocket `agent.speak` |
| LiveKit Manager | Config | `get_livekit_settings_for_heygen()` | `get_livekit_config_for_liveavatar()` |

### Geänderte Models

| Model | Feld | Vorher | Nachher |
|---|---|---|---|
| Tenant | Avatar-ID | `heygen_avatar_id` | `liveavatar_avatar_id` |
| Tenant | Voice-ID | `heygen_voice_id` | `liveavatar_voice_id` |
| Tenant | — (neu) | — | `elevenlabs_api_key`, `elevenlabs_voice_id`, `stt_provider` |
| AvatarSession | Session-ID | `heygen_session_id` | `liveavatar_session_id` |
| AvatarSession | — (neu) | — | `liveavatar_session_token`, `ws_url`, `ws_status` |

### Neue Dependencies

```
elevenlabs>=1.0.0
deepgram-sdk>=3.5.0
livekit-agents>=0.12.0
numpy>=1.26.0
```

## Migrations-Schritte

### 1. Datenbank migrieren

```bash
psql -d liveavatar -f migrations/001_heygen_to_liveavatar.sql
```

### 2. Environment-Variablen setzen

```env
# Neu (Pflicht):
LIVEAVATAR_API_KEY=your-liveavatar-api-key
ELEVENLABS_API_KEY=your-elevenlabs-api-key
ELEVENLABS_DEFAULT_VOICE_ID=your-voice-id
DEEPGRAM_API_KEY=your-deepgram-api-key

# Geändert:
LIVEAVATAR_API_BASE=https://api.liveavatar.com  (war: https://api.heygen.com)
```

### 3. Neuen Code deployen

```bash
git push origin main  # Coolify rebuild
```

### 4. Tenants aktualisieren

Bestehende Tenants müssen ihre Avatar-IDs über die neue API setzen:

```bash
curl -X PUT https://api.liveavatar.klink-io.cloud/api/v1/tenants/{id} \
  -H "Content-Type: application/json" \
  -d '{
    "liveavatar_avatar_id": "neue-avatar-id",
    "elevenlabs_voice_id": "voice-id"
  }'
```

## Nicht betroffen

Diese Teile der Plattform bleiben unverändert:

- LLM Provider (OpenAI, Anthropic, Ollama)
- RAG Pipeline (Qdrant, LangChain)
- Conversation Memory + Context Builder
- Knowledge Base Management
- Admin Routes
- Auth Middleware
- Database Layer
