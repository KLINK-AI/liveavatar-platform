/**
 * Avatar Page — Public-facing page for end users.
 *
 * Accessed via /avatar/:tenantSlug
 * Flow:
 * 1. Load tenant config (incl. API key, preview image, languages)
 * 2. Show preview image (instead of black screen)
 * 3. If multi-language: show language picker
 * 4. Start avatar session with selected language
 * 5. Send greeting in selected language
 * 6. Begin conversation
 */

import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams } from 'react-router-dom'
import AvatarPlayer from '../components/AvatarPlayer'
import ChatInterface from '../components/ChatInterface'
import VoiceInput from '../components/VoiceInput'
import LanguagePicker from '../components/LanguagePicker'
import { useConversation } from '../hooks/useConversation'
import { tenantApi, sessionApi } from '../lib/api'
import { Play } from 'lucide-react'

interface TenantConfig {
  name: string
  slug: string
  branding: {
    primary_color?: string
    logo_url?: string
    background_color?: string
  } | null
  has_avatar: boolean
  api_key: string
  avatar_preview_image: string | null
  supported_languages: string[]
  default_language: string
  greeting_text: string | null
  greeting_translations: Record<string, string>
}

interface AvatarSession {
  sessionId: string
  livekitUrl: string | null
  livekitToken: string | null
  status: string
}

type PageState = 'loading' | 'preview' | 'language_select' | 'connecting' | 'active' | 'error'

