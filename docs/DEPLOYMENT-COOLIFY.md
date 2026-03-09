# Deployment Guide — Coolify + Supabase + LiveKit Cloud

## Was läuft wo?

| Service | Wo? | Kosten |
|---|---|---|
| **Backend** (FastAPI) | Dein VPS via Coolify (Docker) | inkl. VPS |
| **Frontend** (React/Nginx) | Dein VPS via Coolify (Docker) | inkl. VPS |
| **Qdrant** (Vector DB) | Dein VPS via Coolify (Docker) | inkl. VPS |
| **Redis** (Cache) | Dein VPS via Coolify (Docker) | inkl. VPS |
| **PostgreSQL** | Supabase (extern) | Free Tier ausreichend |
| **LiveKit** (WebRTC) | LiveKit Cloud (extern) | Free: 10.000 Min/Monat |
| **Avatar Rendering** | HeyGen LiveAvatar (extern) | Enterprise Account |
| **LLM** | OpenAI API (extern) | Pay-per-use |

---

## Schritt-für-Schritt Anleitung

### Schritt 1: Accounts anlegen (5 Minuten)

#### LiveKit Cloud (kostenlos)
1. Gehe zu https://cloud.livekit.io
2. Erstelle einen Account
3. Erstelle ein neues Projekt
4. Gehe zu **Settings → Keys**
5. Notiere dir:
   - **URL**: `wss://dein-projekt.livekit.cloud`
   - **API Key**: `APIxxxxxxx`
   - **API Secret**: `xxxxxxxxxxxxxxxxx`

#### Supabase Datenbank
1. Gehe zu https://supabase.com (oder nutze deinen bestehenden Account)
2. Erstelle ein neues Projekt (Region: EU - Frankfurt)
3. Gehe zu **Settings → Database → Connection string → URI**
4. Kopiere die Connection URL
5. **WICHTIG**: Ersetze `postgresql://` durch `postgresql+asyncpg://`
   - Beispiel: `postgresql+asyncpg://postgres.abc123:MeinPasswort@aws-0-eu-central-1.pooler.supabase.com:6543/postgres`

### Schritt 2: GitHub Repository (5 Minuten)

1. Erstelle ein neues privates GitHub Repository (z.B. `liveavatar-platform`)
2. Pushe das Projekt dorthin:

```bash
cd liveavatar-platform
git init
git add .
git commit -m "Initial commit: LiveAvatar Platform"
git remote add origin https://github.com/DEIN-USER/liveavatar-platform.git
git push -u origin main
```

### Schritt 3: Coolify einrichten (10 Minuten)

#### 3.1 GitHub verbinden
1. Öffne dein Coolify Dashboard
2. Gehe zu **Sources** → **Add New Source** → **GitHub**
3. Verbinde deinen GitHub Account (OAuth oder Deploy Key)

#### 3.2 Neues Projekt anlegen
1. Klicke auf **Projects** → **Add New Project**
2. Name: `LiveAvatar Platform`

#### 3.3 Application hinzufügen
1. Im Projekt: **Add New Resource** → **Application**
2. Wähle **GitHub** als Source
3. Wähle dein Repository `liveavatar-platform`
4. Branch: `main`
5. Build Pack: **Docker Compose**
6. Coolify erkennt automatisch die `docker-compose.yml`

#### 3.4 Domain zuweisen
1. Gehe zur Application → **Settings**
2. Bei **Domains** trage deine Domain ein, z.B.: `liveavatar.deine-domain.de`
3. **Service**: Wähle `frontend` (Port 80)
4. Coolify erstellt automatisch ein SSL-Zertifikat über Let's Encrypt

#### 3.5 DNS konfigurieren
Bei deinem Domain-Provider einen A-Record setzen:
```
liveavatar.deine-domain.de → IP-deines-VPS
```

### Schritt 4: Environment Variables setzen (5 Minuten)

In Coolify unter **Environment Variables** diese Werte eintragen:

