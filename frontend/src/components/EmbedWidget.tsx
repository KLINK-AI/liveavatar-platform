/**
 * Embeddable Avatar Widget — Bubble + Modal
 *
 * Floating chat-bubble button that opens a modal overlay with
 * the avatar player, control bar, and chat.
 *
 * Can be loaded via a <script> tag that creates this component
 * on the customer's website.
 *
 * v2.5: Uses PlayerControlBar, chat hidden by default
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import { MessageCircle, X, Minimize2, Maximize2 } from 'lucide-react'
import AvatarPlayer from './AvatarPlayer'
import PlayerControlBar from './PlayerControlBar'
import { useConversation } from '../hooks/useConversation'
import { tenantApi, sessionApi } from '../lib/api'

interface EmbedWidgetProps {
  tenantSlug: string
  position?: 'bottom-right' | 'bottom-left'
  primaryColor?: string
}

interface TenantConfig {
  name: string
  slug: string
  branding: { primary_color?: string; logo_url?: string } | null
  has_avatar: boolean
  api_key: string
  avatar_preview_image: string | null
  supported_languages: string[]
  default_language: string
}

interface AvatarSession {
  sessionId: string
  livekitUrl: string | null
  livekitToken: string | null
  status: string
}

export default function EmbedWidget({
  tenantSlug,
  position = 'bottom-right',
  primaryColor: colorOverride,
}: EmbedWidgetProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [isMinimized, setIsMinimized] = useState(false)
  const [tenantConfig, setTenantConfig] = useState<TenantConfig | null>(null)
  const [session, setSession] = useState<AvatarSession | null>(null)
  const [isConnecting, setIsConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [chatVisible, setChatVisible] = useState(false)
  const keepAliveRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const sessionStartedRef = useRef(false)

  const primaryColor = colorOverride || tenantConfig?.branding?.primary_color || '#2563eb'

  // Load tenant config on first open
  const loadTenant = useCallback(async () => {
    if (tenantConfig) return tenantConfig
    try {
      const config = await tenantApi.getBySlug(tenantSlug)
      setTenantConfig(config as any)
      return config
    } catch (e) {
      setError('Widget konnte nicht geladen werden.')
      return null
    }
  }, [tenantSlug, tenantConfig])

  const startSession = useCallback(async () => {
    const config = await loadTenant()
    if (!config || !(config as any).api_key || !(config as any).has_avatar) return
    if (sessionStartedRef.current) return
    sessionStartedRef.current = true
    setIsConnecting(true)
    setError(null)

    try {
      const apiKey = (config as any).api_key
      const language = (config as any).default_language || 'de'
      const data = await sessionApi.create(apiKey, { language })
      const newSession: AvatarSession = {
        sessionId: data.session_id,
        livekitUrl: data.livekit_url,
        livekitToken: data.livekit_token,
        status: data.status,
      }
      setSession(newSession)
      setIsConnecting(false)

      keepAliveRef.current = setInterval(async () => {
        try { await sessionApi.keepAlive(newSession.sessionId, apiKey) } catch (_) {}
      }, 60000)
    } catch (e: any) {
      sessionStartedRef.current = false
      setIsConnecting(false)
      setError(e.message || 'Session-Fehler')
    }
  }, [loadTenant])

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
  }, [session, tenantConfig])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (keepAliveRef.current) clearInterval(keepAliveRef.current)
    }
  }, [])

  const handleOpen = async () => {
    setIsOpen(true)
    if (!session) {
      await startSession()
    }
  }

  const handleClose = async () => {
    setIsOpen(false)
    setIsMinimized(false)
    await stopSession()
  }

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

  const isActive = session?.status === 'active' || session?.status === 'creating'
  const positionClass = position === 'bottom-left' ? 'fixed bottom-6 left-6' : 'fixed bottom-6 right-6'

  // Floating button (when closed)
  if (!isOpen) {
    return (
      <button
        onClick={handleOpen}
        className={`${positionClass} z-50 p-4 rounded-full shadow-xl hover:scale-110 transition-transform`}
        style={{ backgroundColor: primaryColor }}
      >
        <MessageCircle className="w-7 h-7 text-white" />
      </button>
    )
  }

  // Widget modal (when open)
  return (
    <div className={`${positionClass} z-50`}>
      <div
        className={`bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden transition-all ${
          isMinimized ? 'w-80 h-14' : 'w-[400px]'
        }`}
        style={{ maxHeight: isMinimized ? '56px' : '85vh' }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-2.5 text-white"
          style={{ backgroundColor: primaryColor }}
        >
          <div className="flex items-center gap-2">
            {tenantConfig?.branding?.logo_url && (
              <img src={tenantConfig.branding.logo_url} alt="" className="w-5 h-5 rounded" />
            )}
            <span className="font-medium text-sm">
              {tenantConfig?.name || 'Avatar Assistent'}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <button onClick={() => setIsMinimized(!isMinimized)} className="p-1 hover:bg-white/20 rounded">
              {isMinimized ? <Maximize2 className="w-4 h-4" /> : <Minimize2 className="w-4 h-4" />}
            </button>
            <button onClick={handleClose} className="p-1 hover:bg-white/20 rounded">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {!isMinimized && (
          <div className="flex flex-col">
            {/* Avatar Video */}
            <div className="relative aspect-video bg-gray-900">
              {session?.livekitUrl && session?.livekitToken ? (
                <AvatarPlayer
                  livekitUrl={session.livekitUrl}
                  livekitToken={session.livekitToken}
                />
              ) : isConnecting ? (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center text-white">
                    <div className="animate-spin w-8 h-8 border-2 border-white border-t-transparent rounded-full mx-auto mb-2" />
                    <p className="text-sm">Wird geladen...</p>
                  </div>
                </div>
              ) : (
                tenantConfig?.avatar_preview_image && (
                  <img
                    src={tenantConfig.avatar_preview_image}
                    alt=""
                    className="w-full h-full object-cover"
                  />
                )
              )}

              {/* Chat overlay in modal */}
              {chatVisible && isActive && (
                <div className="absolute right-0 top-0 bottom-0 w-56 bg-white/95 backdrop-blur-sm shadow-lg flex flex-col">
                  <div className="px-2 py-1.5 border-b border-gray-200 text-xs font-medium text-gray-600">
                    Chat ({messages.length})
                  </div>
                  <div className="flex-1 overflow-y-auto p-2 space-y-1.5" style={{ minHeight: 0 }}>
                    {messages.map((msg, i) => (
                      <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[90%] rounded-lg px-2 py-1 ${
                          msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-800'
                        }`}>
                          <p className="text-xs leading-relaxed">{msg.content}</p>
                        </div>
                      </div>
                    ))}
                    {streamingText && (
                      <div className="flex justify-start">
                        <div className="max-w-[90%] rounded-lg px-2 py-1 bg-gray-100 text-gray-800">
                          <p className="text-xs leading-relaxed">{streamingText}</p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {error && (
              <div className="px-3 py-2 bg-red-50 text-red-600 text-xs">{error}</div>
            )}

            {/* Control bar + input */}
            {isActive && (
              <>
                <PlayerControlBar
                  onTranscript={sendMessage}
                  disabled={isLoading || avatarSpeaking}
                  avatarSpeaking={avatarSpeaking}
                  language={tenantConfig?.default_language || 'de'}
                  chatVisible={chatVisible}
                  onToggleChat={() => setChatVisible(v => !v)}
                  showLanguageButton={false}
                  primaryColor={primaryColor}
                />

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
                    className="flex-1 px-3 py-2 rounded-lg border border-gray-300 text-sm focus:border-blue-500 outline-none disabled:bg-gray-50"
                  />
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="p-2 rounded-lg text-white disabled:bg-gray-300 transition-colors"
                    style={{ backgroundColor: primaryColor }}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                    </svg>
                  </button>
                </form>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
