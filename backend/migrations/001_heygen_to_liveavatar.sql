-- Migration: HeyGen Streaming API → LiveAvatar LITE Mode
-- Date: 2026-03-09
-- Description: Rename heygen_* fields to liveavatar_*, add TTS/STT/WebSocket fields
--
-- IMPORTANT: Run this migration BEFORE deploying the new code.
-- The new code references the new column names.

-- ============================================
-- TENANTS TABLE: Add new columns
-- ============================================

-- Rename heygen columns to liveavatar
ALTER TABLE tenants RENAME COLUMN heygen_avatar_id TO liveavatar_avatar_id;
ALTER TABLE tenants RENAME COLUMN heygen_voice_id TO liveavatar_voice_id;

-- Add ElevenLabs TTS columns (per-tenant override)
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS elevenlabs_api_key TEXT;
COMMENT ON COLUMN tenants.elevenlabs_api_key IS 'Per-tenant ElevenLabs API key (falls back to global config)';

ALTER TABLE tenants ADD COLUMN IF NOT EXISTS elevenlabs_voice_id VARCHAR(255);
COMMENT ON COLUMN tenants.elevenlabs_voice_id IS 'Per-tenant ElevenLabs voice ID';

-- Add STT provider column (per-tenant override)
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS stt_provider VARCHAR(50);
COMMENT ON COLUMN tenants.stt_provider IS 'deepgram or openai — falls back to global config';


-- ============================================
-- AVATAR_SESSIONS TABLE: Add new columns
-- ============================================

-- Rename heygen_session_id to liveavatar_session_id
ALTER TABLE avatar_sessions RENAME COLUMN heygen_session_id TO liveavatar_session_id;

-- Add session token for WebSocket auth
ALTER TABLE avatar_sessions ADD COLUMN IF NOT EXISTS liveavatar_session_token TEXT;
COMMENT ON COLUMN avatar_sessions.liveavatar_session_token IS 'Session token for WebSocket authentication';

-- Add WebSocket URL for LITE Mode commands
ALTER TABLE avatar_sessions ADD COLUMN IF NOT EXISTS ws_url VARCHAR(500);
COMMENT ON COLUMN avatar_sessions.ws_url IS 'WebSocket URL for LITE Mode command events';

-- Add WebSocket status tracking
ALTER TABLE avatar_sessions ADD COLUMN IF NOT EXISTS ws_status VARCHAR(50) DEFAULT 'disconnected';
COMMENT ON COLUMN avatar_sessions.ws_status IS 'WebSocket state: disconnected/connecting/connected/closed';


-- ============================================
-- VERIFICATION
-- ============================================
-- Run after migration to verify:
-- SELECT column_name, data_type FROM information_schema.columns
-- WHERE table_name = 'tenants' AND column_name LIKE 'liveavatar%';
--
-- SELECT column_name, data_type FROM information_schema.columns
-- WHERE table_name = 'avatar_sessions' AND column_name LIKE 'liveavatar%';