```
APP_ENV=production
APP_SECRET_KEY=<generiere mit: openssl rand -hex 32>
APP_CORS_ORIGINS=https://liveavatar.deine-domain.de
DATABASE_URL=postgresql+asyncpg://postgres.xxx:password@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
HEYGEN_API_KEY=<dein HeyGen API Key>
LIVEKIT_URL=wss://dein-projekt.livekit.cloud
LIVEKIT_API_KEY=<LiveKit Cloud API Key>
LIVEKIT_API_SECRET=<LiveKit Cloud API Secret>
OPENAI_API_KEY=<dein OpenAI API Key>
JWT_SECRET_KEY=<generiere mit: openssl rand -hex 32>
```

### Schritt 5: Deploy (1 Minute)

1. Klicke auf **Deploy** in Coolify
2. Coolify baut automatisch:
   - Backend Docker Image (Python/FastAPI)
   - Frontend Docker Image (React → Nginx)
   - Startet Qdrant + Redis Container
3. Warte bis alle Services grün sind (ca. 3-5 Minuten)

### Schritt 6: Testen

#### Health Check
```bash
curl https://liveavatar.deine-domain.de/health
# → {"status": "healthy", "service": "LiveAvatar Platform", "version": "1.0.0"}
```

#### API Docs
Öffne im Browser: `https://liveavatar.deine-domain.de/api/v1/docs`
(FastAPI Swagger UI mit allen Endpoints)

#### Ersten Tenant anlegen
```bash
curl -X POST https://liveavatar.deine-domain.de/api/v1/tenants/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Demo",
    "slug": "demo",
    "heygen_avatar_id": "DEIN_AVATAR_ID_AUS_HEYGEN",
    "llm_provider": "openai",
    "llm_model": "gpt-4o",
    "system_prompt": "Du bist ein freundlicher Assistent. Antworte auf Deutsch, kurz und präzise."
  }'
```

Notiere dir den `api_key` aus der Antwort!

#### Avatar testen
Öffne: `https://liveavatar.deine-domain.de/avatar/demo`

---

## Checkliste vor dem Deployment

- [ ] LiveKit Cloud Account erstellt + Keys notiert
- [ ] Supabase Projekt erstellt + Connection URL (mit asyncpg!) notiert
- [ ] HeyGen API Key bereit
- [ ] OpenAI API Key bereit
- [ ] GitHub Repository erstellt + Code gepusht
- [ ] DNS A-Record gesetzt (Domain → VPS IP)
- [ ] In Coolify: GitHub Source verbunden
- [ ] In Coolify: Application als Docker Compose angelegt
- [ ] In Coolify: Domain zugewiesen
- [ ] In Coolify: Alle Environment Variables gesetzt
- [ ] Deploy gestartet und alle Services grün
- [ ] Health Check erfolgreich
- [ ] Erster Tenant angelegt

---

## Troubleshooting

**Backend startet nicht?**
→ Prüfe die DATABASE_URL (muss `postgresql+asyncpg://` sein, nicht `postgresql://`)

**Frontend zeigt 502?**
→ Backend ist noch nicht bereit. Warte 1-2 Minuten oder prüfe Coolify Logs.

**Avatar-Video kommt nicht?**
→ Prüfe LIVEKIT_URL (muss `wss://` sein) und LIVEKIT_API_KEY/SECRET

**CORS-Fehler im Browser?**
→ APP_CORS_ORIGINS muss exakt deine Domain enthalten (mit https://)

---

## Monatliche Kosten (Schätzung)

| Service | Kosten |
|---|---|
| VPS (dein bestehender) | 0€ (bereits vorhanden) |
| Supabase (Free Tier) | 0€ |
| LiveKit Cloud (Free Tier) | 0€ (bis 10.000 Min) |
| OpenAI API (GPT-4o) | ~5-20€/Monat je nach Nutzung |
| HeyGen LiveAvatar | Enterprise Vertrag (besteht) |
| **Gesamt** | **~5-20€/Monat** (+ HeyGen) |
