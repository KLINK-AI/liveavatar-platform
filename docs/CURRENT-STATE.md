# LiveAvatar Platform — Aktueller Stand

**Datum**: 11. März 2026
**Version**: Commit `585bafa` (main)
**Status**: Produktiv deployed

## Deployment

| Komponente | URL / Adresse |
|---|---|
| **Frontend** | https://liveavatar.klink-io.cloud |
| **Backend API** | https://api.liveavatar.klink-io.cloud |
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
- **Spracheingabe (STT)** — LiveKit-basierte Transkription (Deepgram)

### Performance
- **Greeting Latency ~3.7s** — Optimiert von ~9s (siehe PERFORMANCE-OPTIMIZATION.md)
- **Greeting Audio Cache** — In-Memory, erste Session generiert TTS, danach instant
- **Parallel TTS + REST API** — TTS läuft während start_session() Call
- **Non-blocking WS Connect** — Kein Warten auf "connected" Event (~380ms statt ~5600ms)
- **ElevenLabs Turbo Model** — `eleven_turbo_v2_5` für Greetings (~500ms statt ~1800ms)

### UI/Layout
- **Responsive Layout** — Avatar links, Chat rechts, gleiche Höhe via ResizeObserver
- **Feste Chat-Höhe** — Chat-Container bleibt stabil, kein Springen bei Nachrichten
- **Session beenden Button** — Oben rechts, beendet Avatar-Session sauber

### Backend
- **Multi-Tenant** — Mehrere Kunden mit eigenen Avataren, Prompts, Wissensbasis
- **Admin Dashboard** — Login (admin/Klink2026!Avatar), Tenant-Verwaltung
- **RAG Pipeline** — Qdrant Vector Search für Knowledge Base
- **Wissensbasis-Upload** — URL-Crawling, Datei-Upload (PDF, DOCX, TXT)
- **Conversation Memory** — Gesprächsverlauf pro Session
- **Keep-Alive** — WebSocket Heartbeat (30s) + REST Keep-Alive

## Tech Stack

| Schicht | Technologie |
|---|---|
| Frontend | React 18, Vite, TypeScript, LiveKit Client SDK |
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), Pydantic |
| Datenbank | PostgreSQL (Supabase), Qdrant (Vektoren), Redis (Cache) |
| TTS | ElevenLabs (eleven_multilingual_v2 + eleven_turbo_v2_5) |
| LLM | OpenAI GPT-4o |
| STT | Deepgram (via LiveKit Agent) |
| Avatar | LiveAvatar (HeyGen) LITE Mode |
| Video | LiveKit Cloud (WebRTC) |
| Deployment | Coolify (Docker Compose), GitHub Auto-Deploy |

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

## Performance-Metriken (Production)

### Session-Aufbau (erste Session)
| Schritt | Dauer | Hinweis |
|---|---|---|
| create_session_token | ~400ms | LiveAvatar API |
| start_session | ~2750ms | LiveAvatar API (nicht optimierbar) |
| **API Response an Frontend** | **~3150ms** | User sieht "Loading" |
| WS TCP Connect | ~380ms | Non-blocking |
| TTS Pre-Generation | ~500ms | Parallel mit start_session, fertig bevor Background |
| Audio Send (cached) | ~115ms | 9 Chunks, ~205KB |
| **Background bis Begrüßung** | **~500ms** | |
| **Total bis Avatar spricht** | **~3650ms** | |

### Session-Aufbau (zweite Session, gleicher Avatar+Sprache)
| Schritt | Dauer | Hinweis |
|---|---|---|
| API Response | ~3150ms | Gleich (LiveAvatar muss Session hochfahren) |
| WS Connect | ~380ms | |
| TTS | 0ms | **Cache Hit** |
| Audio Send | ~115ms | |
| **Background bis Begrüßung** | **~500ms** | |

## Bekannte Einschränkungen

1. **LiveAvatar API Latenz**: `start_session` dauert ~2.8s — das ist die LiveAvatar-Serverzeit und nicht optimierbar.
2. **Audio Cache ist In-Memory**: Geht bei Backend-Restart verloren. Erste Session nach Deploy ist ~500ms langsamer.
3. **Keep-Alive REST**: Kann 401 liefern wenn LiveAvatar Session abgelaufen ist. WS Heartbeat bietet Fallback.
4. **LiveKit Agent (STT)**: Importfehler im Docker-Container (`cannot import name 'rtc'`). Text-Eingabe funktioniert, Spracheingabe nicht im aktuellen Build.

## Dateistruktur (Key Files)

```
liveavatar-platform/
├── backend/
│   ├── api/routes/
│   │   ├── sessions.py          ← Session-Lifecycle + Timing
│   │   ├── messages.py          ← Chat-Nachrichten
│   │   └── tenants.py           ← Tenant CRUD
│   ├── services/
│   │   ├── conversation/
│   │   │   └── engine.py        ← Orchestrator (RAG→LLM→TTS→Avatar)
│   │   ├── liveavatar_client.py ← REST-Client
│   │   ├── liveavatar_ws.py     ← WebSocket-Manager
│   │   ├── tts/
│   │   │   ├── __init__.py      ← Provider Factory
│   │   │   └── elevenlabs_provider.py
│   │   └── rag/pipeline.py      ← Qdrant RAG
│   ├── config.py                ← Settings (inkl. Turbo Model)
│   └── models/                  ← SQLAlchemy Models
├── frontend/
│   ├── src/pages/AvatarPage.tsx ← Avatar UI + LiveKit
│   └── src/styles/index.css     ← Layout CSS
├── docs/
│   ├── ARCHITECTURE.md          ← Technische Architektur
│   ├── PERFORMANCE-OPTIMIZATION.md ← Latenz-Optimierung
│   ├── CURRENT-STATE.md         ← Dieses Dokument
│   ├── DEPLOYMENT-COOLIFY.md    ← Deployment-Anleitung
│   └── setup.md                 ← Quick Start
└── docker-compose.yml           ← 4 Services (Backend, Frontend, Qdrant, Redis)
```

## Commit-Historie (relevante Commits)

| Commit | Beschreibung |
|---|---|
| `585bafa` | Fix keep-alive Endpoint-Pfad + Fehlerbehandlung |
| `a10dbf8` | **WS Connect Blocking entfernt** — ~5s Einsparung |
| `da143d4` | Parallel TTS+WS, Turbo Model, Timing-Instrumentierung |
| `5317cfd` | Chat fixed-height, Greeting Audio Cache, Async TTS |
| `ac36f92` | Chat-Höhe, Greeting-Latenz, Audio bei Re-Session |
| `eaa27dd` | Avatar-Vorschaubild, Sprachauswahl, mehrsprachige Begrüßung |
| `9819c20` | Admin Login mit Username/Password |
