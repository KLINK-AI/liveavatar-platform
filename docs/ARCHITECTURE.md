# LiveAvatar Platform — Technische Architektur

## Systemübersicht

Die LiveAvatar Platform ist ein Multi-Tenant System für KI-gestützte Video-Avatar-Kommunikation. Jeder Tenant (Kunde) erhält einen eigenen Avatar mit individueller Wissensbasis, Begrüßung und Spracheinstellungen.

## Architektur-Diagramm

```
User Browser
  ├── Frontend (React + Vite + Nginx)
  │     ├── AvatarPage.tsx    → Avatar-UI, LiveKit Video, Chat
  │     ├── AdminDashboard    → Tenant-Verwaltung, KB-Upload
  │     └── LiveKit Client    → WebRTC Video-Stream empfangen
  │
  └── API Calls (REST + WebSocket)
        ↓
Backend (FastAPI, Python 3.12)
  ├── api/routes/sessions.py   → Session-Lifecycle (Create → Start → Stop)
  ├── api/routes/messages.py   → Chat-Nachrichten verarbeiten
  ├── api/routes/tenants.py    → Tenant CRUD + Admin
  ├── api/routes/knowledge.py  → Wissensbasis-Verwaltung
  │
  ├── services/
  │     ├── conversation/engine.py     → Orchestrator: RAG → LLM → TTS → Avatar
  │     ├── liveavatar_client.py       → REST-Client für LiveAvatar API
  │     ├── liveavatar_ws.py           → WebSocket-Manager für Audio-Streaming
  │     ├── livekit_manager.py         → LiveKit Token-Generierung
  │     ├── tts/elevenlabs_provider.py → ElevenLabs TTS (PCM 16Bit 24KHz)
  │     ├── llm/provider_factory.py    → OpenAI / Claude / Ollama
  │     └── rag/pipeline.py            → Qdrant Vector Search
  │
  └── Externe Services
        ├── LiveAvatar API (api.liveavatar.com)  → Avatar-Session + WebRTC
        ├── LiveKit Cloud (livekit.cloud)         → WebRTC Video-Streaming
        ├── ElevenLabs API                        → Text-to-Speech
        ├── OpenAI API                            → LLM (GPT-4o)
        ├── Supabase (PostgreSQL)                 → Datenbank
        ├── Qdrant                                → Vektor-Datenbank (RAG)
        └── Redis                                 → Cache
```

## LITE Mode Audio Pipeline

Die Plattform nutzt LiveAvatar im **LITE Mode**: Wir kontrollieren ASR/STT, LLM und TTS selbst; LiveAvatar rendert nur den Avatar mit Lip-Sync aus unseren Audio-Daten.

```
Benutzer-Frage
  → RAG Context Retrieval (Qdrant)
  → LLM Prompt + Response (OpenAI GPT-4o)
  → ElevenLabs TTS → PCM 16Bit 24KHz Audio-Chunks
  → Base64 Encoding → WebSocket `agent.speak` Events
  → LiveAvatar rendert Lip-Sync Video
  → LiveKit WebRTC Stream → Browser zeigt Avatar
```

## Session-Lifecycle

### Schritt 1: Session erstellen (synchron, ~3.2s)

```
Frontend POST /api/v1/sessions/
  → Backend: create_session_token() via LiveAvatar REST API (~400ms)
  → [PARALLEL] TTS Greeting Pre-Generation startet als asyncio.Task (~500ms)
  → Backend: start_session() via LiveAvatar REST API (~2800ms)
  → Response mit LiveKit URL + Token an Frontend
```

### Schritt 2: Background Setup (async, ~500ms)

```
Background Task:
  → WebSocket TCP/TLS Connect (~380ms, non-blocking)
  → TTS ist bereits gecacht (lief parallel mit start_session)
  → Cached Audio an Avatar senden (~115ms)
  → Avatar spricht Begrüßung
  → LiveKit STT Agent starten (optional)
```

### Schritt 3: Gespräch

```
Benutzer tippt Frage → POST /api/v1/messages/
  → ConversationEngine.process_message()
  → RAG → LLM → TTS → WebSocket → Avatar spricht Antwort
```

### Schritt 4: Session beenden

```
Frontend POST /api/v1/sessions/{id}/stop
  → LiveAvatar Session stoppen
  → WebSocket disconnecten
  → LiveKit Agent stoppen
  → Conversation Memory löschen
```

## Multi-Tenant Architektur

Jeder Tenant hat:
- Eigenen Avatar (liveavatar_avatar_id)
- Eigene Voice (elevenlabs_voice_id)
- Eigenen System-Prompt für den LLM
- Eigene Wissensbasis(en) in Qdrant
- Unterstützte Sprachen + Begrüßungsübersetzungen
- Eigenen API-Key für Frontend-Zugang

## Datenbank-Schema (Supabase PostgreSQL)

- **tenants** — Mandanten-Konfiguration
- **avatar_sessions** — Session-Tracking (Status, Dauer, Tokens)
- **conversations** — Gesprächs-Zuordnung zu Sessions
- **knowledge_bases** — RAG Wissensbasis-Metadaten
- **documents** — Indexierte Dokumente/URLs

## Caching-Strategie

- **Greeting Audio Cache**: In-Memory Dict (`tenant_slug:language:text_hash` → PCM Chunks). Erste Session generiert TTS, alle folgenden Sessions nutzen Cache (~0ms statt ~500ms).
- **TTS Provider Cache**: Singleton pro Provider+API-Key+Model Kombination
- **Redis**: Session-Metadaten und Rate Limiting (geplant)

## Key Design Decisions

1. **Non-blocking WS Connect**: WebSocket wartet NICHT auf `session.state_updated=connected` Event. TCP/TLS Handshake reicht — Audio wird sofort nach Connect gesendet.

2. **Parallel TTS Pre-Generation**: TTS Greeting-Audio wird WÄHREND des `start_session()` REST-Calls generiert (als asyncio.Task), nicht danach. So ist Audio gecacht bevor der Background Task überhaupt startet.

3. **Turbo Model für Greetings**: `eleven_turbo_v2_5` statt `eleven_multilingual_v2` für schnellere Greeting-Generierung (~500ms statt ~1800ms).

4. **ResizeObserver für Chat-Höhe**: Chat-Container synchronisiert seine Höhe pixelgenau mit dem Avatar-Wrapper via ResizeObserver, damit beides gleich hoch ist.
