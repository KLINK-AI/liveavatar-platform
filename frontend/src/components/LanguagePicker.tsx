/**
 * Language Picker Component
 *
 * Displays a modal overlay where the user selects their preferred language
 * before starting the avatar conversation.
 *
 * Features:
 * - Grid of language flags with labels
 * - Search/filter functionality
 * - Highlights default language
 * - Responsive design
 */

import { useState, useMemo } from 'react'
import { Search } from 'lucide-react'

interface LanguagePickerProps {
  supportedLanguages: string[]
  defaultLanguage: string
  onSelect: (language: string) => void
  tenantName?: string
}

// Language metadata: code → { name, nativeName, flag }
const LANGUAGE_DATA: Record<string, { name: string; nativeName: string; flag: string }> = {
  de: { name: 'Deutsch', nativeName: 'Deutsch', flag: '🇩🇪' },
  en: { name: 'English', nativeName: 'English', flag: '🇬🇧' },
  fr: { name: 'Französisch', nativeName: 'Français', flag: '🇫🇷' },
  es: { name: 'Spanisch', nativeName: 'Español', flag: '🇪🇸' },
  it: { name: 'Italienisch', nativeName: 'Italiano', flag: '🇮🇹' },
  nl: { name: 'Niederländisch', nativeName: 'Nederlands', flag: '🇳🇱' },
  pt: { name: 'Portugiesisch', nativeName: 'Português', flag: '🇵🇹' },
  pl: { name: 'Polnisch', nativeName: 'Polski', flag: '🇵🇱' },
  ru: { name: 'Russisch', nativeName: 'Русский', flag: '🇷🇺' },
  uk: { name: 'Ukrainisch', nativeName: 'Українська', flag: '🇺🇦' },
  tr: { name: 'Türkisch', nativeName: 'Türkçe', flag: '🇹🇷' },
  ar: { name: 'Arabisch', nativeName: 'العربية', flag: '🇸🇦' },
  zh: { name: 'Chinesisch', nativeName: '中文', flag: '🇨🇳' },
  ja: { name: 'Japanisch', nativeName: '日本語', flag: '🇯🇵' },
  ko: { name: 'Koreanisch', nativeName: '한국어', flag: '🇰🇷' },
  hi: { name: 'Hindi', nativeName: 'हिन्दी', flag: '🇮🇳' },
  sv: { name: 'Schwedisch', nativeName: 'Svenska', flag: '🇸🇪' },
  no: { name: 'Norwegisch', nativeName: 'Norsk', flag: '🇳🇴' },
  da: { name: 'Dänisch', nativeName: 'Dansk', flag: '🇩🇰' },
  fi: { name: 'Finnisch', nativeName: 'Suomi', flag: '🇫🇮' },
  el: { name: 'Griechisch', nativeName: 'Ελληνικά', flag: '🇬🇷' },
  cs: { name: 'Tschechisch', nativeName: 'Čeština', flag: '🇨🇿' },
  ro: { name: 'Rumänisch', nativeName: 'Română', flag: '🇷🇴' },
  hu: { name: 'Ungarisch', nativeName: 'Magyar', flag: '🇭🇺' },
  bg: { name: 'Bulgarisch', nativeName: 'Български', flag: '🇧🇬' },
  hr: { name: 'Kroatisch', nativeName: 'Hrvatski', flag: '🇭🇷' },
  sk: { name: 'Slowakisch', nativeName: 'Slovenčina', flag: '🇸🇰' },
  sl: { name: 'Slowenisch', nativeName: 'Slovenščina', flag: '🇸🇮' },
}

export default function LanguagePicker({
  supportedLanguages,
  defaultLanguage,
  onSelect,
  tenantName,
}: LanguagePickerProps) {
  const [search, setSearch] = useState('')

  const filteredLanguages = useMemo(() => {
    if (!search.trim()) return supportedLanguages

    const term = search.toLowerCase()
    return supportedLanguages.filter((code) => {
      const data = LANGUAGE_DATA[code]
      if (!data) return false
      return (
        data.name.toLowerCase().includes(term) ||
        data.nativeName.toLowerCase().includes(term) ||
        code.toLowerCase().includes(term)
      )
    })
  }, [supportedLanguages, search])

  // If only one language, auto-select it
  if (supportedLanguages.length === 1) {
    // Will be handled by parent
    return null
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden"
        style={{ animation: 'fadeIn 0.3s ease-out' }}
      >
        {/* Header */}
        <div className="p-6 pb-4 text-center">
          <h2 className="text-xl font-bold text-gray-900 mb-1">
            Sprache auswählen
          </h2>
          <p className="text-sm text-gray-500">
            Suchen oder auswählen:
          </p>
        </div>

        {/* Search */}
        {supportedLanguages.length > 6 && (
          <div className="px-6 pb-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Sprache suchen..."
                className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-gray-200 focus:border-blue-500 outline-none text-sm"
                autoFocus
              />
            </div>
          </div>
        )}

        {/* Default language hint */}
        {!search && (
          <div className="px-6 pb-3 flex items-center gap-2 text-sm text-gray-500">
            <span>Standard:</span>
            <button
              onClick={() => onSelect(defaultLanguage)}
              className="inline-flex items-center gap-1.5 px-3 py-1 bg-blue-50 text-blue-700 rounded-full hover:bg-blue-100 transition-colors font-medium"
            >
              <span className="text-lg">{LANGUAGE_DATA[defaultLanguage]?.flag || '🌐'}</span>
              {LANGUAGE_DATA[defaultLanguage]?.nativeName || defaultLanguage}
            </button>
          </div>
        )}

        {/* Language Grid */}
        <div className="px-6 pb-6 max-h-[50vh] overflow-y-auto">
          <div className="grid grid-cols-4 gap-2">
            {filteredLanguages.map((code) => {
              const data = LANGUAGE_DATA[code]
              if (!data) return null

              const isDefault = code === defaultLanguage

              return (
                <button
                  key={code}
                  onClick={() => onSelect(code)}
                  className={`
                    flex items-center gap-2 px-3 py-2.5 rounded-xl text-left transition-all
                    hover:bg-blue-50 hover:scale-[1.02] active:scale-[0.98]
                    ${isDefault
                      ? 'bg-blue-50 border-2 border-blue-200'
                      : 'bg-gray-50 border-2 border-transparent hover:border-blue-200'
                    }
                  `}
                >
                  <span className="text-xl">{data.flag}</span>
                  <span className="text-sm font-medium text-gray-800 truncate">
                    {code.toUpperCase()}
                  </span>
                </button>
              )
            })}
          </div>

          {filteredLanguages.length === 0 && (
            <p className="text-center text-gray-400 py-4 text-sm">
              Keine Sprache gefunden.
            </p>
          )}
        </div>
      </div>

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: scale(0.95) translateY(10px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
      `}</style>
    </div>
  )
}
