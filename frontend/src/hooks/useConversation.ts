/**
 * React Hook for managing conversations with the avatar.
 *
 * Supports both:
 * - REST mode (simple request/response)
 * - WebSocket mode (streaming tokens for real-time display)
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import { conversationApi, createConversationSocket } from '../lib/api'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  isStreaming?: boolean
}

interface UseConversationOptions {
  sessionId: string
  apiKey: string
  useStreaming?: boolean
}

export function useConversation(options: UseConversationOptions) {
  const { sessionId, apiKey, useStreaming = false } = options

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [streamingText, setStreamingText] = useState('')
  const [avatarSpeaking, setAvatarSpeaking] = useState(false)
  const socketRef = useRef<ReturnType<typeof createConversationSocket> | null>(null)
  const speakingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Cleanup speaking timer on unmount
  useEffect(() => {
    return () => {
      if (speakingTimerRef.current) clearTimeout(speakingTimerRef.current)
    }
  }, [])

  /**
   * Estimate how long the avatar will speak a given text.
   * German speech: ~150 wpm ≈ 15 chars/sec → 67ms per char.
   * We use 60ms/char + 500ms buffer, clamped to [2s, 15s].
   */
  const estimateSpeakingDuration = (text: string): number => {
    const ms = text.length * 60 + 500
    return Math.max(2000, Math.min(ms, 15000))
  }

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim()) return

    // Add user message
    const userMessage: ChatMessage = {
      role: 'user',
      content: text,
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)

    if (useStreaming) {
      // WebSocket streaming mode
      setStreamingText('')

      const socket = createConversationSocket(
        sessionId,
        apiKey,
        // onToken
        (token) => {
          setStreamingText(prev => prev + token)
        },
        // onAvatarSent
        (_sentence) => {
          // Avatar is speaking this sentence
        },
        // onDone
        (fullResponse) => {
          setStreamingText('')
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: fullResponse,
            timestamp: new Date(),
          }])
          setIsLoading(false)
        },
        // onError
        (error) => {
          console.error('Stream error:', error)
          setIsLoading(false)
        },
      )

      socketRef.current = socket
      socket.send(text)
    } else {
      // REST mode
      try {
        const response = await conversationApi.sendMessage(sessionId, text, apiKey)
        const responseText = response.response || ''
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: responseText,
          timestamp: new Date(),
        }])

        // Avatar is now speaking the response audio via LiveKit.
        // Lock the mic for the estimated speaking duration to prevent
        // the avatar's audio from being picked up by the user's microphone.
        setIsLoading(false)
        setAvatarSpeaking(true)
        if (speakingTimerRef.current) clearTimeout(speakingTimerRef.current)
        speakingTimerRef.current = setTimeout(() => {
          setAvatarSpeaking(false)
        }, estimateSpeakingDuration(responseText))
      } catch (e: any) {
        console.error('Message error:', e)
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: 'Entschuldigung, es gab einen Fehler bei der Verarbeitung.',
          timestamp: new Date(),
        }])
        setIsLoading(false)
      }
    }
  }, [sessionId, apiKey, useStreaming])

  const clearMessages = useCallback(() => {
    setMessages([])
  }, [])

  return {
    messages,
    isLoading,
    avatarSpeaking,
    streamingText,
    sendMessage,
    clearMessages,
  }
}
