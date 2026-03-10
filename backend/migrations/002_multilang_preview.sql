-- Migration 002: Multi-language support + avatar preview image
-- Features: Preview image, language selection, multilingual greetings

-- Avatar preview image (Base64 or URL, per tenant)
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS avatar_preview_image TEXT;

-- Supported languages for this tenant (JSON array, e.g. ["de","en","fr","es"])
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS supported_languages JSON DEFAULT '["de"]';

-- Greeting text in main language
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS greeting_text TEXT DEFAULT 'Hallo, ich bin Ihr digitaler Assistent und stehe Ihnen für Fragen zur Verfügung.';

-- Greeting translations (JSON object, e.g. {"en": "Hello, I am...", "fr": "Bonjour, je suis..."})
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS greeting_translations JSON DEFAULT '{}';

-- Default language for this tenant
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS default_language VARCHAR(10) DEFAULT 'de';
