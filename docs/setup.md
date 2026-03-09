# LiveAvatar Platform — Setup Guide

## Voraussetzungen

- Docker & Docker Compose
- HeyGen Enterprise Account + API Key
- OpenAI oder Anthropic API Key
- (Optional) Eigener LiveKit Server oder LiveKit Cloud Account

## Quick Start

### 1. Repository klonen & konfigurieren

```bash
cd liveavatar-platform
cp .env.example .env
```

### 2. .env Datei anpassen

Mindestens diese Werte setzen:
- `HEYGEN_API_KEY` — Dein HeyGen API Key
- `OPENAI_API_KEY` — Für LLM und Embeddings
- `APP_SECRET_KEY` — Zufälliger String
- `JWT_SECRET_KEY` — Zufälliger String

### 3. Services starten

```bash
docker compose up -d
```

Das startet: Backend (Port 8000), Frontend (Port 5173), PostgreSQL, Qdrant, Redis.

### 4. Ersten Tenant anlegen

```bash
curl -X POST http://localhost:8000/api/v1/tenants/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Demo Tenant",
    "slug": "demo",
    "heygen_avatar_id": "DEIN_AVATAR_ID",
    "llm_provider": "openai",
    "llm_model": "gpt-4o",
    "system_prompt": "Du bist ein freundlicher Assistent."
  }'
```

Notiere dir den `api_key` aus der Antwort.

### 5. Wissensbasis anlegen

```bash
# Knowledge Base erstellen
curl -X POST http://localhost:8000/api/v1/knowledge/ \
  -H "X-API-Key: DEIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "Hauptwissen"}'

# URL indexieren
curl -X POST http://localhost:8000/api/v1/knowledge/KB_ID/urls \
  -H "X-API-Key: DEIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://deine-website.de", "crawl_site": true}'
```

### 6. Avatar testen

Öffne im Browser: `http://localhost:5173/avatar/demo`

### 7. Auf Website einbetten

```html
<script
  src="https://dein-server.de/embed.js"
  data-api-key="DEIN_API_KEY"
  data-tenant="demo"
  data-position="bottom-right"
></script>
```

## Architektur

```
User → Frontend (React/LiveKit) → Backend (FastAPI)
                                     ├── RAG Pipeline (Qdrant)
                                     ├── LLM (OpenAI/Claude/Ollama)
                                     └── HeyGen LiveAvatar API
                                          └── LiveKit WebRTC Stream → User sieht Avatar
```

## API Dokumentation

Nach dem Start erreichbar unter: `http://localhost:8000/docs`

## Production Deployment

Für Production:
1. HTTPS/SSL mit Nginx Reverse Proxy einrichten
2. `.env` mit sicheren Passwörtern aktualisieren
3. `APP_ENV=production` setzen
4. LiveKit Cloud oder eigenen LiveKit Server nutzen
5. Backups für PostgreSQL und Qdrant einrichten
