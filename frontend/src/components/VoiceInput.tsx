/**
 * Voice Input Component
 *
 * Allows users to speak their questions via microphone.
 * Uses the Web Speech API for speech-to-text, then sends
 * the transcribed text through the conversation pipeline.
 *
 * Accepts short language codes ('de', 'en', etc.) and maps
 * them to BCP-47 tags ('de-DE', 'en-US') for the Web Speech API.
 */

import { useState, useRef, useCallback, useMemo, useEffect } from 'react'
import { Mic, MicOff, Loader2, Volume2 } from 'lucide-react'

/** Map short language codes to BCP-47 tags for Web Speech API */
const LANGUAGE_MAP: Record<string, string> = {
  de: 'de-DE',
  en: 'en-US',
  fr: 'fr-FR',
  es: 'es-ES',
  it: 'it-IT',
  nl: 'nl-NL',
}

interface VoiceInputProps {
  onTranscript: (text: string) => void
  disabled?: boolean
  language?: string
}

export default function VoiceInput({
  onTranscript,
  disabled = false,
  language = 'de',
}: VoiceInputProps) {
  const [isListening, setIsListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const recognitionRef = useRef<any>(null)
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const latestTranscriptRef = useRef<string>('')
  // Guard flag: prevents onTranscript from being called more than once
  // per recognition session. The race condition between the silence timer,
  // onend handler, and manual stop could otherwise fire onTranscript 2-3x.
  const hasSentRef = useRef<boolean>(false)

  /** How long to wait after last speech before sending (ms) */
  const SILENCE_TIMEOUT = 2000

  // Resolve short code ('de') to BCP-47 ('de-DE') for Web Speech API
  const speechLang = useMemo(
    () => LANGUAGE_MAP[language] || language,
    [language],
  )

  // Cleanup silence timer on unmount
  useEffect(() => {
    return () => {
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current)
    }
  }, [])

  const startListening = useCallback(() => {
    // Check browser support
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition

    if (!SpeechRecognition) {
      alert('Spracherkennung wird in diesem Browser nicht unterstützt.')
      return
    }

    const recognition = new SpeechRecognition()
    recognition.lang = speechLang
    recognition.continuous = true       // Keep listening (don't auto-stop on pause)
    recognition.interimResults = true

    recognition.onstart = () => {
      setIsListening(true)
      setTranscript('')
      latestTranscriptRef.current = ''
      hasSentRef.current = false  // Reset guard for new session
    }

    recognition.onresult = (event: any) => {
      // Combine all results into one transcript
      let fullTranscript = ''
      for (let i = 0; i < event.results.length; i++) {
        fullTranscript += event.results[i][0].transcript
      }

      setTranscript(fullTranscript)
      latestTranscriptRef.current = fullTranscript

      // Reset silence timer on every new speech input.
      // After 2s of silence, we consider the user done speaking.
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current)
      silenceTimerRef.current = setTimeout(() => {
        if (hasSentRef.current) return  // Already sent — skip
        const finalText = latestTranscriptRef.current.trim()
        if (finalText) {
          hasSentRef.current = true
          onTranscript(finalText)
        }
        if (recognitionRef.current) {
          try { recognitionRef.current.stop() } catch (_) {}
        }
        setIsListening(false)
        setTranscript('')
        latestTranscriptRef.current = ''
      }, SILENCE_TIMEOUT)
    }

    recognition.onerror = (event: any) => {
      console.error('Speech recognition error:', event.error)
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current)
      setIsListening(false)
      setTranscript('')
    }

    recognition.onend = () => {
      // With continuous=true, the browser may still auto-stop.
      // If we have pending text and it hasn't been sent yet, send it now.
      if (!hasSentRef.current && latestTranscriptRef.current.trim()) {
        if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current)
        hasSentRef.current = true
        onTranscript(latestTranscriptRef.current.trim())
        latestTranscriptRef.current = ''
      }
      setIsListening(false)
      setTranscript('')
    }

    recognitionRef.current = recognition
    recognition.start()
  }, [speechLang, onTranscript])

  const stopListening = useCallback(() => {
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current)
    // When user manually stops, send whatever was said so far (only once)
    if (!hasSentRef.current) {
      const finalText = latestTranscriptRef.current.trim()
      if (finalText) {
        hasSentRef.current = true
        onTranscript(finalText)
      }
    }
    if (recognitionRef.current) {
      try { recognitionRef.current.stop() } catch (_) {}
    }
    setIsListening(false)
    setTranscript('')
    latestTranscriptRef.current = ''
  }, [onTranscript])

  // Force-stop listening immediately when disabled becomes true
  // (e.g., when avatar starts speaking or a new response is loading)
  useEffect(() => {
    if (disabled && isListening) {
      stopListening()
      setTranscript('')
    }
  }, [disabled, isListening, stopListening])

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={isListening ? stopListening : startListening}
        disabled={disabled}
        className={`p-4 rounded-full transition-all ${
          isListening
            ? 'bg-red-500 text-white animate-pulse shadow-lg shadow-red-200'
            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
        } disabled:opacity-50 disabled:cursor-not-allowed`}
        title={isListening ? 'Aufnahme stoppen' : 'Spracheingabe starten'}
      >
        {isListening ? (
          <MicOff className="w-6 h-6" />
        ) : (
          <Mic className="w-6 h-6" />
        )}
      </button>

      {/* Live transcript preview */}
      {transcript && (
        <div className="flex-1 px-4 py-2 bg-blue-50 rounded-lg text-sm text-blue-800 italic">
          {transcript}
          <Loader2 className="inline w-3 h-3 ml-2 animate-spin" />
        </div>
      )}

      {!isListening && !transcript && disabled && (
        <span className="flex items-center gap-2 text-sm text-amber-500">
          <Volume2 className="w-4 h-4 animate-pulse" />
          Avatar spricht...
        </span>
      )}

      {!isListening && !transcript && !disabled && (
        <span className="text-sm text-gray-400">
          oder per Mikrofon sprechen
        </span>
      )}
    </div>
  )
}
