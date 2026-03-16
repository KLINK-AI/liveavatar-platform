# LiveAvatar Platform — Next Steps & Roadmap

**Stand**: 16. März 2026 (v0.4.0)
**Basis**: Avatar funktioniert, Session-Aufbau ~5s, Text-Chat aktiv

---

## Priorität 1 — Bugs & Stabilität

### 1.1 STT / Spracheingabe reparieren
**Status**: Defekt (UI vorhanden, Backend-Import schlägt fehl)
**Fehler**: `cannot import name 'rtc' from 'livekit'`
**Impact**: User sehen "oder per Mikrofon sprechen" aber es funktioniert nicht
**Ansatz**: `livekit-agents` korrekt installieren oder Alternative (z.B. Deepgram direkt via WebSocket)
**Dateien**: `backend/services/livekit_manager.py`, `backend/requirements.txt`

### 1.2 `/debug/network` Endpoint entfernen/sichern
**Status**: Offen
**Risk**: Gibt interne Netzwerk-Infos preis (DNS, IP, Container-Details)
**Ansatz**: Entweder entfernen oder hinter Admin-Auth setzen
**Datei**: `backend/main.py`

### 1.3 Diagnostic Logging aufräumen
**Status**: Offen
**Was**: `start_session` loggt vollständige Raw-Response (bis 2000 Zeichen) auf INFO-Level
**Ansatz**: Auf DEBUG-Level setzen oder `import json as _json` entfernen
**Datei**: `backend/services/liveavatar_client.py` (Zeilen ~248-260)

---

## Priorität 2 — UX-Verbesserungen

### 2.1 Loading-State verbessern
**Was**: Zwischen "Gespräch starten" und Avatar-Video vergehen ~5s. User sieht nur ein statisches Bild.
**Idee**: Animierter Loading-Indikator, Fortschrittsanzeige ("Verbinde mit Avatar...", "Lade Begrüßung...")
**Dateien**: `frontend/src/pages/AvatarPage.tsx`, `frontend/src/hooks/useAvatarSession.ts`

### 2.2 Fehler-Recovery
**Was**: Bei API-Fehler (z.B. 500 von LiveAvatar) sieht User nur generische Fehlermeldung.
**Idee**: "Erneut versuchen" Button, automatischer Retry im Frontend
**Dateien**: `frontend/src/pages/AvatarPage.tsx`

### 2.3 Session-Timeout Handling
**Was**: LiveAvatar Session läuft nach max_session_duration (3600s) ab.
**Idee**: Countdown-Anzeige, automatische Verlängerung, oder saubere "Session abgelaufen" Meldung
**Dateien**: `frontend/src/hooks/useAvatarSession.ts`, `backend/api/routes/sessions.py`

---

## Priorität 3 — Features

### 3.1 Streaming-Antworten (LLM → TTS → Avatar)
**Was**: Aktuell wartet der Avatar bis die komplette LLM-Antwort fertig ist, dann wird alles auf einmal gesprochen.
**Idee**: LLM-Tokens streamen, Satz-für-Satz an TTS schicken, Avatar spricht progressiv
**Impact**: Deutlich natürlicheres Gesprächserlebnis, geringere wahrgenommene Latenz
**Dateien**: `backend/services/conversation/engine.py`, `backend/services/tts/elevenlabs_provider.py`

### 3.2 Conversation History / Analytics
**Was**: Gespräche werden aktuell nur in-memory gehalten, kein persistentes Logging.
**Idee**: Alle Fragen + Antworten in Supabase speichern, Analytics-Dashboard für Tenant-Admin
**Dateien**: `backend/api/routes/messages.py`, `backend/models/`

### 3.3 Custom Avatar Upload
**Was**: Avatare müssen aktuell über LiveAvatar Dashboard erstellt werden.
**Idee**: Upload-Flow im Admin Dashboard (Video hochladen → LiveAvatar API → Avatar ID)
**Dateien**: `backend/api/routes/tenants.py`, `frontend/src/pages/AdminDashboard.tsx`

### 3.4 Embed Widget
**Was**: Avatar ist nur über die eigene Platform-URL erreichbar.
**Idee**: JavaScript Embed-Code (`<script>` Tag) für Kundenwebseiten, iFrame-Alternative
**Neue Dateien**: `frontend/src/embed/`, Widget-Bundle mit Vite

### 3.5 Mehrere Avatare pro Tenant
**Was**: Aktuell hat jeder Tenant genau einen Avatar.
**Idee**: Tenant kann mehrere Avatare konfigurieren (z.B. verschiedene Sprachen, Themen)
**Dateien**: DB-Schema-Änderung, `backend/models/`, `backend/api/routes/tenants.py`

---

## Priorität 4 — Infrastruktur

### 4.1 Audio Cache persistent machen
**Was**: Greeting-Audio geht bei Backend-Restart verloren.
**Idee**: Redis als Cache-Backend statt In-Memory Dict
**Dateien**: `backend/services/conversation/engine.py`

### 4.2 HTTP Client optimieren
**Was**: `start_session`/`stop_session`/`keep_alive` erstellen jeweils eigenen httpx Client.
**Idee**: Zwei Singleton-Clients (HTTP/1.1 + HTTP/2) mit Connection Pooling
**Datei**: `backend/services/liveavatar_client.py`

### 4.3 Rate Limiting
**Was**: Kein Rate Limiting auf API-Ebene.
**Idee**: Redis-basiertes Rate Limiting pro API-Key
**Dateien**: `backend/api/middleware/`, Redis ist bereits im Stack

### 4.4 Monitoring & Alerting
**Was**: Logs nur über Coolify UI einsehbar.
**Idee**: Structured Logging nach Grafana/Loki, Uptime Monitoring, Alert bei Fehlerrate > X%
**Dateien**: `docker-compose.yml` (Loki Driver), `backend/main.py`

### 4.5 CI/CD Pipeline
**Was**: Nur Coolify Auto-Deploy bei Push auf main.
**Idee**: GitHub Actions für Tests, Linting, Build-Check vor Deploy
**Neue Dateien**: `.github/workflows/`

---

## Schnelle Wins (< 1 Stunde)

| # | Aufgabe | Datei(en) |
|---|---|---|
| 1 | `/debug/network` entfernen | `backend/main.py` |
| 2 | Diagnostic Logging auf DEBUG | `backend/services/liveavatar_client.py` |
| 3 | keep_alive 405 Warning suppressor | `backend/services/liveavatar_client.py` |
| 4 | Frontend Loading-Text verbessern | `frontend/src/pages/AvatarPage.tsx` |
| 5 | Audio Cache in Redis verschieben | `backend/services/conversation/engine.py` |
