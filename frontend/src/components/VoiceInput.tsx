/**
 * Voice Input Component
 *
 * Allows users to speak their questions via microphone.
 * Uses the Web Speech API for speech-to-text, then sends
 * the transcribed text through the conversation pipeline.
 */

import { useState, useRef, useCallback } from 'react'
import { Mic, MicOff, Loader2 } from 'lucide-react'

interface VoiceInputProps {
  onTranscript: (text: string) => void
  disabled?: boolean
  language?: string
}

export default function VoiceInput({
  onTranscript,
  disabled = false,
  language = 'de-DE',
}: VoiceInputProps) {
  const [isListening, setIsListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const recognitionRef = useRef<any>(null)

  const startListening = useCallback(() => {
    // Check browser support
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition

    if (!SpeechRecognition) {
      alert('Spracherkennung wird in diesem Browser nicht unterstützt.')
      return
    }

    const recognition = new SpeechRecognition()
    recognition.lang = language
    recognition.continuous = false
    recognition.interimResults = true

    recognition.onstart = () => {
      setIsListening(true)
      setTranscript('')
    }

    recognition.onresult = (event: any) => {
      const result = event.results[event.results.length - 1]
      const text = result[0].transcript

      setTranscript(text)

      if (result.isFinal) {
        onTranscript(text)
        setIsListening(false)
        setTranscript('')
      }
    }

    recognition.onerror = (event: any) => {
      console.error('Speech recognition error:', event.error)
      setIsListening(false)
      setTranscript('')
    }

    recognition.onend = () => {
      setIsListening(false)
    }

    recognitionRef.current = recognition
    recognition.start()
  }, [language, onTranscript])

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop()
    }
    setIsListening(false)
  }, [])

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

      {!isListening && !transcript && (
        <span className="text-sm text-gray-400">
          oder per Mikrofon sprechen
        </span>
      )}
    </div>
  )
}
