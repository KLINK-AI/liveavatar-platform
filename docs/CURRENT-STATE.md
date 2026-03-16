# LiveAvatar Platform — Aktueller Stand

**Datum**: 16. März 2026
**Version**: 0.4.0 — Commit `458afa3` (main)
**Status**: Produktiv deployed, Avatar funktioniert

## Deployment

| Komponente | URL / Adresse |
|---|---|
| **Frontend** | https://liveavatar.klink-io.cloud |
| **Backend API** | https://liveavatar.klink-io.cloud/api (via Nginx Proxy) |
| **Admin Dashboard** | https://liveavatar.klink-io.cloud/admin |
| **Demo Avatar** | https://liveavatar.klink-io.cloud/avatar/demo |
| **Coolify** | https://coolify.klink-io.cloud |
| **Server IP** | 72.62.91.69 |
| **GitHub** | https://github.com/KLINK-AI/liveavatar-platform |
| **Supabase** | https://supabase.com/dashboard/project/fxqqsqzgsjdmmvyzlxym |

## Implementierte Features

### Avatar & Kommunikation
- **LiveAvatar LITE Mode** — Eigenes ASR/LLM/TTS, LiveAvatar rendert nur Avatar + Lip-Sync
- **Multi-Language Support** — DE, EN, FR, ES, IT, NL (konfigurierbar pro Tenant)
- **Sprachauswahl-Dialog** — Erscheint beim Sessionstart, zeigt unterstützte Sprachen
- **Mehrsprachige Begrüßung** — Tenant kann pro Sprache eine eigene Begrüßung definieren
- **Avatar-Vorschaubild** — Zeigt Standbild des Avatars vor Sessionstart
- **Text-Chat** — Eingabefeld für Fragen, Antworten erscheinen im Chat
- **Frontend Timeout-Schutz** — AbortController verhindert endlose Wartezeiten (90s/30s)

### Performance
- **Session-Aufbau ~5s** — Von ~9s optimiert (siehe PERFORMANCE-OPTIMIZATION.md)
- **Greeting Audio Cache** — In-Memory, erste Session generiert TTS, danach instant
- **Parallel TTS + REST API** — TTS läuft während start_session() Call
- **Non-blocking WS Connect** — Kein Warten auf "connected" Event (~565ms statt ~5600ms)
- **ElevenLabs Turbo Model** — `eleven_turbo_v2_5` für Greetings (~500ms statt ~1800ms)

### UI/Layout
- **Responsive Layout** — Avatar links, Chat rechts, gleiche Höhe via ResizeObserver
- **Feste Chat-Höhe** — Chat-Container bleibt stabil, kein Springen bei Nachrichten
- **Session beenden Button** — Oben rechts, beendet Avatar-Session sauber
- **Mikrofon-Hinweis** — "oder per Mikrofon sprechen" (UI vorhanden, STT noch nicht aktiv)

### Backend
- **Multi-Tenant** — Mehrere Kunden mit eigenen Avataren, Prompts, Wissensbasis
- **Admin Dashboard** — Login (admin/Klink2026!Avatar), Tenant-Verwaltung
- **RAG Pipeline** — Qdrant Vector Search für Knowledge Base
- **Wissensbasis-Upload** — URL-Crawling, Datei-Upload (PDF, DOCX, TXT)
- **Conversation Memory** — Gesprächsverlauf pro Session
- **Keep-Alive** — WebSocket Heartbeat (30s) als primärer Mechanismus
- **Retry-Logik** — `tenacity` Retries für LiveAvatar API (max 2 Versuche, exponential backoff)

## Tech Stack

| Schicht | Technologie |
|---|---|
| Frontend | React 18, Vite, TypeScript, LiveKit Client SDK |
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), Pydantic |
| Datenbank | PostgreSQL (Supabase), Qdrant (Vektoren), Redis (Cache) |
| TTS | ElevenLabs (eleven_multilingual_v2 + eleven_turbo_v2_5) |
| LLM | OpenAI GPT-4o |
| STT | Deepgram (via LiveKit Agent) — aktuell deaktiviert, siehe Known Issues |
| Avatar | LiveAvatar (HeyGen) LITE Mode |
| Video | LiveKit Cloud (WebRTC) |
| HTTP Client | httpx 0.27.2 mit HTTP/2 Support (h2 Package) |
| Retry | tenacity 9.0.0 |
| Deployment | Coolify (Docker Compose), GitHub Auto-Deploy |

## HTTP-Protokoll-Anforderungen (WICHTIG)

Die LiveAvatar API hinter Cloudflare hat unterschiedliche HTTP-Protokoll-Anforderungen:

| Endpoint | Protokoll | Auth | Anmerkung |
|---|---|---|---|
| `POST /v1/sessions/token` | **HTTP/1.1** | X-API-KEY Header | HTTP/2 hängt hier |
| `POST /v1/sessions/start` | **HTTP/2** | Bearer Token | HTTP/1.1 hängt hier |
| `POST /v1/sessions/stop` | **HTTP/2** | Bearer Token | |
| `POST /v1/sessions/keep_alive` | **HTTP/2** | Bearer Token | Gibt aktuell 405 zurück |
| `GET /v1/avatars/*` | HTTP/1.1 | X-API-KEY Header | |

