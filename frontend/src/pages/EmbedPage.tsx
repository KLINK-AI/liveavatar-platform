/**
 * Embed Page — Lightweight avatar player for iframe embedding.
 *
 * Accessed via /embed/:tenantSlug
 *
 * This is a standalone, borderless page designed to be embedded
 * in customer websites via iframe. It contains:
 * - Avatar video player (full-width)
 * - Player control bar (mic, language, chat toggle)
 * - Text input field
 * - Collapsible chat overlay
 *
 * Usage:
 *   <iframe src="https://liveavatar.klink-io.cloud/embed/buettelborn"
 *           width="600" height="400" frameborder="0"
 *           allow="microphone; camera" />
 *
 * Query params:
 *   ?autostart=1   — skip preview, start session immediately
 *   ?lang=de       — pre-select language
 *   ?chat=1        — show chat by default
 */

import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import AvatarPlayer from '../components/AvatarPlayer'
import PlayerControlBar from '../components/PlayerControlBar'
import { useConversation } from '../hooks/useConversation'
import { tenantApi, sessionApi } from '../lib/api'
import { Play, Loader2 } from 'lucide-react'

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

type EmbedState = 'loading' | 'preview' | 'connecting' | 'active' | 'error'

export default function EmbedPage() {
  const { tenantSlug } = useParams<{ tenantSlug: string }>()
  const [searchParams] = useSearchParams()
  const [tenantConfig, setTenantConfig] = useState<TenantConfig | null>(null)
  const [session, setSession] = useState<AvatarSession | null>(null)
  const [state, setState] = useState<EmbedState>('loading')
  const [selectedLanguage, setSelectedLanguage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [chatVisible, setChatVisible] = useState(searchParams.get('chat') === '1')
  const keepAliveRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const sessionStartedRef = useRef(false)

  const autostart = searchParams.get('autostart') === '1'
  const langParam = searchParams.get('lang')

  // Load tenant config
  useEffect(() => {
    if (!tenantSlug) return
    tenantApi.getBySlug(tenantSlug)
      .then((config: any) => {
        setTenantConfig(config)
        const lang = langParam || config.default_language || 'de'
        setSelectedLanguage(lang)

        if (autostart) {
          setState('connecting')
        } else {
          setState('preview')
        }
      })
      .catch(() => {
        setError(`Tenant "${tenantSlug}" nicht gefunden.`)
        setState('error')
      })
  }, [tenantSlug])

  // Auto-start if requested
  useEffect(() => {
    if (autostart && selectedLanguage && tenantConfig && !session && state === 'connecting') {
      startSession(selectedLanguage)
    }
  }, [autostart, selectedLanguage, tenantConfig, state])

  const startSession = useCallback(async (language: string) => {
    if (!tenantConfig?.api_key || !tenantConfig.has_avatar) return
    if (sessionStartedRef.current) return
    sessionStartedRef.current = true
    setError(null)
    setState('connecting')

    try {
      const data = await sessionApi.create(tenantConfig.api_key, { language })
      const newSession: AvatarSession = {
        sessionId: data.session_id,
        livekitUrl: data.livekit_url,
        livekitToken: data.livekit_token,
        status: data.status,
      }
      setSession(newSession)
      setState('active')

      // Notify parent widget that session is active
      if (window.parent !== window) {
        window.parent.postMessage('liveavatar-session-started', '*')
      }

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
      setState('error')
    }
  }, [tenantConfig])

  // Stop session handler (can be called from widget via postMessage)
  const stopSession = useCallback(async () => {
    if (keepAliveRef.current) {
      clearInterval(keepAliveRef.current)
      keepAliveRef.current = null
    }
    if (session && tenantConfig) {
      try { await sessionApi.stop(session.sessionId, tenantConfig.api_key) } catch (_) {}
    }
    setSession(null)
    sessionStartedRef.current = false
    setChatVisible(false)
    setState('preview')
    // Notify parent widget
    if (window.parent !== window) {
      window.parent.postMessage('liveavatar-session-ended', '*')
    }
  }, [session, tenantConfig])

  // Listen for messages from parent widget
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (event.data === 'liveavatar-end-session') {
        stopSession()
      }
    }
    window.addEventListener('message', handler)
    return () => window.removeEventListener('message', handler)
  }, [stopSession])

  // Cleanup
  useEffect(() => {
    return () => {
      if (keepAliveRef.current) clearInterval(keepAliveRef.current)
    }
  }, [])

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

  // --- RENDER ---

  if (state === 'loading') {
    return (
      <div className="embed-player items-center justify-center">
        <div className="animate-spin w-8 h-8 border-2 border-white border-t-transparent rounded-full" />
      </div>
    )
  }

  if (state === 'error') {
    return (
      <div className="embed-player items-center justify-center text-white text-center p-4">
        <p className="text-sm opacity-70">{error}</p>
        <button
          onClick={() => {
            sessionStartedRef.current = false
            setState('preview')
            setError(null)
          }}
          className="mt-3 px-4 py-2 rounded-lg text-sm text-white"
          style={{ backgroundColor: primaryColor }}
        >
          Erneut versuchen
        </button>
      </div>
    )
  }

  return (
    <div className="embed-player">
      {/* Avatar area — fills available space */}
      <div className="avatar-wrapper flex-1" style={{ aspectRatio: 'auto' }}>
        {session?.livekitUrl && session?.livekitToken ? (
          <AvatarPlayer
            livekitUrl={session.livekitUrl}
            livekitToken={session.livekitToken}
          />
        ) : (
          <>
            {tenantConfig?.avatar_preview_image ? (
              <img
                src={tenantConfig.avatar_preview_image}
                alt={tenantConfig.name}
                className="w-full h-full object-cover absolute inset-0"
              />
            ) : (
              <div className="w-full h-full bg-gradient-to-br from-gray-800 to-gray-900 absolute inset-0" />
            )}

            {state === 'preview' && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                <button
                  onClick={() => {
                    setState('connecting')
                    startSession(selectedLanguage || 'de')
                  }}
                  className="flex items-center gap-2 px-6 py-3 rounded-xl text-white font-medium shadow-lg transition-all hover:scale-105 active:scale-95"
                  style={{ backgroundColor: primaryColor }}
                >
                  <Play className="w-5 h-5" />
                  Starten
                </button>
              </div>
            )}

            {state === 'connecting' && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/50">
                <div className="text-center text-white">
                  <Loader2 className="w-8 h-8 animate-spin mx-auto mb-2" />
                  <p className="text-sm">Wird geladen...</p>
                </div>
              </div>
            )}
          </>
        )}

        {/* Chat overlay (slides in from right) */}
        {chatVisible && isActive && (
          <div className="absolute right-0 top-0 bottom-0 w-72 bg-white/95 backdrop-blur-sm shadow-lg flex flex-col chat-panel-enter">
            <div className="px-3 py-2 border-b border-gray-200 text-xs font-medium text-gray-600">
              Chat-Verlauf ({messages.length})
            </div>
            <div className="flex-1 overflow-y-auto p-3 space-y-2" style={{ minHeight: 0 }}>
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[90%] rounded-xl px-2.5 py-1.5 ${
                      msg.role === 'user'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    <p className="text-xs leading-relaxed">{msg.content}</p>
                  </div>
                </div>
              ))}

              {streamingText && (
                <div className="flex justify-start">
                  <div className="max-w-[90%] rounded-xl px-2.5 py-1.5 bg-gray-100 text-gray-800">
                    <p className="text-xs leading-relaxed">{streamingText}</p>
                    <span className="inline-block w-1.5 h-3 bg-blue-500 animate-pulse ml-0.5" />
                  </div>
                </div>
              )}

              {isLoading && !streamingText && (
                <div className="flex justify-start">
                  <div className="rounded-xl px-2.5 py-1.5 bg-gray-100">
                    <Loader2 className="w-3 h-3 animate-spin text-gray-400" />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Control bar + input */}
      {isActive && (
        <div className="bg-[#1a1a1a] border-t border-gray-700">
          <PlayerControlBar
            onTranscript={sendMessage}
            disabled={isLoading || avatarSpeaking}
            avatarSpeaking={avatarSpeaking}
            language={selectedLanguage || tenantConfig?.default_language || 'de'}
            chatVisible={chatVisible}
            onToggleChat={() => setChatVisible(v => !v)}
            showLanguageButton={(tenantConfig?.supported_languages?.length || 0) > 1}
            primaryColor={primaryColor}
          />

          {/* Compact text input */}
          <form
            onSubmit={(e) => {
              e.preventDefault()
              const input = (e.target as HTMLFormElement).elements.namedItem('question') as HTMLInputElement
              if (input.value.trim() && !isLoading) {
                sendMessage(input.value.trim())
                input.value = ''
              }
            }}
            className="flex items-center gap-2 px-3 pb-3"
          >
            <input
              name="question"
              type="text"
              placeholder="Frage eingeben..."
              disabled={isLoading}
              className="flex-1 px-3 py-2 rounded-lg border border-gray-600 bg-gray-800 text-white text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none disabled:opacity-50 placeholder-gray-500"
            />
            <button
              type="submit"
              disabled={isLoading}
              className="p-2 rounded-lg text-white disabled:opacity-50 transition-colors"
              style={{ backgroundColor: primaryColor }}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </form>
        </div>
      )}
    </div>
  )
}
