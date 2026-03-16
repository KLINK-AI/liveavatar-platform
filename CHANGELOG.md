# Changelog — LiveAvatar Platform

Alle relevanten Änderungen an der LiveAvatar Platform werden hier dokumentiert.
Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/).

---

## [0.4.0] — 2026-03-16 — HTTP/2 Fix & Stabilisierung

**Status**: Produktiv deployed auf https://liveavatar.klink-io.cloud
**Commit**: `458afa3` (main)

### Behoben
- **KRITISCH: Avatar startete nicht mehr** — `start_session` hing endlos mit HTTP/1.1.
  Root Cause: Die LiveAvatar API (`/v1/sessions/start`) erfordert HTTP/2 hinter Cloudflare.
  HTTP/1.1-Requests hängen ohne Response. Fix: HTTP/2 für `start_session`, `stop_session` und `keep_alive`; HTTP/1.1 bleibt für `create_session_token` (funktioniert dort zuverlässig).
- **`httpx[http2]`** als Dependency hinzugefügt (installiert `h2` Package für HTTP/2 Support)
- **Frontend AbortController** — Verhindert endlose Wartezeiten bei API-Calls.
  Session-Create: 90s Timeout, alle anderen: 30s. Bei Timeout: deutsche Fehlermeldung.
- **Retry-Logik** für `start_session` mit `tenacity` (max 2 Versuche, exponential backoff)
- **Diagnostic Logging** — Vollständige Raw-Response-Logs für `start_session` zur Fehleranalyse

### Geändert
- `start_session`, `stop_session`, `keep_alive` verwenden jetzt jeweils einen eigenen `httpx.AsyncClient` mit `http2=True` (statt den shared HTTP/1.1 Client)
- API Timeouts reduziert: `start_session` 30s (statt 60s), `create_session_token` bleibt bei 60s
- Debug-Endpoint `/debug/network` hinzugefügt (nur für Entwicklung, vor Production entfernen!)

### Bekannte Probleme
- `keep_alive` REST-Endpoint gibt 405 zurück — nicht kritisch, WS-Heartbeat funktioniert
- LiveKit Agent (STT via Mikrofon): `cannot import name 'rtc' from 'livekit'` — Text-Input funktioniert
- `/debug/network` Endpoint sollte vor Production entfernt oder gesichert werden

### Performance nach Fix
| Schritt | Dauer |
|---|---|
| `create_session_token` | ~233ms |
| `start_session` (HTTP/2) | ~3.694ms |
| WS TCP Connect | ~565ms |
| Greeting Audio Send (cached) | ~223ms |
| **Total bis Avatar spricht** | **~5s** |

---

## [0.3.0] — 2026-03-11 — Performance-Optimierung

**Commit**: `585bafa` (main)

### Hinzugefügt
- **Greeting Audio In-Memory Cache** — Erste Session generiert TTS, danach instant (0ms)
- **Parallel TTS Pre-Generation** — TTS läuft während `start_session()` REST-Call
- **ElevenLabs Turbo Model** (`eleven_turbo_v2_5`) für Greetings (~500ms statt ~1800ms)
- **Timing-Instrumentierung** — `TIMING` Logzeilen für alle kritischen Pfade
- **Architecture, Performance, Current-State Dokumentation** in `docs/`

### Behoben
- **WS Connect Blocking entfernt** — Wartete 5s auf Server-Event, jetzt nur TCP/TLS (~380ms)
- Keep-alive Endpoint-Pfad korrigiert: `/v1/sessions/keep-alive` → `/v1/sessions/keep_alive`
- Chat-Container Höhe springt nicht mehr bei neuen Nachrichten (ResizeObserver)

### Performance-Verbesserung
| Metrik | Vorher | Nachher |
|---|---|---|
| Greeting-Latenz | ~9s | ~3.7s |
| WS Connect | ~5.6s | ~380ms |
| TTS (effektiv) | ~1.8s | 0ms (parallel) |

---

## [0.2.0] — 2026-03-10 — Multi-Language & Admin

**Commit**: `eaa27dd` (main)

### Hinzugefügt
- **Multi-Language Support** — DE, EN, FR, ES, IT, NL (konfigurierbar pro Tenant)
- **Sprachauswahl-Dialog** beim Sessionstart mit Flaggen-Icons
- **Mehrsprachige Begrüßungen** — Pro Tenant und Sprache konfigurierbar
- **Avatar-Vorschaubild** — Zeigt Standbild vor Sessionstart
- **Admin Login** mit Username/Password (JWT-basiert)
- **LLM-generierte Antwort** in Knowledge-Base Suchtests
- **Tenant-Bearbeitung** im Admin Dashboard

### Behoben
- ConversationEngine Singleton-Pattern (shared State Bug)
- WS State Wait + Keep-Alive URL korrigiert
- 8 kritische Bugs: Public Avatar Page, Doc Upload, API Key Display
- KB Auth Bug behoben

---

## [0.1.0] — 2026-03-09 — Initiale LiveAvatar LITE Migration

**Commit**: `7a85d4f` (main)

### Hinzugefügt
- **Migration von HeyGen Streaming → LiveAvatar LITE Mode**
- **2-Step Session Flow**: `create_session_token` → `start_session`
- **LITE Mode Pipeline**: Eigenes ASR/LLM/TTS, LiveAvatar rendert nur Avatar + Lip-Sync
- **Multi-Tenant Architektur** mit Supabase PostgreSQL
- **RAG Pipeline** mit Qdrant Vector Search
- **ElevenLabs TTS** (PCM 16Bit 24KHz → WebSocket → Avatar)
- **LiveKit WebRTC** für Video-Streaming
- **Docker Compose** Setup für Coolify (Backend, Frontend, Qdrant, Redis)

### Behoben
- Dependency-Konflikte (websockets, httpx, anthropic)
- livekit-rtc native Dependencies entfernt (Docker-kompatibel)
- Langchain Import-Kompatibilität für v1.x