**Diagnose-Geschichte**: Anfangs hingen ALLE Endpoints mit HTTP/2, daher wurde HTTP/1.1 erzwungen.
Später stellte sich heraus, dass nur `/token` HTTP/1.1 braucht, während `/start` HTTP/2 ERFORDERT.
Die Lösung: Gemischter Ansatz — HTTP/1.1 für Token, HTTP/2 für Session-Lifecycle.

## Demo Tenant Konfiguration

| Einstellung | Wert |
|---|---|
| Slug | `demo` |
| Avatar ID | `9b116530-ab51-48ec-9fc6-e5c01d4d3568` |
| Default Language | `de` |
| Supported Languages | de, en, fr, es, it, nl |
| LLM Model | gpt-4o |
| TTS Voice | `i864UlSuWq9bx6fRZpva` (ElevenLabs) |
| TTS Model (Standard) | eleven_multilingual_v2 |
| TTS Model (Greetings) | eleven_turbo_v2_5 |

## Performance-Metriken (Production, 16. März 2026)

### Session-Aufbau (nach HTTP/2 Fix)
| Schritt | Dauer | Hinweis |
|---|---|---|
| create_session_token (HTTP/1.1) | ~233ms | LiveAvatar API |
| start_session (HTTP/2) | ~3694ms | LiveAvatar API |
| **API Response an Frontend** | **~3927ms** | User sieht "Loading" |
| WS TCP Connect | ~565ms | Non-blocking |
| TTS Pre-Generation | ~577ms | Parallel mit start_session, fertig vorher |
| Setup Phase | ~566ms | |
| Audio Send (cached) | ~223ms | 9 Chunks, ~214KB |
| **Total bis Avatar spricht** | **~5s** | |

### Session-Aufbau (zweite Session, gleicher Avatar+Sprache)
| Schritt | Dauer | Hinweis |
|---|---|---|
| API Response | ~3927ms | Gleich (LiveAvatar muss Session hochfahren) |
| WS Connect | ~565ms | |
| TTS | 0ms | **Cache Hit** |
| Audio Send | ~223ms | |
| **Background bis Begrüßung** | **~788ms** | |

## Bekannte Einschränkungen & Issues

### Aktiv / Offen
1. **LiveKit Agent (STT)**: `cannot import name 'rtc' from 'livekit'` — Spracheingabe per Mikrofon funktioniert nicht. Text-Eingabe funktioniert. Fix: `livekit-agents` oder `livekit-rtc` korrekt installieren (hat native Dependencies).
2. **keep_alive REST 405**: Der Endpoint `/v1/sessions/keep_alive` gibt HTTP 405 zurück. Nicht kritisch — WS-Heartbeat hält Session am Leben. Möglicherweise hat LiveAvatar die API geändert.
3. **`/debug/network` Endpoint**: Noch aktiv im Production-Build. Sollte entfernt oder hinter Admin-Auth gesichert werden.
4. **Audio Cache In-Memory**: Geht bei Backend-Restart verloren. Erste Session nach Deploy ist ~500ms langsamer.

### Architektur-Schulden
5. **Diagnostic Logging in `start_session`**: Vollständige Raw-Response-Logs (bis 2000 Zeichen) — Gut für Debugging, sollte für Production auf DEBUG-Level oder entfernt werden.
6. **Shared Client vs. Per-Request Client**: `create_session_token` nutzt Singleton-Client (HTTP/1.1), `start_session`/`stop_session`/`keep_alive` erstellen jeweils eigenen Client (HTTP/2). Könnte optimiert werden (z.B. zwei Singleton-Clients).

## Dateistruktur (Key Files)

```
liveavatar-platform/
├── CHANGELOG.md                    ← Versions-Historie (NEU)
├── backend/
│   ├── api/routes/
│   │   ├── sessions.py             ← Session-Lifecycle + Timing
│   │   ├── messages.py             ← Chat-Nachrichten
│   │   ├── knowledge.py            ← Wissensbasis CRUD
│   │   └── tenants.py              ← Tenant CRUD
│   ├── services/
│   │   ├── conversation/
│   │   │   └── engine.py           ← Orchestrator (RAG→LLM→TTS→Avatar)
│   │   ├── liveavatar_client.py    ← REST-Client (HTTP/1.1 + HTTP/2 gemischt)
│   │   ├── liveavatar_ws.py        ← WebSocket-Manager (Audio → Avatar)
│   │   ├── livekit_manager.py      ← LiveKit Token-Generierung
│   │   ├── tts/
│   │   │   ├── __init__.py         ← Provider Factory
│   │   │   └── elevenlabs_provider.py ← ElevenLabs (PCM 16Bit 24KHz)
│   │   ├── llm/
│   │   │   └── provider_factory.py ← OpenAI / Claude / Ollama
│   │   └── rag/pipeline.py         ← Qdrant RAG
│   ├── config.py                   ← Settings (Turbo Model, API Keys)
│   ├── main.py                     ← FastAPI App + /debug/network
│   ├── models/                     ← SQLAlchemy Models
│   └── requirements.txt            ← Dependencies (httpx[http2])
├── frontend/
│   ├── src/
│   │   ├── pages/AvatarPage.tsx    ← Avatar UI + LiveKit + State Machine
│   │   ├── components/
│   │   │   └── AvatarPlayer.tsx    ← LiveKit WebRTC Video
│   │   ├── hooks/
│   │   │   └── useAvatarSession.ts ← Session State Management
│   │   ├── lib/api.ts              ← API Client (AbortController Timeouts)
│   │   └── styles/index.css        ← Layout CSS
│   └── package.json
├── docs/
│   ├── ARCHITECTURE.md             ← Technische Architektur
│   ├── PERFORMANCE-OPTIMIZATION.md ← Latenz-Optimierung (4 Runden)
│   ├── CURRENT-STATE.md            ← Dieses Dokument
│   ├── DEPLOYMENT-COOLIFY.md       ← Deployment-Anleitung
│   └── setup.md                    ← Quick Start
└── docker-compose.yml              ← 4 Services (Backend, Frontend, Qdrant, Redis)
```

