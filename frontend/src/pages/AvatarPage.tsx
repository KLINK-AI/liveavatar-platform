/**
 * Avatar Page — Public-facing page for end users.
 *
 * Accessed via /avatar/:tenantSlug
 * Loads tenant config (incl. API key), auto-starts avatar session.
 * NO manual API key entry needed — fully public.
 */

import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams } from 'react-router-dom'
import AvatarPlayer from '../components/AvatarPlayer'
import ChatInterface from '../components/ChatInterface'
import VoiceInput from '../components/VoiceInput'
import { useConversation } from '../hooks/useConversation'
import { tenantApi, sessionApi } from '../lib/api'

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
}

interface AvatarSession {
  sessionId: string
  livekitUrl: string | null
  livekitToken: string | null
  status: string
}

export default function AvatarPage() {
  const { tenantSlug } = useParams<{ tenantSlug: string }>()
  const [tenantConfig, setTenantConfig] = useState<TenantConfig | null>(null)
  const [session, setSession] = useState<AvatarSession | null>(null)
  const [isConnecting, setIsConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loadingTenant, setLoadingTenant] = useState(true)
  const keepAliveRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const sessionStartedRef = useRef(false)

  // Step 1: Load tenant config (includes API key)
  useEffect(() => {
    if (!tenantSlug) return
    setLoadingTenant(true)
    tenantApi.getBySlug(tenantSlug)
      .then((config: any) => {
        setTenantConfig(config)
        setLoadingTenant(false)
      })
      .catch(() => {
        setError(`Mandant "${tenantSlug}" nicht gefunden.`)
        setLoadingTenant(false)
      })
  }, [tenantSlug])

  // Step 2: Auto-start session when tenant is loaded
  const startSession = useCallback(async () => {
    if (!tenantConfig?.api_key || !tenantConfig.has_avatar) return
    if (sessionStartedRef.current) return
    sessionStartedRef.current = true
    setIsConnecting(true)
    setError(null)

    try {
      const data = await sessionApi.create(tenantConfig.api_key)
      const newSession: AvatarSession = {
        sessionId: data.session_id,
        livekitUrl: data.livekit_url,
        livekitToken: data.livekit_token,
        status: data.status,
      }
      setSession(newSession)

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
    } finally {
      setIsConnecting(false)
    }
  }, [tenantConfig])

  useEffect(() => {
    if (tenantConfig?.has_avatar && tenantConfig.api_key && !session && !isConnecting) {
      startSession()
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
    sessionStartedRef.current = false
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

  // Loading state
  if (loadingTenant) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin w-10 h-10 border-3 border-blue-600 border-t-transparent rounded-full mx-auto mb-4" />
          <p className="text-gray-500">Wird geladen...</p>
        </div>
      </div>
    )
  }

  // Error: tenant not found or no avatar
  if (error && !session) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-md text-center">
          <div className="text-4xl mb-4">&#9888;</div>
          <h1 className="text-xl font-bold mb-2 text-gray-900">Fehler</h1>
          <p className="text-gray-500 mb-6">{error}</p>
          <button
            onClick={() => { sessionStartedRef.current = false; startSession() }}
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

        {/* Main Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Avatar Video */}
          <div>
            {session?.livekitUrl && session?.livekitToken ? (
              <AvatarPlayer
                livekitUrl={session.livekitUrl}
                livekitToken={session.livekitToken}
              />
            ) : (
              <div className="aspect-video bg-gray-900 rounded-xl flex items-center justify-center text-white">
                {isConnecting ? (
                  <div className="text-center">
                    <div className="animate-spin w-10 h-10 border-3 border-white border-t-transparent rounded-full mx-auto mb-3" />
                    <p>Avatar wird geladen...</p>
                  </div>
                ) : error ? (
                  <div className="text-center text-red-400">
                    <p>Fehler: {error}</p>
                    <button
                      onClick={() => { sessionStartedRef.current = false; startSession() }}
                      className="mt-3 px-4 py-2 bg-white/10 rounded-lg hover:bg-white/20"
                    >
                      Erneut versuchen
                    </button>
                  </div>
                ) : (
                  <div className="text-center">
                    <div className="animate-spin w-10 h-10 border-3 border-white border-t-transparent rounded-full mx-auto mb-3" />
                    <p className="text-gray-400">Avatar wird vorbereitet...</p>
                  </div>
                )}
              </div>
            )}

            {/* Voice Input */}
            {isActive && (
              <div className="mt-4">
                <VoiceInput
                  onTranscript={sendMessage}
                  disabled={isLoading}
                />
              </div>
            )}
          </div>

          {/* Chat Interface */}
          <div>
            <ChatInterface
              messages={messages}
              streamingText={streamingText}
              isLoading={isLoading}
              onSendMessage={sendMessage}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
