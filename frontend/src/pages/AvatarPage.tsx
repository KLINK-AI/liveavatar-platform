/**
 * Avatar Page — Public-facing page for end users.
 *
 * Accessed via /avatar/:tenantSlug
 * Loads tenant branding, starts avatar session, provides chat interface.
 */

import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import AvatarPlayer from '../components/AvatarPlayer'
import ChatInterface from '../components/ChatInterface'
import VoiceInput from '../components/VoiceInput'
import { useAvatarSession } from '../hooks/useAvatarSession'
import { useConversation } from '../hooks/useConversation'
import { tenantApi } from '../lib/api'

interface TenantConfig {
  name: string
  slug: string
  branding: {
    primary_color?: string
    logo_url?: string
    background_color?: string
  } | null
  has_avatar: boolean
}

export default function AvatarPage() {
  const { tenantSlug } = useParams<{ tenantSlug: string }>()
  const [tenantConfig, setTenantConfig] = useState<TenantConfig | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [isReady, setIsReady] = useState(false)

  // Load tenant config
  useEffect(() => {
    if (tenantSlug) {
      tenantApi.getBySlug(tenantSlug)
        .then(setTenantConfig)
        .catch(console.error)
    }
  }, [tenantSlug])

  // For now, API key must be provided (in production: embedded in widget config)
  const handleStart = () => {
    if (apiKey) setIsReady(true)
  }

  const {
    session,
    isConnecting,
    error: sessionError,
    startSession,
    stopSession,
    isActive,
  } = useAvatarSession({ apiKey })

  const {
    messages,
    isLoading,
    streamingText,
    sendMessage,
  } = useConversation({
    sessionId: session?.sessionId || '',
    apiKey,
  })

  // Auto-start session when ready
  useEffect(() => {
    if (isReady && !session && !isConnecting) {
      startSession()
    }
  }, [isReady])

  const primaryColor = tenantConfig?.branding?.primary_color || '#2563eb'

  // API Key input (for testing — in production this comes from embed config)
  if (!isReady) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-md">
          <h1 className="text-2xl font-bold mb-2">
            {tenantConfig?.name || 'Avatar Assistent'}
          </h1>
          <p className="text-gray-500 mb-6">
            Geben Sie Ihren API-Key ein, um den Avatar zu starten.
          </p>
          <input
            type="text"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="API Key"
            className="w-full px-4 py-3 rounded-xl border border-gray-300 mb-4 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none"
          />
          <button
            onClick={handleStart}
            disabled={!apiKey}
            className="w-full py-3 rounded-xl text-white font-medium disabled:opacity-50"
            style={{ backgroundColor: primaryColor }}
          >
            Avatar starten
          </button>
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
          {isActive && (
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
                ) : sessionError ? (
                  <div className="text-center text-red-400">
                    <p>Fehler: {sessionError}</p>
                    <button
                      onClick={() => startSession()}
                      className="mt-3 px-4 py-2 bg-white/10 rounded-lg hover:bg-white/20"
                    >
                      Erneut versuchen
                    </button>
                  </div>
                ) : (
                  <p className="text-gray-400">Avatar wird vorbereitet...</p>
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
