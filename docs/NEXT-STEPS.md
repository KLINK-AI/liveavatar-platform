# LiveAvatar Platform — Next Steps & Roadmap

**Stand**: 16. März 2026 (v0.4.1)
**Basis**: Avatar funktioniert, Session-Aufbau ~5s, Text-Chat aktiv, P1 Bugs behoben

---

## Priorität 1 — Bugs & Stabilität ✅ ERLEDIGT

### 1.1 STT / Spracheingabe ✅
**Lösung**: Browser Web Speech API statt LiveKit Agent. BCP-47 Language Mapping (de→de-DE etc.) implementiert.
LiveKit Agent ImportError auf DEBUG-Level gesetzt (erwartet, nicht kritisch).

### 1.2 `/debug/network` Endpoint ✅
**Lösung**: Komplett entfernt aus `backend/main.py` (~100 Zeilen).

### 1.3 Diagnostic Logging ✅
**Lösung**: Raw JSON Response-Dump entfernt, keep_alive 405 auf DEBUG-Level.

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

### 3.1 🔥 Kunden-Admin (tenant_admin Rolle) — NÄCHSTES FEATURE
**Referenz**: buergerguide.botgenossen.cloud/admin/rag (Partner-System als Vorlage)
**Impact**: Kunden können selbständig ihre Knowledge Base verwalten, Qualität prüfen und Nutzung analysieren.
**Status**: In Planung

#### 3.1.1 Auth & Rollen-System
Separater Login für Kunden-Admins (tenant_admin), getrennt vom Master-Admin (superadmin).
Jeder tenant_admin sieht NUR seinen eigenen Tenant — keine Mandantenübergreifende Sicht.

Neues Rollen-Modell:
- `superadmin` — Platform-Betreiber (Stefan), sieht alle Tenants
- `tenant_admin` — Kunde, sieht nur eigenen Tenant (KB, Logs, Analytics)

Neue Dateien:
- `backend/models/user.py` — User-Model mit Rolle + Tenant-Zuordnung
- `backend/api/routes/auth.py` — Login, JWT-Token, Role-Guard
- `backend/api/middleware/tenant_guard.py` — Middleware: tenant_admin darf nur eigenen Tenant

#### 3.1.2 Knowledge Base Management (Dokumente Tab)
Kunden-Admin kann Dokumente hochladen, einsehen und löschen.
Anzeige: Dateiname, Upload-Datum, Chunk-Anzahl, Status (aktiv/inaktiv).

Neue Dateien:
- `frontend/src/pages/TenantAdmin/DocumentsTab.tsx`
- Backend nutzt existierende `api/routes/knowledge.py` (erweitert um tenant_admin Auth)

#### 3.1.3 Test Query Interface (Test Query Tab)
Chat-Interface direkt im Admin-Bereich — Fragen stellen ohne Video-Avatar.
Zeigt: Antworttext, verwendete RAG-Quellen mit Confidence %, Antwortzeit-Breakdown (RAG, LLM, Gesamt).
Daneben: System Prompt Editor (anzeigen + bearbeiten + testen).

Neue Dateien:
- `frontend/src/pages/TenantAdmin/TestQueryTab.tsx`
- `backend/api/routes/tenant_admin.py` — `/test-query` Endpoint (nur LLM+RAG, kein TTS/Avatar)

#### 3.1.4 Chat Logs (Logs & Analysen Tab)
Alle Fragen und Antworten werden persistent geloggt.
Pro Eintrag sichtbar: Zeitstempel, Benutzeranfrage, Bot-Antwort, RAG-Tag (ob RAG genutzt wurde),
verwendete Quelldokumente mit Confidence %, Antwortzeit (Gesamt, RAG, LLM), Token-Verbrauch.
Expandierbare Zeilen wie im Botgenossen-System.

Neue Dateien:
- `backend/models/chat_log.py` — ChatLog Model (session_id, tenant_id, user_msg, bot_msg, rag_sources, timings, tokens)
- `backend/api/routes/tenant_admin.py` — `/chat-logs` Endpoint mit Pagination + Filter
- `frontend/src/pages/TenantAdmin/ChatLogsTab.tsx`

#### 3.1.5 Document Analytics (Analytik Tab)
Welche Dokumente werden wie oft als Quelle herangezogen?
Heatmap/Balkendiagramm der Dokumentnutzung, Zugriffsfrequenz pro Dokument,
ungenutzte Dokumente identifizieren, Zeitverlauf der Nutzung.

Neue Dateien:
- `backend/api/routes/tenant_admin.py` — `/analytics` Endpoint
- `frontend/src/pages/TenantAdmin/AnalyticsTab.tsx`

#### 3.1.6 System Prompt Editor
System Prompt anzeigen und bearbeiten (pro Tenant).
Änderungen sofort testbar über Test Query Tab.

Erweitert: `backend/api/routes/tenants.py` (System Prompt CRUD)
Neue Datei: `frontend/src/pages/TenantAdmin/SystemPromptEditor.tsx`

#### Implementierungsreihenfolge:
1. Backend: User Model + Auth (JWT Login, tenant_admin Rolle)
2. Backend: ChatLog Model + Logging in ConversationEngine
3. Backend: tenant_admin API Endpoints (chat-logs, test-query, analytics)
4. Frontend: TenantAdmin Dashboard mit Tabs (Dokumente, Test Query, Logs, Analytik)
5. Integration + Test

---

### 3.2 Streaming-Antworten (LLM → TTS → Avatar)
**Was**: Aktuell wartet der Avatar bis die komplette LLM-Antwort fertig ist, dann wird alles auf einmal gesprochen.
**Idee**: LLM-Tokens streamen, Satz-für-Satz an TTS schicken, Avatar spricht progressiv
**Impact**: Deutlich natürlicheres Gesprächserlebnis, geringere wahrgenommene Latenz
**Dateien**: `backend/services/conversation/engine.py`, `backend/services/tts/elevenlabs_provider.py`

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

| # | Aufgabe | Datei(en) | Status |
|---|---|---|---|
| 1 | `/debug/network` entfernen | `backend/main.py` | ✅ |
| 2 | Diagnostic Logging auf DEBUG | `backend/services/liveavatar_client.py` | ✅ |
| 3 | keep_alive 405 Warning suppressor | `backend/services/liveavatar_client.py` | ✅ |
| 4 | Frontend Loading-Text verbessern | `frontend/src/pages/AvatarPage.tsx` | Offen |
| 5 | Audio Cache in Redis verschieben | `backend/services/conversation/engine.py` | Offen |
