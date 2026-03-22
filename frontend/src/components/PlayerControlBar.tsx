/**
 * Player Control Bar — unified controls below the avatar player.
 *
 * Contains:
 * - Microphone button (start/stop voice input)
 * - Language selector button (opens LanguagePicker)
 * - Chat toggle button (show/hide chat history)
 *
 * Designed to work in both AvatarPage and Embed contexts.
 */

import { useState, useRef, useCallback, useMemo, useEffect } from 'react'
import { Mic, MicOff, Globe, MessageSquare, MessageSquareOff, Loader2, Volume2 } from 'lucide-react'

/** Map short language codes to BCP-47 tags for Web Speech API */
const LANGUAGE_MAP: Record<string, string> = {
  de: 'de-DE',
  en: 'en-US',
  fr: 'fr-FR',
  es: 'es-ES',
  it: 'it-IT',
  nl: 'nl-NL',
  pt: 'pt-PT',
  pl: 'pl-PL',
  ru: 'ru-RU',
  tr: 'tr-TR',
  ar: 'ar-SA',
  zh: 'zh-CN',
  ja: 'ja-JP',
  ko: 'ko-KR',
  hi: 'hi-IN',
  sv: 'sv-SE',
  no: 'nb-NO',
  da: 'da-DK',
  fi: 'fi-FI',
  el: 'el-GR',
  cs: 'cs-CZ',
  ro: 'ro-RO',
  hu: 'hu-HU',
  bg: 'bg-BG',
  hr: 'hr-HR',
  sk: 'sk-SK',
  sl: 'sl-SI',
  uk: 'uk-UA',
}

const LANGUAGE_FLAGS: Record<string, string> = {
  de: '🇩🇪', en: '🇬🇧', fr: '🇫🇷', es: '🇪🇸', it: '🇮🇹', nl: '🇳🇱',
  pt: '🇵🇹', pl: '🇵🇱', ru: '🇷🇺', uk: '🇺🇦', tr: '🇹🇷', ar: '🇸🇦',
  zh: '🇨🇳', ja: '🇯🇵', ko: '🇰🇷', hi: '🇮🇳', sv: '🇸🇪', no: '🇳🇴',
  da: '🇩🇰', fi: '🇫🇮', el: '🇬🇷', cs: '🇨🇿', ro: '🇷🇴', hu: '🇭🇺',
  bg: '🇧🇬', hr: '🇭🇷', sk: '🇸🇰', sl: '🇸🇮',
}

interface PlayerControlBarProps {
  /** Called with transcribed text from voice input */
  onTranscript: (text: string) => void
  /** Whether voice input / message sending is disabled (loading or avatar speaking) */
  disabled: boolean
  /** Whether the avatar is currently speaking */
  avatarSpeaking: boolean
  /** Current language code (e.g. 'de') */
  language: string
  /** Whether chat history panel is visible */
  chatVisible: boolean
  /** Toggle chat history visibility */
  onToggleChat: () => void
  /** Called when user wants to change language (opens language picker) */
  onLanguageChange?: () => void
  /** Whether language change is available (multi-language tenant) */
  showLanguageButton?: boolean
  /** Primary color for active states */
  primaryColor?: string
}

export default function PlayerControlBar({
  onTranscript,
  disabled,
  avatarSpeaking,
  language,
  chatVisible,
  onToggleChat,
  onLanguageChange,
  showLanguageButton = false,
  primaryColor = '#2563eb',
}: PlayerControlBarProps) {
  const [isListening, setIsListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const recognitionRef = useRef<any>(null)
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const latestTranscriptRef = useRef<string>('')
  const hasSentRef = useRef<boolean>(false)

  const SILENCE_TIMEOUT = 2000

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
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition

    if (!SpeechRecognition) {
      alert('Spracherkennung wird in diesem Browser nicht unterstützt.')
      return
    }

    const recognition = new SpeechRecognition()
    recognition.lang = speechLang
    recognition.continuous = true
    recognition.interimResults = true

    recognition.onstart = () => {
      setIsListening(true)
      setTranscript('')
      latestTranscriptRef.current = ''
      hasSentRef.current = false
    }

    recognition.onresult = (event: any) => {
      let fullTranscript = ''
      for (let i = 0; i < event.results.length; i++) {
        fullTranscript += event.results[i][0].transcript
      }
      setTranscript(fullTranscript)
      latestTranscriptRef.current = fullTranscript

      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current)
      silenceTimerRef.current = setTimeout(() => {
        if (hasSentRef.current) return
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

  // Force-stop listening when disabled becomes true
  useEffect(() => {
    if (disabled && isListening) {
      stopListening()
      setTranscript('')
    }
  }, [disabled, isListening, stopListening])

  const flag = LANGUAGE_FLAGS[language] || '🌐'

  return (
    <div className="player-control-bar">
      {/* Transcript preview — shows above control bar when listening */}
      {transcript && (
        <div className="px-4 pb-2">
          <div className="px-4 py-2 bg-blue-50 rounded-lg text-sm text-blue-800 italic flex items-center gap-2">
            <span className="flex-1 truncate">{transcript}</span>
            <Loader2 className="w-3 h-3 animate-spin flex-shrink-0" />
          </div>
        </div>
      )}

      {/* Avatar speaking indicator */}
      {!isListening && !transcript && avatarSpeaking && (
        <div className="px-4 pb-2">
          <div className="flex items-center justify-center gap-2 text-sm text-amber-500">
            <Volume2 className="w-4 h-4 animate-pulse" />
            <span>Avatar spricht...</span>
          </div>
        </div>
      )}

      {/* Control buttons row */}
      <div className="flex items-center justify-center gap-3 px-4 py-3">
        {/* Microphone button */}
        <button
          onClick={isListening ? stopListening : startListening}
          disabled={disabled}
          className={`control-btn ${
            isListening
              ? 'bg-red-500 text-white shadow-lg shadow-red-200 animate-pulse'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          } disabled:opacity-50 disabled:cursor-not-allowed`}
          title={isListening ? 'Aufnahme stoppen' : 'Spracheingabe starten'}
        >
          {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
        </button>

        {/* Language button */}
        {showLanguageButton && onLanguageChange && (
          <button
            onClick={onLanguageChange}
            className="control-btn bg-gray-100 text-gray-600 hover:bg-gray-200 gap-1.5"
            title="Sprache wechseln"
          >
            <span className="text-base leading-none">{flag}</span>
            <Globe className="w-4 h-4" />
          </button>
        )}

        {/* Chat toggle button */}
        <button
          onClick={onToggleChat}
          className={`control-btn ${
            chatVisible
              ? 'text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
          style={chatVisible ? { backgroundColor: primaryColor } : undefined}
          title={chatVisible ? 'Chat verbergen' : 'Chat anzeigen'}
        >
          {chatVisible ? (
            <MessageSquare className="w-5 h-5" />
          ) : (
            <MessageSquareOff className="w-5 h-5" />
          )}
        </button>
      </div>
    </div>
  )
}
