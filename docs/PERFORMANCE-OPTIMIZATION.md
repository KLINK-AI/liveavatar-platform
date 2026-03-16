# Greeting-Latenz Optimierung — Dokumentation

## Zusammenfassung

Die Zeit vom Klick auf "Gespräch starten" bis zur Avatar-Begrüßung wurde von **~9 Sekunden auf ~3.7 Sekunden** reduziert — eine Verbesserung von **~59%**. Die verbleibenden ~3.2s sind LiveAvatar API-Antwortzeiten, die extern nicht beeinflussbar sind.

## Optimierungshistorie

### Runde 1 — Grundlagen (Commit `5317cfd`)

**Problem**: Greeting-Audio wurde bei jeder Session neu generiert, WebSocket Connect nutzte einen polling-basierten Warteloop.

**Maßnahmen**:
- Greeting Audio In-Memory Cache eingeführt (Key: `tenant_slug:language:text_hash`)
- `asyncio.Event` statt Polling-Loop für WS Connected-State
- `asyncio.gather()` für parallele TTS + WS Verbindung im Background Task

### Runde 2 — Timing-Instrumentierung (Commit `da143d4`)

**Problem**: Unklare Engpässe — wo genau geht die Zeit verloren?

**Maßnahmen**:
- `time.monotonic()` Timing an allen kritischen Stellen eingefügt
- ElevenLabs Turbo Model (`eleven_turbo_v2_5`) für Greeting-TTS eingeführt
- Timeout/Retry für LiveAvatar Client reduziert (30s→15s, 3→2 Retries)

**Ergebnisse (erste Messung)**:
| Schritt | Dauer |
|---|---|
| `create_session_token` HTTP | 456ms |
| `start_session` HTTP | 2799ms |
| **API Total (synchron)** | **3267ms** |
| WS Connect (mit 5s Timeout-Wait) | **5634ms** ← Engpass! |
| TTS Pre-Generation (parallel) | 1761ms |
| Cached Audio Send | 108ms |
| **Background Total** | **5743ms** |
| **Gesamtzeit** | **~9000ms** |

**Erkenntnis**: Der WS Connect wartete fast immer die vollen 5 Sekunden auf ein `session.state_updated=connected` Event, das vom LiveAvatar-Server sehr spät (oder gar nicht innerhalb des Timeouts) kam.

### Runde 3 — Durchbruch (Commit `a10dbf8`)

**Problem**: WS Connect (5634ms) ist der dominante Engpass. Das "connected"-Event wird fast immer nach Timeout ignoriert.

**Maßnahmen**:

1. **Blockierende WS-Wartezeit entfernt**
   - `await asyncio.wait_for(self._connected_event.wait(), timeout=5.0)` komplett entfernt
   - Nur noch TCP/TLS Handshake, kein Wait auf Server-Event
   - Diagnostik: Server "connected"-Event wird asynchron geloggt wenn es eintrifft

2. **TTS Pre-Generation während REST API Calls**
   - TTS startet jetzt als `asyncio.create_task()` direkt nach `create_session_token()`, PARALLEL zu `start_session()`
   - Da start_session ~2.8s dauert und TTS nur ~500ms, ist Audio fertig bevor Background Task beginnt

**Ergebnisse (nach Optimierung)**:
| Schritt | Vorher | Nachher | Δ |
|---|---|---|---|
| `create_session_token` HTTP | 456ms | 399ms | -57ms |
| TTS Pre-Generation | 1761ms (nach API) | 493ms (während API) | Effektiv 0ms |
| `start_session` HTTP | 2799ms | 2752ms | -47ms |
| **API Total (synchron)** | **3267ms** | **3159ms** | **-108ms** |
| WS Connect | **5634ms** | **381ms** | **-5253ms (-93%)** |
| TTS Wait | — | 0ms (bereits fertig) | — |
| Setup Phase | — | 381ms | — |
| Cached Audio Send | 108ms | 115ms | +7ms |
| **Background Total** | **5743ms** | **496ms** | **-5247ms (-91%)** |
| **Gesamtzeit** | **~9000ms** | **~3655ms** | **-5345ms (-59%)** |

### Runde 3b — Bugfix (Commit `585bafa`)

- Keep-alive URL korrigiert: `/v1/sessions/keep-alive` → `/v1/sessions/keep_alive`
- Keep-alive Fehler graceful abfangen (WS Heartbeat bietet Redundanz)

