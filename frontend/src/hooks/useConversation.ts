/**
 * React Hook for managing conversations with the avatar.
 *
 * Supports both:
 * - REST mode (simple request/response)
 * - WebSocket mode (streaming tokens for real-time display)
 */

import { useState, useCallback, useRef } from 'react'
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
  const socketRef = useRef<ReturnType<typeof createConversationSocket> | null>(null)

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
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: response.response,
          timestamp: new Date(),
        }])
      } catch (e: any) {
        console.error('Message error:', e)
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: 'Entschuldigung, es gab einen Fehler bei der Verarbeitung.',
          timestamp: new Date(),
        }])
      } finally {
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
    streamingText,
    sendMessage,
    clearMessages,
  }
}
