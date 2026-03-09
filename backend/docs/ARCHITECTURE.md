# LiveAvatar Platform — Architektur (LITE Mode)

## Überblick

Die LiveAvatar Platform ist eine White-Label-Plattform für interaktive Video-Avatare.
Im **LITE Mode** kontrollieren wir die gesamte Konversations-Pipeline selbst:

- **ASR/STT** → Deepgram (real-time) / OpenAI Whisper (fallback)
- **LLM** → OpenAI / Anthropic / Ollama (per-Tenant konfigurierbar)
- **RAG** → Qdrant Vektordatenbank mit LangChain
- **TTS** → ElevenLabs (PCM 16Bit 24KHz)
- **Avatar** → LiveAvatar rendert Lip-Sync-Video aus unserem Audio

LiveAvatar übernimmt **nur** das Avatar-Video-Rendering mit Lip-Sync.

## Konversations-Flow

```
User spricht ins Mikrofon
  ↓
Audio via WebRTC → LiveKit Room
  ↓
LiveKit Agent captured Audio-Stream (services/livekit_agent.py)
  ↓
STT (Deepgram/Whisper) transkribiert → Text (services/stt/)
  ↓
ConversationEngine (services/conversation/engine.py):
  1. RAG: Sucht relevante Chunks in Qdrant (services/rag/)
  2. Context Builder: System-Prompt + RAG-Kontext + History
  3. LLM: Generiert Text-Antwort (services/llm/)
  4. TTS: Text → PCM 16Bit 24KHz Audio (services/tts/elevenlabs_provider.py)
  5. WebSocket: agent.speak(audio_base64) → LiveAvatar (services/liveavatar_ws.py)
  ↓
LiveAvatar rendert Avatar-Video mit Lip-Sync zum Audio
  ↓
Video-Stream via LiveKit WebRTC → User sieht Avatar sprechen
```

## Service-Architektur

```
┌──────────────────────────────────────────────────┐
│                   FastAPI App                      │
│                                                    │
│  api/routes/sessions.py      — Session CRUD        │
│  api/routes/conversations.py — Chat Endpoints      │
│  api/routes/tenants.py       — Tenant Management   │
│  api/routes/knowledge.py     — Wissensbasis        │
│  api/routes/admin.py         — Admin-Funktionen    │
│                                                    │
├──────────────────────────────────────────────────┤
│                   Services                         │
│                                                    │
│  services/conversation/                            │
│    ├── engine.py         — Orchestrator            │
│    ├── context_builder.py — Prompt-Aufbau          │
│    └── memory.py          — Chat-History           │
│                                                    │
│  services/liveavatar_client.py — REST API Client   │
│  services/liveavatar_ws.py     — WebSocket Manager │
│  services/livekit_manager.py   — Token-Management  │
│  services/livekit_agent.py     — Audio Capture     │
│                                                    │
│  services/tts/                                     │
│    ├── __init__.py         — Base + Factory        │
│    └── elevenlabs_provider.py — ElevenLabs TTS     │
│                                                    │
│  services/stt/                                     │
│    ├── __init__.py              — Base + Factory   │
│    ├── deepgram_provider.py     — Echtzeit-STT     │
│    └── openai_whisper_provider.py — Batch-Fallback │
│                                                    │
│  services/llm/                                     │
│    ├── base.py             — LLM Interface         │
│    ├── openai_provider.py  — OpenAI GPT            │
│    ├── anthropic_provider.py — Claude              │
│    ├── ollama_provider.py  — Lokales LLM           │
│    └── provider_factory.py — Factory               │
│                                                    │
│  services/rag/                                     │
│    ├── pipeline.py         — RAG-Orchestrierung    │
│    ├── vector_store.py     — Qdrant Client         │
│    ├── document_ingester.py — Dokument-Import      │
│    └── web_crawler.py      — Web-Crawler           │
│                                                    │
├──────────────────────────────────────────────────┤
│                   Data Layer                       │
│                                                    │
│  models/tenant.py       — Tenant (Multi-Mandant)   │
│  models/session.py      — Avatar Sessions          │
│  models/conversation.py — Messages                 │
│  models/knowledge.py    — Knowledge Bases          │
│  database.py            — SQLAlchemy + PostgreSQL   │
│                                                    │
└──────────────────────────────────────────────────┘
```

## LiveAvatar LITE Mode API

### REST Endpoints (api.liveavatar.com)

| Endpoint | Methode | Beschreibung |
|---|---|---|
| `/v1/sessions/token` | POST | Session-Token erstellen (mode: LITE) |
| `/v1/sessions/start` | POST | Avatar-Streaming starten |
| `/v1/sessions/stop` | POST | Session beenden |
| `/v1/sessions/keep_alive` | POST | Idle-Timer zurücksetzen |
| `/v1/avatars/public` | GET | Öffentliche Avatare auflisten |
| `/v1/avatars` | GET | Eigene Avatare auflisten |

### WebSocket Command Events (wir senden)

| Event | Payload | Beschreibung |
|---|---|---|
| `agent.speak` | `{audio: "base64..."}` | PCM Audio an Avatar senden |
| `agent.speak_end` | `{}` | Signal: fertig gesprochen |
| `agent.interrupt` | `{}` | Avatar-Sprache unterbrechen |
| `agent.start_listening` | `{}` | Avatar → Listening-Animation |
| `agent.stop_listening` | `{}` | Avatar → Idle-Animation |
| `session.keep_alive` | `{}` | Session am Leben halten |

### WebSocket Server Events (wir empfangen)

| Event | Beschreibung |
|---|---|
| `session.state_updated` | Zustand: connected/connecting/closed |
| `agent.speak_started` | Avatar hat angefangen zu sprechen |
| `agent.speak_ended` | Avatar hat aufgehört zu sprechen |

## Environment-Variablen

Siehe `docs/ENV_VARS.md` für die vollständige Liste.

## Session-Lifecycle

```
1. POST /api/v1/sessions/
   → LiveAvatar API: POST /v1/sessions/token (mode: LITE)
   → WebSocket-Verbindung aufbauen (Background)
   → LiveKit STT Agent starten (Background)

2. POST /api/v1/sessions/{id}/start
   → LiveAvatar API: POST /v1/sessions/start
   → Avatar erscheint im LiveKit Room

3. POST /api/v1/conversations/{id}/message
   → RAG → LLM → ElevenLabs TTS → WebSocket agent.speak
   → Avatar spricht mit Lip-Sync

4. POST /api/v1/sessions/{id}/stop
   → LiveAvatar API: POST /v1/sessions/stop
   → WebSocket trennen, LiveKit Agent stoppen
```