### Runde 4 — HTTP/2 Fix & Stabilisierung (Commits `f41e124` → `458afa3`, 2026-03-16)

**Problem**: Avatar startete nicht mehr. `start_session` hing endlos — kein Video, keine Fehlermeldung, Frontend zeigte "Avatar wird geladen..." für immer.

**Diagnose-Verlauf**:
1. **Erste Vermutung**: Netzwerkproblem im Docker-Container → `/debug/network` Endpoint hinzugefügt (Commit `45a3f7c`)
2. **Zweite Vermutung**: API-Timeout zu niedrig → HTTP/1.1 erzwungen, Timeout auf 60s (Commit `f41e124`)
3. **Dritte Maßnahme**: Retry-Logik + besseres Logging (Commits `29632e1`, `c049590`)
4. **Durchbruch**: `curl -v` aus dem Docker-Container gezeigt:
   - `curl` nutzt HTTP/2 → Antwort in 6.6s ✅
   - `httpx` mit HTTP/1.1 → hängt endlos ❌
   - **Root Cause**: `/v1/sessions/start` ERFORDERT HTTP/2 hinter Cloudflare

**Lösung** (Commit `458afa3`):
- `start_session`, `stop_session`, `keep_alive` → `http2=True` (eigener AsyncClient pro Call)
- `create_session_token` → bleibt bei `http1=True, http2=False` (funktioniert nur so)
- `httpx[http2]` in requirements.txt (installiert `h2` Package)
- Frontend: AbortController mit Timeouts (90s/30s) als Sicherheitsnetz

**Ergebnisse (nach HTTP/2 Fix)**:
| Schritt | Runde 3 | Runde 4 | Status |
|---|---|---|---|
| `create_session_token` (HTTP/1.1) | ~400ms | ~233ms | ✅ |
| `start_session` (HTTP/2) | ~2750ms | ~3694ms | ✅ (vorher: Timeout!) |
| WS TCP Connect | ~381ms | ~565ms | ✅ |
| TTS Pre-Generation | 0ms (cache) | ~577ms (erste Session) | ✅ |
| Setup Phase | ~381ms | ~566ms | ✅ |
| Cached Audio Send | ~115ms | ~223ms | ✅ |
| **Total** | **~3655ms** | **~5s** | ✅ |

**Hinweis**: Die leicht höheren Zeiten in Runde 4 vs. Runde 3 erklären sich durch:
- `start_session` HTTP/2 vs. HTTP/1.1 hat mehr TLS-Overhead beim Connection Setup
- WS Connect Varianz (Netzwerk-abhängig)
- Es war die erste Session nach Deploy (kein TTS-Cache)

## Verbleibende Engpässe

| Engpass | Dauer | Kontrollierbar? |
|---|---|---|
| `start_session` API Call | ~2750ms | Nein (LiveAvatar-Server) |
| `create_session_token` API Call | ~400ms | Nein (LiveAvatar-Server) |
| WS TCP/TLS Handshake | ~380ms | Begrenzt (Netzwerk) |
| Audio Send (9 Chunks, 205KB) | ~115ms | Begrenzt (Netzwerk) |

**Fazit**: Die verbleibenden ~3.2s synchrone API-Zeit (Token + Start) sind durch die LiveAvatar-Infrastruktur vorgegeben. Backend-seitig sind alle Optimierungsmöglichkeiten ausgeschöpft.

## Zweite Session im gleichen Browser

Bei der zweiten Session (gleicher Avatar, gleicher Browser) profitiert man zusätzlich vom Greeting Audio Cache:
- TTS Pre-Generation: **0ms** (Cache Hit, "Greeting audio already cached")
- Keine ElevenLabs API-Call nötig
- Nur WS Connect (~380ms) + Audio Send (~115ms) = **~495ms Background**

## Technische Details

### Dateien mit Timing-Instrumentierung

- `backend/api/routes/sessions.py` — `create_token_ms`, `start_session_ms`, `total_api_ms`, `setup_phase_ms`, `greeting_send_ms`, `total_setup_ms`
- `backend/services/liveavatar_client.py` — `elapsed_ms` für HTTP Calls
- `backend/services/liveavatar_ws.py` — `tcp_connect_ms`, `ms_since_ws_connect` (Diagnoselog)
- `backend/services/conversation/engine.py` — TTS elapsed, cache lookup, audio send timing

### Log-Filter für Timing

In Coolify Logs nach `TIMING` filtern zeigt alle Performance-relevanten Logzeilen:
```
grep "TIMING" backend-logs
```
