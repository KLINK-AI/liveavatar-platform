# Environment-Variablen

Alle Variablen werden über `.env` Datei oder Umgebungsvariablen gesetzt.

## App

| Variable | Default | Beschreibung |
|---|---|---|
| `APP_NAME` | `LiveAvatar Platform` | App-Name |
| `APP_ENV` | `development` | Umgebung |
| `APP_SECRET_KEY` | `change-me` | **Ändern!** App-Secret |
| `APP_CORS_ORIGINS` | `http://localhost:5173,...` | Erlaubte Origins (Komma-separiert) |

## LiveAvatar LITE Mode API

| Variable | Default | Beschreibung |
|---|---|---|
| `LIVEAVATAR_API_KEY` | — | **Pflicht.** LiveAvatar API Key |
| `LIVEAVATAR_API_BASE` | `https://api.liveavatar.com` | API Base URL |

## TTS — ElevenLabs

| Variable | Default | Beschreibung |
|---|---|---|
| `ELEVENLABS_API_KEY` | — | **Pflicht.** ElevenLabs API Key |
| `ELEVENLABS_DEFAULT_VOICE_ID` | — | **Pflicht.** Standard-Stimme |
| `ELEVENLABS_MODEL_ID` | `eleven_multilingual_v2` | TTS-Modell |
| `TTS_SAMPLE_RATE` | `24000` | PCM Output Sample Rate (24KHz für LiveAvatar) |

## STT — Speech-to-Text

| Variable | Default | Beschreibung |
|---|---|---|
| `STT_PROVIDER` | `deepgram` | `deepgram` oder `openai` |
| `DEEPGRAM_API_KEY` | — | **Pflicht bei deepgram.** Deepgram API Key |
| `DEEPGRAM_MODEL` | `nova-2` | Deepgram-Modell |
| `DEEPGRAM_LANGUAGE` | `de` | Standard-Sprache |

## LiveKit WebRTC

| Variable | Default | Beschreibung |
|---|---|---|
| `LIVEKIT_URL` | `ws://localhost:7880` | LiveKit Server URL |
| `LIVEKIT_API_KEY` | — | LiveKit API Key |
| `LIVEKIT_API_SECRET` | — | LiveKit API Secret |

## LLM Providers

| Variable | Default | Beschreibung |
|---|---|---|
| `OPENAI_API_KEY` | — | OpenAI API Key |
| `ANTHROPIC_API_KEY` | — | Anthropic API Key |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama Server URL |
| `DEFAULT_LLM_PROVIDER` | `openai` | Standard LLM Provider |
| `DEFAULT_LLM_MODEL` | `gpt-4o` | Standard LLM Modell |

## Datenbank

| Variable | Default | Beschreibung |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL Connection String |

## Vector DB (RAG)

| Variable | Default | Beschreibung |
|---|---|---|
| `QDRANT_URL` | `http://localhost:6333` | Qdrant Server URL |
| `QDRANT_API_KEY` | — | Qdrant API Key |

## Embeddings

| Variable | Default | Beschreibung |
|---|---|---|
| `EMBEDDING_PROVIDER` | `openai` | Embedding Provider |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding Modell |

## Auth / JWT

| Variable | Default | Beschreibung |
|---|---|---|
| `JWT_SECRET_KEY` | `change-me` | **Ändern!** JWT Secret |
| `JWT_ALGORITHM` | `HS256` | JWT Algorithmus |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token-Gültigkeit |

## Redis

| Variable | Default | Beschreibung |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis Connection String |
