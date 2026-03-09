/**
 * Embeddable Avatar Widget
 *
 * Self-contained component that can be embedded on any website
 * via iframe or web component. Includes avatar, chat, and voice input.
 */

import { useState } from 'react'
import { MessageCircle, X, Minimize2, Maximize2 } from 'lucide-react'
import AvatarPlayer from './AvatarPlayer'
import ChatInterface from './ChatInterface'
import VoiceInput from './VoiceInput'
import { useAvatarSession } from '../hooks/useAvatarSession'
import { useConversation } from '../hooks/useConversation'

interface EmbedWidgetProps {
  apiKey: string
  tenantSlug: string
  avatarId?: string
  branding?: {
    primaryColor?: string
    logo_url?: string
    title?: string
  }
  position?: 'bottom-right' | 'bottom-left' | 'center'
  startOpen?: boolean
}

export default function EmbedWidget({
  apiKey,
  tenantSlug,
  avatarId,
  branding,
  position = 'bottom-right',
  startOpen = false,
}: EmbedWidgetProps) {
  const [isOpen, setIsOpen] = useState(startOpen)
  const [isMinimized, setIsMinimized] = useState(false)

  const {
    session,
    isConnecting,
    error: sessionError,
    startSession,
    stopSession,
    isActive,
  } = useAvatarSession({ apiKey, avatarId })

  const {
    messages,
    isLoading,
    streamingText,
    sendMessage,
  } = useConversation({
    sessionId: session?.sessionId || '',
    apiKey,
  })

  const primaryColor = branding?.primaryColor || '#2563eb'

  const handleOpen = async () => {
    setIsOpen(true)
    if (!session) {
      try {
        await startSession()
      } catch (e) {
        console.error('Failed to start:', e)
      }
    }
  }

  const handleClose = async () => {
    setIsOpen(false)
    await stopSession()
  }

  const positionClasses = {
    'bottom-right': 'fixed bottom-6 right-6',
    'bottom-left': 'fixed bottom-6 left-6',
    'center': 'fixed inset-0 flex items-center justify-center',
  }

  // Floating button (when closed)
  if (!isOpen) {
    return (
      <button
        onClick={handleOpen}
        className={`${positionClasses[position]} z-50 p-4 rounded-full shadow-xl hover:scale-110 transition-transform`}
        style={{ backgroundColor: primaryColor }}
      >
        <MessageCircle className="w-7 h-7 text-white" />
      </button>
    )
  }

  // Widget (when open)
  return (
    <div
      className={`${
        position === 'center' ? positionClasses[position] : positionClasses[position]
      } z-50`}
    >
      <div
        className={`bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden transition-all ${
          isMinimized ? 'w-80 h-16' : 'w-[420px] max-h-[700px]'
        }`}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-3 text-white"
          style={{ backgroundColor: primaryColor }}
        >
          <div className="flex items-center gap-2">
            {branding?.logo_url && (
              <img src={branding.logo_url} alt="" className="w-6 h-6 rounded" />
            )}
            <span className="font-medium text-sm">
              {branding?.title || 'Avatar Assistent'}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setIsMinimized(!isMinimized)}
              className="p-1 hover:bg-white/20 rounded"
            >
              {isMinimized ? (
                <Maximize2 className="w-4 h-4" />
              ) : (
                <Minimize2 className="w-4 h-4" />
              )}
            </button>
            <button
              onClick={handleClose}
              className="p-1 hover:bg-white/20 rounded"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {!isMinimized && (
          <div className="flex flex-col">
            {/* Avatar Video */}
            {session?.livekitUrl && session?.livekitToken && (
              <div className="aspect-video bg-gray-900">
                <AvatarPlayer
                  livekitUrl={session.livekitUrl}
                  livekitToken={session.livekitToken}
                />
              </div>
            )}

            {/* Loading / Error states */}
            {isConnecting && (
              <div className="p-8 text-center text-gray-500">
                <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-3" />
                <p>Avatar wird geladen...</p>
              </div>
            )}

            {sessionError && (
              <div className="p-4 bg-red-50 text-red-600 text-sm">
                Fehler: {sessionError}
              </div>
            )}

            {/* Chat */}
            {isActive && (
              <>
                <ChatInterface
                  messages={messages}
                  streamingText={streamingText}
                  isLoading={isLoading}
                  onSendMessage={sendMessage}
                />

                {/* Voice Input */}
                <div className="px-4 pb-4">
                  <VoiceInput
                    onTranscript={sendMessage}
                    disabled={isLoading}
                  />
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