export default function AvatarPage() {
  const { tenantSlug } = useParams<{ tenantSlug: string }>()
  const [tenantConfig, setTenantConfig] = useState<TenantConfig | null>(null)
  const [session, setSession] = useState<AvatarSession | null>(null)
  const [pageState, setPageState] = useState<PageState>('loading')
  const [selectedLanguage, setSelectedLanguage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const keepAliveRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const sessionStartedRef = useRef(false)

  // Step 1: Load tenant config (includes API key, preview image, languages)
  useEffect(() => {
    if (!tenantSlug) return
    tenantApi.getBySlug(tenantSlug)
      .then((config: any) => {
        setTenantConfig(config)
        setPageState('preview')
      })
      .catch(() => {
        setError(`Mandant "${tenantSlug}" nicht gefunden.`)
        setPageState('error')
      })
  }, [tenantSlug])

  // Step 2: User clicks "Start" on preview → show language picker or start directly
  const handleStartClick = useCallback(() => {
    if (!tenantConfig) return

    const languages = tenantConfig.supported_languages || ['de']
    if (languages.length > 1) {
      // Multi-language: show language picker
      setPageState('language_select')
    } else {
      // Single language: start directly
      setSelectedLanguage(languages[0] || 'de')
    }
  }, [tenantConfig])

  // Step 3: Language selected → start session
  const handleLanguageSelect = useCallback((language: string) => {
    setSelectedLanguage(language)
    setPageState('connecting')
  }, [])

  // Auto-start when language is selected and we're not yet in a session
  useEffect(() => {
    if (selectedLanguage && !session && pageState !== 'active') {
      setPageState('connecting')
      startSession(selectedLanguage)
    }
  }, [selectedLanguage])

  // Step 4: Create session + send greeting
  const startSession = useCallback(async (language: string) => {
    if (!tenantConfig?.api_key || !tenantConfig.has_avatar) return
    if (sessionStartedRef.current) return
    sessionStartedRef.current = true
    setError(null)

    try {
      // Create session with selected language
      const data = await sessionApi.create(tenantConfig.api_key, { language })
      const newSession: AvatarSession = {
        sessionId: data.session_id,
        livekitUrl: data.livekit_url,
        livekitToken: data.livekit_token,
        status: data.status,
      }
      setSession(newSession)
      setPageState('active')

      // Keep-alive every 60s
      keepAliveRef.current = setInterval(async () => {
        try {
          await sessionApi.keepAlive(newSession.sessionId, tenantConfig.api_key)
        } catch (e) {
          console.warn('Keep-alive failed:', e)
        }
      }, 60000)

      // Greeting is now sent automatically by the backend
      // immediately after WebSocket connects (no delay needed)

    } catch (e: any) {
      sessionStartedRef.current = false
      setError(e.message || 'Session konnte nicht gestartet werden.')
      setPageState('error')
    }
  }, [tenantConfig])

  // Cleanup
  useEffect(() => {
    return () => {
      if (keepAliveRef.current) clearInterval(keepAliveRef.current)
    }
  }, [])

  const stopSession = useCallback(async () => {
    if (!session || !tenantConfig) return
    if (keepAliveRef.current) {
      clearInterval(keepAliveRef.current)
      keepAliveRef.current = null
    }
    try {
      await sessionApi.stop(session.sessionId, tenantConfig.api_key)
    } catch (e) {
      console.warn('Session stop error:', e)
    }
    setSession(null)
    setSelectedLanguage(null)
    sessionStartedRef.current = false
    setPageState('preview')
  }, [session, tenantConfig])

  const {
    messages,
    isLoading,
    streamingText,
    sendMessage,
  } = useConversation({
    sessionId: session?.sessionId || '',
    apiKey: tenantConfig?.api_key || '',
  })

  const primaryColor = tenantConfig?.branding?.primary_color || '#2563eb'
  const isActive = session?.status === 'active' || session?.status === 'creating'

  // --- RENDER ---

  // Loading state
  if (pageState === 'loading') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin w-10 h-10 border-3 border-blue-600 border-t-transparent rounded-full mx-auto mb-4" />
          <p className="text-gray-500">Wird geladen...</p>
        </div>
      </div>
    )
  }

  // Error state
  if (pageState === 'error' && !session) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-md text-center">
          <div className="text-4xl mb-4">&#9888;</div>
          <h1 className="text-xl font-bold mb-2 text-gray-900">Fehler</h1>
          <p className="text-gray-500 mb-6">{error}</p>
          <button
            onClick={() => {
              sessionStartedRef.current = false
              setPageState('preview')
              setError(null)
            }}
            className="px-6 py-3 rounded-xl text-white font-medium"
            style={{ backgroundColor: primaryColor }}
          >
            Erneut versuchen
          </button>
        </div>
      </div>
    )
  }

  // No avatar configured
  if (tenantConfig && !tenantConfig.has_avatar) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-md text-center">
          <h1 className="text-xl font-bold mb-2">{tenantConfig.name}</h1>
          <p className="text-gray-500">
            Kein Avatar konfiguriert. Bitte weisen Sie im Admin-Dashboard einen Avatar zu.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div
      className="min-h-screen p-4 md:p-8"
      style={{ backgroundColor: tenantConfig?.branding?.background_color || '#f3f4f6' }}
    >
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            {tenantConfig?.branding?.logo_url && (
              <img
                src={tenantConfig.branding.logo_url}
                alt={tenantConfig.name}
                className="h-10"
              />
            )}
            <h1 className="text-xl font-bold text-gray-900">
              {tenantConfig?.name || 'Avatar Assistent'}
            </h1>
          </div>
          {session && (
            <button
              onClick={stopSession}
              className="px-4 py-2 rounded-lg bg-red-100 text-red-600 hover:bg-red-200 text-sm"
            >
              Session beenden
            </button>
          )}
        </div>

        {/* Main Layout — avatar and chat side by side, same height */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Avatar Video / Preview — unified wrapper ensures consistent size */}
          <div className="flex flex-col">
            <div className="avatar-wrapper shadow-2xl">
              {session?.livekitUrl && session?.livekitToken ? (
                /* Active session: show live avatar video */
                <AvatarPlayer
                  livekitUrl={session.livekitUrl}
                  livekitToken={session.livekitToken}
                />
              ) : (
                /* Preview / Start screen */
                <>
                  {/* Preview Image */}
                  {tenantConfig?.avatar_preview_image ? (
                    <img
                      src={tenantConfig.avatar_preview_image}
                      alt={`${tenantConfig.name} Avatar`}
                      className="w-full h-full object-cover absolute inset-0"
                    />
                  ) : (
                    /* Fallback: gradient background */
                    <div className="w-full h-full bg-gradient-to-br from-gray-800 to-gray-900 absolute inset-0" />
                  )}

                  {/* Start overlay */}
                  {pageState === 'preview' && (
                    <div className="absolute inset-0 flex flex-col items-center justify-end pb-[15%] bg-black/30">
                      <button
                        onClick={handleStartClick}
                        className="group flex items-center gap-3 px-8 py-4 rounded-2xl text-white font-semibold text-lg shadow-xl transition-all hover:scale-105 active:scale-95"
                        style={{ backgroundColor: primaryColor }}
                      >
                        <Play className="w-6 h-6 group-hover:scale-110 transition-transform" />
                        Gespräch starten
                      </button>
                      <p className="text-white/70 text-sm mt-3">
                        {tenantConfig?.name || 'Avatar Assistent'}
                      </p>
                    </div>
                  )}

                  {/* Connecting spinner */}
                  {pageState === 'connecting' && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/50">
                      <div className="text-center text-white">
                        <div className="animate-spin w-12 h-12 border-3 border-white border-t-transparent rounded-full mx-auto mb-3" />
                        <p className="font-medium">Avatar wird geladen...</p>
                        {selectedLanguage && (
                          <p className="text-sm text-white/60 mt-1">
                            Sprache: {selectedLanguage.toUpperCase()}
                          </p>
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Voice Input — only when active */}
            {isActive && (
              <div className="mt-4">
                <VoiceInput
                  onTranscript={sendMessage}
                  disabled={isLoading}
                />
              </div>
            )}
          </div>

          {/* Chat Interface — fixed height matching the avatar (16:9 aspect) */}
          <div className="avatar-chat-column">
            <ChatInterface
              messages={messages}
              streamingText={streamingText}
              isLoading={isLoading}
              onSendMessage={sendMessage}
            />
          </div>
        </div>
      </div>

      {/* Language Picker Modal */}
      {pageState === 'language_select' && tenantConfig && (
        <LanguagePicker
          supportedLanguages={tenantConfig.supported_languages}
          defaultLanguage={tenantConfig.default_language}
          onSelect={handleLanguageSelect}
          tenantName={tenantConfig.name}
        />
      )}
    </div>
  )
}
