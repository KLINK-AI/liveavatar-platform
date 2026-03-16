# LiveAvatar Platform — Technische Architektur

**Aktualisiert**: 16. März 2026 (v0.4.0)

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

### Schritt 1: Session erstellen (synchron, ~4s)

```
Frontend POST /api/v1/sessions/
  → Backend: create_session_token() via HTTP/1.1 (~233ms)
  → [PARALLEL] TTS Greeting Pre-Generation startet als asyncio.Task (~577ms)
  → Backend: start_session() via HTTP/2 (~3694ms)       ← MUSS HTTP/2 sein!
  → Response mit LiveKit URL + Token an Frontend
```

> **HTTP-Protokoll-Hinweis**: `create_session_token` nutzt HTTP/1.1 (hängt mit HTTP/2),
> `start_session` nutzt HTTP/2 (hängt mit HTTP/1.1). Siehe CURRENT-STATE.md für Details.

### Schritt 2: Background Setup (async, ~800ms)

```
Background Task:
  → WebSocket TCP/TLS Connect (~565ms, non-blocking)
  → TTS ist bereits gecacht (lief parallel mit start_session)
  → Cached Audio an Avatar senden (~223ms, 9 Chunks, ~214KB)
  → Avatar spricht Begrüßung
  → LiveKit STT Agent starten (optional, aktuell deaktiviert)
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

1. **Gemischtes HTTP-Protokoll**: `create_session_token` (X-API-KEY Auth) nutzt HTTP/1.1 via Singleton-Client. `start_session`/`stop_session`/`keep_alive` (Bearer Token Auth) nutzen HTTP/2 via eigene temporäre Clients. Grund: Cloudflare behandelt die Endpoints unterschiedlich.

2. **Non-blocking WS Connect**: WebSocket wartet NICHT auf `session.state_updated=connected` Event. TCP/TLS Handshake reicht — Audio wird sofort nach Connect gesendet.

3. **Parallel TTS Pre-Generation**: TTS Greeting-Audio wird WÄHREND des `start_session()` REST-Calls generiert (als asyncio.Task), nicht danach. So ist Audio gecacht bevor der Background Task überhaupt startet.

4. **Turbo Model für Greetings**: `eleven_turbo_v2_5` statt `eleven_multilingual_v2` für schnellere Greeting-Generierung (~500ms statt ~1800ms).

5. **ResizeObserver für Chat-Höhe**: Chat-Container synchronisiert seine Höhe pixelgenau mit dem Avatar-Wrapper via ResizeObserver, damit beides gleich hoch ist.

6. **Frontend AbortController**: Alle API-Calls haben Timeouts (Session-Create: 90s, Rest: 30s) um endlose Wartezeiten zu verhindern. Bei Timeout erscheint eine deutsche Fehlermeldung.

7. **Retry mit Exponential Backoff**: `tenacity` Decorator für API-Calls (max 2 Versuche, 2-8s Wartezeit). Fängt intermittierende 500er Fehler ab.
