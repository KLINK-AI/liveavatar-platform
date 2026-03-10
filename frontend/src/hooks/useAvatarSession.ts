/**
 * React Hook for managing LiveAvatar sessions.
 *
 * Handles the full session lifecycle:
 * 1. Create session via backend API
 * 2. Connect to LiveKit room
 * 3. Keep-alive management
 * 4. Clean shutdown
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import { sessionApi } from '../lib/api'

interface AvatarSession {
  sessionId: string
  heygenSessionId: string | null
  livekitUrl: string | null
  livekitToken: string | null
  status: string
}

interface UseAvatarSessionOptions {
  apiKey: string
  avatarId?: string
  keepAliveInterval?: number // ms, default 60000
}

export function useAvatarSession(options: UseAvatarSessionOptions) {
  const { apiKey, avatarId, keepAliveInterval = 60000 } = options

  const [session, setSession] = useState<AvatarSession | null>(null)
  const [isConnecting, setIsConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const keepAliveRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const startSession = useCallback(async () => {
    setIsConnecting(true)
    setError(null)

    try {
      const data = await sessionApi.create(apiKey, { avatarId })
      const newSession: AvatarSession = {
        sessionId: data.session_id,
        heygenSessionId: data.heygen_session_id,
        livekitUrl: data.livekit_url,
        livekitToken: data.livekit_token,
        status: data.status,
      }
      setSession(newSession)

      // Start keep-alive interval
      keepAliveRef.current = setInterval(async () => {
        try {
          await sessionApi.keepAlive(newSession.sessionId, apiKey)
        } catch (e) {
          console.warn('Keep-alive failed:', e)
        }
      }, keepAliveInterval)

      return newSession
    } catch (e: any) {
      setError(e.message || 'Failed to start session')
      throw e
    } finally {
      setIsConnecting(false)
    }
  }, [apiKey, avatarId, keepAliveInterval])

  const stopSession = useCallback(async () => {
    if (!session) return

    // Clear keep-alive
    if (keepAliveRef.current) {
      clearInterval(keepAliveRef.current)
      keepAliveRef.current = null
    }

    try {
      await sessionApi.stop(session.sessionId, apiKey)
    } catch (e) {
      console.warn('Session stop error:', e)
    }

    setSession(null)
  }, [session, apiKey])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (keepAliveRef.current) {
        clearInterval(keepAliveRef.current)
      }
    }
  }, [])

  return {
    session,
    isConnecting,
    error,
    startSession,
    stopSession,
    isActive: session?.status === 'active',
  }
}
