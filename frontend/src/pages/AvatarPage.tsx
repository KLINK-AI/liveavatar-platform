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
 *
 * v2.5: Unified Player Control Bar (Mic, Language, Chat-Toggle)
 *       Chat history hidden by default, toggle-able by user
 */

import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams } from 'react-router-dom'
import AvatarPlayer from '../components/AvatarPlayer'
import ChatInterface from '../components/ChatInterface'
import PlayerControlBar from '../components/PlayerControlBar'
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
  const [chatVisible, setChatVisible] = useState(false) // Hidden by default
  const [showLanguagePicker, setShowLanguagePicker] = useState(false)
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
      setPageState('language_select')
    } else {
      setSelectedLanguage(languages[0] || 'de')
    }
  }, [tenantConfig])

  // Step 3: Language selected → start session
  const handleLanguageSelect = useCallback((language: string) => {
    setSelectedLanguage(language)
    setPageState('connecting')
    setShowLanguagePicker(false)
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
    setChatVisible(false)
    setPageState('preview')
  }, [session, tenantConfig])

  const {
    messages,
    isLoading,
    avatarSpeaking,
    streamingText,
    sendMessage,
  } = useConversation({
    sessionId: session?.sessionId || '',
    apiKey: tenantConfig?.api_key || '',
  })

  const primaryColor = tenantConfig?.branding?.primary_color || '#2563eb'
  const isActive = session?.status === 'active' || session?.status === 'creating'
  const hasMultipleLanguages = (tenantConfig?.supported_languages?.length || 0) > 1

  // Handle language change during active session
  const handleLanguageChangeRequest = useCallback(() => {
    if (hasMultipleLanguages) {
      setShowLanguagePicker(true)
    }
  }, [hasMultipleLanguages])

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

        {/* Main Layout — Player with optional Chat panel */}
        <div className={`grid gap-6 ${chatVisible && isActive ? 'grid-cols-1 lg:grid-cols-5' : 'grid-cols-1 max-w-2xl mx-auto'}`}>
          {/* Player Column (Avatar + Control Bar) */}
          <div className={`flex flex-col ${chatVisible && isActive ? 'lg:col-span-3' : ''}`}>
            {/* Avatar Video / Preview */}
            <div className="avatar-wrapper shadow-2xl">
              {session?.livekitUrl && session?.livekitToken ? (
                <AvatarPlayer
                  livekitUrl={session.livekitUrl}
                  livekitToken={session.livekitToken}
                />
              ) : (
                <>
                  {/* Preview Image */}
                  {tenantConfig?.avatar_preview_image ? (
                    <img
                      src={tenantConfig.avatar_preview_image}
                      alt={`${tenantConfig.name} Avatar`}
                      className="w-full h-full object-cover absolute inset-0"
                    />
                  ) : (
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

            {/* Player Control Bar — always visible when session is active */}
            {isActive && (
              <PlayerControlBar
                onTranscript={sendMessage}
                disabled={isLoading || avatarSpeaking}
                avatarSpeaking={avatarSpeaking}
                language={selectedLanguage || tenantConfig?.default_language || 'de'}
                chatVisible={chatVisible}
                onToggleChat={() => setChatVisible(v => !v)}
                onLanguageChange={handleLanguageChangeRequest}
                showLanguageButton={hasMultipleLanguages}
                primaryColor={primaryColor}
              />
            )}

            {/* Text input — always visible when session is active */}
            {isActive && (
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  const input = (e.target as HTMLFormElement).elements.namedItem('question') as HTMLInputElement
                  if (input.value.trim() && !isLoading) {
                    sendMessage(input.value.trim())
                    input.value = ''
                  }
                }}
                className="mt-3 flex items-center gap-3"
              >
                <input
                  name="question"
                  type="text"
                  placeholder="Stelle eine Frage..."
                  disabled={isLoading}
                  className="flex-1 px-4 py-3 rounded-xl border border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition-all disabled:bg-gray-50 bg-white shadow-sm"
                />
                <button
                  type="submit"
                  disabled={isLoading}
                  className="p-3 rounded-xl text-white hover:opacity-90 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors shadow-sm"
                  style={{ backgroundColor: primaryColor }}
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                </button>
              </form>
            )}
          </div>

          {/* Chat History Panel — only when toggled on */}
          {chatVisible && isActive && (
            <div className="lg:col-span-2 chat-panel-enter">
              <div className="bg-white rounded-xl shadow-lg border border-gray-200 h-full flex flex-col" style={{ minHeight: '400px', maxHeight: '600px' }}>
                {/* Chat header */}
                <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-700">Chat-Verlauf</span>
                  <span className="text-xs text-gray-400">{messages.length} Nachrichten</span>
                </div>

                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-4 space-y-3" style={{ minHeight: 0 }}>
                  {messages.length === 0 && (
                    <div className="text-center text-gray-400 py-8">
                      <p className="text-sm">Noch keine Nachrichten.</p>
                    </div>
                  )}

                  {messages.map((msg, i) => (
                    <div
                      key={i}
                      className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-[85%] rounded-2xl px-3 py-2 ${
                          msg.role === 'user'
                            ? 'bg-blue-600 text-white rounded-br-md'
                            : 'bg-gray-100 text-gray-800 rounded-bl-md'
                        }`}
                      >
                        <p className="text-sm leading-relaxed">{msg.content}</p>
                        <span className="text-xs opacity-60 mt-0.5 block">
                          {msg.timestamp.toLocaleTimeString('de-DE', {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </span>
                      </div>
                    </div>
                  ))}

                  {/* Streaming text preview */}
                  {streamingText && (
                    <div className="flex justify-start">
                      <div className="max-w-[85%] rounded-2xl rounded-bl-md px-3 py-2 bg-gray-100 text-gray-800">
                        <p className="text-sm leading-relaxed">{streamingText}</p>
                        <span className="inline-block w-2 h-4 bg-blue-500 animate-pulse ml-1" />
                      </div>
                    </div>
                  )}

                  {/* Loading indicator */}
                  {isLoading && !streamingText && (
                    <div className="flex justify-start">
                      <div className="rounded-2xl rounded-bl-md px-3 py-2 bg-gray-100">
                        <div className="animate-spin w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full" />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Language Picker Modal — initial selection */}
      {pageState === 'language_select' && tenantConfig && (
        <LanguagePicker
          supportedLanguages={tenantConfig.supported_languages}
          defaultLanguage={tenantConfig.default_language}
          onSelect={handleLanguageSelect}
          tenantName={tenantConfig.name}
        />
      )}

      {/* Language Picker Modal — change during session */}
      {showLanguagePicker && tenantConfig && (
        <LanguagePicker
          supportedLanguages={tenantConfig.supported_languages}
          defaultLanguage={selectedLanguage || tenantConfig.default_language}
          onSelect={(lang) => {
            setSelectedLanguage(lang)
            setShowLanguagePicker(false)
          }}
          tenantName={tenantConfig.name}
        />
      )}
    </div>
  )
}