## API Endpoints (Backend)

### Public (mit X-API-Key)
| Method | Endpoint | Beschreibung |
|---|---|---|
| GET | `/api/v1/tenants/by-slug/{slug}` | Tenant-Infos für Frontend |
| POST | `/api/v1/sessions/` | Session erstellen (Token → Start → LiveKit) |
| POST | `/api/v1/sessions/{id}/stop` | Session beenden |
| POST | `/api/v1/sessions/{id}/keep-alive` | Keep-Alive |
| POST | `/api/v1/sessions/{id}/greeting` | Begrüßung senden |
| POST | `/api/v1/conversations/{id}/message` | Nachricht senden |
| GET | `/api/v1/conversations/{id}/history` | Gesprächsverlauf |
| WS | `/api/v1/conversations/{id}/stream` | Streaming-Antworten |

### Admin (mit JWT Token)
| Method | Endpoint | Beschreibung |
|---|---|---|
| POST | `/api/v1/admin/auth/token` | Admin Login |
| GET | `/api/v1/admin/stats` | Globale Statistiken |
| GET/POST | `/api/v1/tenants/` | Tenant CRUD |
| GET/POST/DELETE | `/api/v1/knowledge/` | Knowledge Base CRUD |

### Debug (NICHT FÜR PRODUCTION)
| Method | Endpoint | Beschreibung |
|---|---|---|
| GET | `/debug/network` | Netzwerk-Diagnose aus Docker-Container |

## Umgebungsvariablen (docker-compose.yml)

Alle Variablen werden über Coolify Environment Variables gesetzt:

| Variable | Beschreibung | Beispiel |
|---|---|---|
| `DATABASE_URL` | Supabase PostgreSQL | `postgresql+asyncpg://...` |
| `LIVEAVATAR_API_KEY` | LiveAvatar API Key | `43031916-bb2d-...` |
| `LIVEAVATAR_API_BASE` | LiveAvatar API URL | `https://api.liveavatar.com` |
| `LIVEKIT_URL` | LiveKit Cloud URL | `wss://...livekit.cloud` |
| `LIVEKIT_API_KEY` | LiveKit API Key | |
| `LIVEKIT_API_SECRET` | LiveKit API Secret | |
| `OPENAI_API_KEY` | OpenAI (GPT-4o + Embeddings) | |
| `ELEVENLABS_API_KEY` | ElevenLabs TTS | |
| `ELEVENLABS_DEFAULT_VOICE_ID` | Standard-Stimme | |
| `DEEPGRAM_API_KEY` | Deepgram STT | |
| `APP_SECRET_KEY` | App Secret | |
| `JWT_SECRET_KEY` | JWT Token Signing | |

## Commit-Historie (relevante Commits)

| Version | Commit | Datum | Beschreibung |
|---|---|---|---|
| **0.4.0** | `458afa3` | 2026-03-16 | HTTP/2 Fix für start_session |
| | `c049590` | 2026-03-16 | Reduzierte Timeouts + Diagnostic Logging |
| | `29632e1` | 2026-03-16 | Retry-Logik für start_session |
| | `f41e124` | 2026-03-16 | Force HTTP/1.1 (erste Diagnose) |
| | `45a3f7c` | 2026-03-16 | /debug/network Endpoint |
| **0.3.0** | `585bafa` | 2026-03-11 | Keep-alive Fix + Fehlerbehandlung |
| | `a10dbf8` | 2026-03-11 | WS Connect Blocking entfernt (-5s) |
| | `da143d4` | 2026-03-11 | Parallel TTS, Turbo Model, Timing |
| | `5317cfd` | 2026-03-11 | Greeting Cache, Async TTS |
| **0.2.0** | `eaa27dd` | 2026-03-10 | Multi-Language, Sprachauswahl, Vorschaubild |
| | `9819c20` | 2026-03-10 | Admin Login |
| **0.1.0** | `7a85d4f` | 2026-03-09 | LiveAvatar LITE Migration |
