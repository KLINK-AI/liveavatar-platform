/**
 * Tenant Manager — Create, edit, and manage white-label tenants.
 *
 * Extended with:
 * - Avatar preview image upload
 * - Multi-language configuration
 * - Greeting text management with auto-translate
 */

import { useEffect, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Pencil, Database, ArrowLeft, X, Check, Upload, Globe, MessageSquare } from 'lucide-react'
import { tenantApi } from '../../lib/api'

const API_BASE = '/api/v1'

interface TenantForm {
  name: string
  slug: string
  liveavatar_avatar_id: string
  llm_provider: string
  llm_model: string
  llm_api_key: string
  system_prompt: string
  elevenlabs_api_key: string
  elevenlabs_voice_id: string
  stt_provider: string
  supported_languages: string[]
  default_language: string
  greeting_text: string
}

const emptyForm: TenantForm = {
  name: '',
  slug: '',
  liveavatar_avatar_id: '',
  llm_provider: 'openai',
  llm_model: 'gpt-4o',
  llm_api_key: '',
  system_prompt: '',
  elevenlabs_api_key: '',
  elevenlabs_voice_id: '',
  stt_provider: 'deepgram',
  supported_languages: ['de'],
  default_language: 'de',
  greeting_text: 'Hallo, ich bin Ihr digitaler Assistent und stehe Ihnen für Fragen zur Verfügung.',
}

const ALL_LANGUAGES = [
  { code: 'de', name: 'Deutsch', flag: '🇩🇪' },
  { code: 'en', name: 'English', flag: '🇬🇧' },
  { code: 'fr', name: 'Français', flag: '🇫🇷' },
  { code: 'es', name: 'Español', flag: '🇪🇸' },
  { code: 'it', name: 'Italiano', flag: '🇮🇹' },
  { code: 'nl', name: 'Nederlands', flag: '🇳🇱' },
  { code: 'pt', name: 'Português', flag: '🇵🇹' },
  { code: 'pl', name: 'Polski', flag: '🇵🇱' },
  { code: 'ru', name: 'Русский', flag: '🇷🇺' },
  { code: 'uk', name: 'Українська', flag: '🇺🇦' },
  { code: 'tr', name: 'Türkçe', flag: '🇹🇷' },
  { code: 'ar', name: 'العربية', flag: '🇸🇦' },
  { code: 'zh', name: '中文', flag: '🇨🇳' },
  { code: 'ja', name: '日本語', flag: '🇯🇵' },
  { code: 'ko', name: '한국어', flag: '🇰🇷' },
  { code: 'sv', name: 'Svenska', flag: '🇸🇪' },
  { code: 'no', name: 'Norsk', flag: '🇳🇴' },
  { code: 'da', name: 'Dansk', flag: '🇩🇰' },
  { code: 'fi', name: 'Suomi', flag: '🇫🇮' },
  { code: 'el', name: 'Ελληνικά', flag: '🇬🇷' },
  { code: 'cs', name: 'Čeština', flag: '🇨🇿' },
  { code: 'ro', name: 'Română', flag: '🇷🇴' },
  { code: 'hu', name: 'Magyar', flag: '🇭🇺' },
  { code: 'bg', name: 'Български', flag: '🇧🇬' },
  { code: 'hr', name: 'Hrvatski', flag: '🇭🇷' },
  { code: 'sk', name: 'Slovenčina', flag: '🇸🇰' },
  { code: 'sl', name: 'Slovenščina', flag: '🇸🇮' },
  { code: 'hi', name: 'हिन्दी', flag: '🇮🇳' },
]

export default function TenantManager() {
  const token = localStorage.getItem('admin_token') || ''
  const [tenants, setTenants] = useState<any[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [editingTenant, setEditingTenant] = useState<any>(null)
  const [form, setForm] = useState<TenantForm>({ ...emptyForm })
  const [saving, setSaving] = useState(false)
  const [uploadingImage, setUploadingImage] = useState(false)
  const [translating, setTranslating] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (token) {
      tenantApi.list(token).then(setTenants).catch(console.error)
    }
  }, [token])

  const handleCreate = async () => {
    setSaving(true)
    try {
      const data: any = { ...form }
      Object.keys(data).forEach(k => { if (data[k] === '') delete data[k] })
      await tenantApi.create(data, token)
      setShowCreate(false)
      setForm({ ...emptyForm })
      const updated = await tenantApi.list(token)
      setTenants(updated)
    } catch (e: any) {
      alert(`Fehler: ${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleEdit = (tenant: any) => {
    setEditingTenant(tenant)
    setForm({
      name: tenant.name || '',
      slug: tenant.slug || '',
      liveavatar_avatar_id: tenant.liveavatar_avatar_id || '',
      llm_provider: tenant.llm_provider || 'openai',
      llm_model: tenant.llm_model || 'gpt-4o',
      llm_api_key: '',
      system_prompt: tenant.system_prompt || '',
      elevenlabs_api_key: '',
      elevenlabs_voice_id: tenant.elevenlabs_voice_id || '',
      stt_provider: tenant.stt_provider || 'deepgram',
      supported_languages: tenant.supported_languages || ['de'],
      default_language: tenant.default_language || 'de',
      greeting_text: tenant.greeting_text || '',
    })
    setShowCreate(false)
  }

  const handleUpdate = async () => {
    if (!editingTenant) return
    setSaving(true)
    try {
      const data: any = { ...form }
      delete data.slug
      if (!data.llm_api_key) delete data.llm_api_key
      if (!data.elevenlabs_api_key) delete data.elevenlabs_api_key
      await tenantApi.update(editingTenant.id, data, token)
      setEditingTenant(null)
      setForm({ ...emptyForm })
      const updated = await tenantApi.list(token)
      setTenants(updated)
    } catch (e: any) {
      alert(`Fehler: ${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = () => {
    setShowCreate(false)
    setEditingTenant(null)
    setForm({ ...emptyForm })
  }

  const handlePreviewImageUpload = async (file: File) => {
    if (!editingTenant) return
    setUploadingImage(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await fetch(`${API_BASE}/tenants/${editingTenant.id}/preview-image`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      })
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Upload failed' }))
        throw new Error(err.detail)
      }
      // Refresh tenant list to get updated image
      const updated = await tenantApi.list(token)
      setTenants(updated)
      // Update editingTenant reference
      const updatedTenant = updated.find((t: any) => t.id === editingTenant.id)
      if (updatedTenant) setEditingTenant(updatedTenant)
      alert('Vorschaubild erfolgreich hochgeladen!')
    } catch (e: any) {
      alert(`Upload-Fehler: ${e.message}`)
    } finally {
      setUploadingImage(false)
    }
  }

  const handleAutoTranslate = async () => {
    if (!editingTenant || !form.greeting_text) return
    setTranslating(true)
    try {
      const targetLangs = form.supported_languages.filter(l => l !== form.default_language)
      if (targetLangs.length === 0) {
        alert('Keine Zielsprachen ausgewählt. Fügen Sie zuerst weitere Sprachen hinzu.')
        return
      }
      const response = await fetch(`${API_BASE}/tenants/${editingTenant.id}/greeting`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          greeting_text: form.greeting_text,
          default_language: form.default_language,
          auto_translate: true,
          target_languages: targetLangs,
        }),
      })
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Translation failed' }))
        throw new Error(err.detail)
      }
      const result = await response.json()
      // Refresh tenant data
      const updated = await tenantApi.list(token)
      setTenants(updated)
      const updatedTenant = updated.find((t: any) => t.id === editingTenant.id)
      if (updatedTenant) setEditingTenant(updatedTenant)
      alert(`Begrüßung in ${targetLangs.length} Sprache(n) übersetzt!`)
    } catch (e: any) {
      alert(`Übersetzungsfehler: ${e.message}`)
    } finally {
      setTranslating(false)
    }
  }

  const toggleLanguage = (code: string) => {
    const current = form.supported_languages
    if (current.includes(code)) {
      // Don't remove default language
      if (code === form.default_language) return
      setForm({ ...form, supported_languages: current.filter(l => l !== code) })
    } else {
      setForm({ ...form, supported_languages: [...current, code] })
    }
  }

  const isEditing = !!editingTenant
  const showForm = showCreate || isEditing

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <Link to="/admin" className="p-2 hover:bg-gray-200 rounded-lg">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <h1 className="text-2xl font-bold text-gray-900">Mandanten-Verwaltung</h1>
          </div>
          {!showForm && (
            <button
              onClick={() => { setShowCreate(true); setEditingTenant(null); setForm({ ...emptyForm }) }}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              <Plus className="w-4 h-4" /> Neuer Mandant
            </button>
          )}
        </div>

        {/* Create / Edit Form */}
        {showForm && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">
                {isEditing ? `${editingTenant.name} bearbeiten` : 'Neuen Mandanten anlegen'}
              </h2>
              <button onClick={handleCancel} className="p-1 hover:bg-gray-100 rounded">
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4">
              {/* --- Basic Info --- */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="z.B. Gemeinde Büttelborn"
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 focus:border-blue-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Slug (URL) {isEditing && <span className="text-gray-400">— nicht änderbar</span>}
                </label>
                <input
                  type="text"
                  value={form.slug}
                  onChange={(e) => setForm({ ...form, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') })}
                  placeholder="z.B. buettelborn"
                  disabled={isEditing}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 focus:border-blue-500 outline-none disabled:bg-gray-100 disabled:text-gray-500"
                />
              </div>

              {/* --- Avatar Settings --- */}
              <div className="col-span-2 mt-2">
                <h3 className="text-sm font-semibold text-blue-600 uppercase tracking-wider mb-2">Avatar-Einstellungen</h3>
              </div>
              <div className="col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  LiveAvatar Avatar-ID
                  <span className="text-gray-400 text-xs ml-2">Die ID aus Ihrem liveavatar.com Account</span>
                </label>
                <input
                  type="text"
                  value={form.liveavatar_avatar_id}
                  onChange={(e) => setForm({ ...form, liveavatar_avatar_id: e.target.value })}
                  placeholder="z.B. 9b116530-ab51-48ec-..."
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 focus:border-blue-500 outline-none"
                />
              </div>

              {/* --- Preview Image Upload --- */}
              {isEditing && (
                <div className="col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Upload className="w-4 h-4 inline mr-1" />
                    Vorschaubild (Startbildschirm)
                  </label>
                  <div className="flex items-start gap-4">
                    {/* Current preview */}
                    {editingTenant.avatar_preview_image && (
                      <div className="w-32 h-20 rounded-lg overflow-hidden border border-gray-200 flex-shrink-0">
                        <img
                          src={editingTenant.avatar_preview_image}
                          alt="Vorschau"
                          className="w-full h-full object-cover"
                        />
                      </div>
                    )}
                    {/* Upload button */}
                    <div>
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/png,image/jpeg,image/webp"
                        className="hidden"
                        onChange={(e) => {
                          const file = e.target.files?.[0]
                          if (file) handlePreviewImageUpload(file)
                        }}
                      />
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        disabled={uploadingImage}
                        className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 text-sm disabled:opacity-50"
                      >
                        {uploadingImage ? 'Wird hochgeladen...' : 'Bild hochladen'}
                      </button>
                      <p className="text-xs text-gray-400 mt-1">PNG, JPG oder WebP. Max 5MB.</p>
                    </div>
                  </div>
                </div>
              )}

              {/* --- Multi-Language --- */}
              <div className="col-span-2 mt-4">
                <h3 className="text-sm font-semibold text-green-600 uppercase tracking-wider mb-2">
                  <Globe className="w-4 h-4 inline mr-1" />
                  Mehrsprachigkeit
                </h3>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Hauptsprache</label>
                <select
                  value={form.default_language}
                  onChange={(e) => {
                    const lang = e.target.value
                    setForm({
                      ...form,
                      default_language: lang,
                      supported_languages: form.supported_languages.includes(lang)
                        ? form.supported_languages
                        : [lang, ...form.supported_languages],
                    })
                  }}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 focus:border-blue-500 outline-none"
                >
                  {ALL_LANGUAGES.map(l => (
                    <option key={l.code} value={l.code}>{l.flag} {l.name}</option>
                  ))}
                </select>
              </div>
              <div className="col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Unterstützte Sprachen
                  <span className="text-gray-400 text-xs ml-2">Klicken zum An/Abwählen</span>
                </label>
                <div className="flex flex-wrap gap-2">
                  {ALL_LANGUAGES.map(l => {
                    const isSelected = form.supported_languages.includes(l.code)
                    const isDefault = l.code === form.default_language
                    return (
                      <button
                        key={l.code}
                        type="button"
                        onClick={() => toggleLanguage(l.code)}
                        className={`
                          inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm transition-all
                          ${isSelected
                            ? isDefault
                              ? 'bg-green-100 text-green-800 border-2 border-green-300 font-medium'
                              : 'bg-blue-100 text-blue-800 border-2 border-blue-200'
                            : 'bg-gray-100 text-gray-500 border-2 border-transparent hover:bg-gray-200'
                          }
                        `}
                      >
                        <span>{l.flag}</span>
                        <span>{l.code.toUpperCase()}</span>
                      </button>
                    )
                  })}
                </div>
                <p className="text-xs text-gray-400 mt-2">
                  Ausgewählt: {form.supported_languages.length} Sprache(n). Hauptsprache (grün) kann nicht abgewählt werden.
                </p>
              </div>

              {/* --- Greeting --- */}
              <div className="col-span-2 mt-4">
                <h3 className="text-sm font-semibold text-purple-600 uppercase tracking-wider mb-2">
                  <MessageSquare className="w-4 h-4 inline mr-1" />
                  Begrüßungstext
                </h3>
                <p className="text-xs text-gray-400 mb-3">
                  Der Avatar spricht diesen Text beim Start des Gesprächs.
                </p>
              </div>
              <div className="col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Begrüßung ({ALL_LANGUAGES.find(l => l.code === form.default_language)?.name || 'Hauptsprache'})
                </label>
                <textarea
                  value={form.greeting_text}
                  onChange={(e) => setForm({ ...form, greeting_text: e.target.value })}
                  placeholder="Hallo, ich bin Ihr digitaler Assistent..."
                  rows={2}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 focus:border-blue-500 outline-none"
                />
                <p className="text-xs text-gray-400 mt-1">
                  {form.greeting_text.length}/200 Zeichen
                </p>
              </div>
              {isEditing && form.supported_languages.length > 1 && (
                <div className="col-span-2">
                  <button
                    type="button"
                    onClick={handleAutoTranslate}
                    disabled={translating || !form.greeting_text}
                    className="flex items-center gap-2 px-4 py-2 bg-purple-100 text-purple-700 rounded-lg hover:bg-purple-200 text-sm disabled:opacity-50"
                  >
                    <Globe className="w-4 h-4" />
                    {translating ? 'Wird übersetzt...' : 'Automatisch übersetzen'}
                  </button>
                  {/* Show existing translations */}
                  {editingTenant.greeting_translations && Object.keys(editingTenant.greeting_translations).length > 0 && (
                    <div className="mt-3 space-y-2">
                      {Object.entries(editingTenant.greeting_translations).map(([lang, text]) => {
                        const langData = ALL_LANGUAGES.find(l => l.code === lang)
                        return (
                          <div key={lang} className="flex items-start gap-2 text-sm">
                            <span className="flex-shrink-0 mt-0.5">{langData?.flag || '🌐'}</span>
                            <span className="text-gray-600">{text as string}</span>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* --- LLM Settings --- */}
              <div className="col-span-2 mt-4">
                <h3 className="text-sm font-semibold text-blue-600 uppercase tracking-wider mb-2">LLM-Einstellungen</h3>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">LLM Provider</label>
                <select
                  value={form.llm_provider}
                  onChange={(e) => setForm({ ...form, llm_provider: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 focus:border-blue-500 outline-none"
                >
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic (Claude)</option>
                  <option value="ollama">Ollama (Lokal)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">LLM Model</label>
                <input
                  type="text"
                  value={form.llm_model}
                  onChange={(e) => setForm({ ...form, llm_model: e.target.value })}
                  placeholder="z.B. gpt-4o"
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 focus:border-blue-500 outline-none"
                />
              </div>
              <div className="col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  LLM API Key (optional, falls pro Mandant)
                </label>
                <input
                  type="password"
                  value={form.llm_api_key}
                  onChange={(e) => setForm({ ...form, llm_api_key: e.target.value })}
                  placeholder={isEditing && editingTenant?.llm_api_key_masked
                    ? `Gespeichert: ${editingTenant.llm_api_key_masked} — leer lassen um beizubehalten`
                    : 'Leer = globaler Key aus Umgebungsvariablen'}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 focus:border-blue-500 outline-none"
                />
                {isEditing && editingTenant?.llm_api_key_masked && (
                  <p className="text-xs text-green-600 mt-1">
                    Gespeicherter Key: {editingTenant.llm_api_key_masked}
                  </p>
                )}
              </div>
              <div className="col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">System Prompt</label>
                <textarea
                  value={form.system_prompt}
                  onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
                  placeholder="Du bist der digitale Assistent der Gemeinde Büttelborn..."
                  rows={4}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 focus:border-blue-500 outline-none"
                />
              </div>

              {/* --- TTS / STT Settings --- */}
              <div className="col-span-2 mt-2">
                <h3 className="text-sm font-semibold text-blue-600 uppercase tracking-wider mb-2">
                  Stimme (ElevenLabs TTS)
                </h3>
                <p className="text-xs text-gray-400 mb-3">
                  Im LITE Mode wird die Stimme über ElevenLabs generiert und als Audio an den Avatar gesendet.
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  ElevenLabs API Key (optional)
                </label>
                <input
                  type="password"
                  value={form.elevenlabs_api_key}
                  onChange={(e) => setForm({ ...form, elevenlabs_api_key: e.target.value })}
                  placeholder={isEditing && editingTenant?.elevenlabs_api_key_masked
                    ? `Gespeichert: ${editingTenant.elevenlabs_api_key_masked} — leer lassen`
                    : 'Leer = globaler Key'}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 focus:border-blue-500 outline-none"
                />
                {isEditing && editingTenant?.elevenlabs_api_key_masked && (
                  <p className="text-xs text-green-600 mt-1">
                    Gespeicherter Key: {editingTenant.elevenlabs_api_key_masked}
                  </p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  ElevenLabs Voice-ID
                  <span className="text-gray-400 text-xs ml-1">(die Stimme für den Avatar)</span>
                </label>
                <input
                  type="text"
                  value={form.elevenlabs_voice_id}
                  onChange={(e) => setForm({ ...form, elevenlabs_voice_id: e.target.value })}
                  placeholder="z.B. i864UlSuWq9bx6fRZpva"
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 focus:border-blue-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">STT Provider (Spracherkennung)</label>
                <select
                  value={form.stt_provider}
                  onChange={(e) => setForm({ ...form, stt_provider: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 focus:border-blue-500 outline-none"
                >
                  <option value="deepgram">Deepgram</option>
                  <option value="openai">OpenAI Whisper</option>
                </select>
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={isEditing ? handleUpdate : handleCreate}
                disabled={saving}
                className="flex items-center gap-2 px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                <Check className="w-4 h-4" />
                {saving ? 'Speichern...' : (isEditing ? 'Speichern' : 'Anlegen')}
              </button>
              <button
                onClick={handleCancel}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
              >
                Abbrechen
              </button>
            </div>
          </div>
        )}

        {/* Tenant List */}
        <div className="space-y-4">
          {tenants.map((tenant) => (
            <div key={tenant.id} className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <div className="flex items-center justify-between">
                <div className="flex items-start gap-4">
                  {/* Preview thumbnail */}
                  {tenant.avatar_preview_image && (
                    <div className="w-16 h-16 rounded-lg overflow-hidden flex-shrink-0 border border-gray-200">
                      <img
                        src={tenant.avatar_preview_image}
                        alt=""
                        className="w-full h-full object-cover"
                      />
                    </div>
                  )}
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">{tenant.name}</h3>
                    <p className="text-sm text-gray-500 mt-1">
                      Slug: <code className="bg-gray-100 px-2 py-0.5 rounded">{tenant.slug}</code>
                      {' | '}LLM: {tenant.llm_provider}/{tenant.llm_model}
                    </p>
                    {tenant.liveavatar_avatar_id && (
                      <p className="text-xs text-gray-400 mt-1">
                        Avatar: <code>{tenant.liveavatar_avatar_id.substring(0, 20)}...</code>
                      </p>
                    )}
                    {!tenant.liveavatar_avatar_id && (
                      <p className="text-xs text-orange-500 mt-1">
                        Kein Avatar zugewiesen — bitte bearbeiten
                      </p>
                    )}
                    {/* Language badges */}
                    {tenant.supported_languages && tenant.supported_languages.length > 1 && (
                      <div className="flex items-center gap-1 mt-1">
                        <Globe className="w-3 h-3 text-green-600" />
                        <span className="text-xs text-green-600">
                          {tenant.supported_languages.length} Sprachen
                        </span>
                        <span className="text-xs text-gray-400 ml-1">
                          ({(tenant.supported_languages as string[]).map((l: string) => l.toUpperCase()).join(', ')})
                        </span>
                      </div>
                    )}
                    <p className="text-xs text-gray-400 mt-1 font-mono">
                      API Key: {tenant.api_key?.substring(0, 16)}...
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    onClick={() => handleEdit(tenant)}
                    className="flex items-center gap-1 px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 rounded-lg border border-gray-200"
                  >
                    <Pencil className="w-4 h-4" /> Bearbeiten
                  </button>
                  <Link
                    to={`/admin/knowledge/${tenant.id}`}
                    className="flex items-center gap-1 px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 rounded-lg border border-gray-200"
                  >
                    <Database className="w-4 h-4" /> Wissensbasis
                  </Link>
                  <button
                    onClick={() => {
                      // Superadmin jumps into tenant-admin view by storing admin_token as tenant_admin_token
                      const adminToken = localStorage.getItem('admin_token')
                      if (adminToken) {
                        localStorage.setItem('tenant_admin_token', adminToken)
                        window.open('/tenant-admin', '_blank')
                      }
                    }}
                    className="flex items-center gap-1 px-3 py-2 text-sm text-purple-600 hover:bg-purple-50 rounded-lg border border-purple-200"
                    title="Als Kunde den Admin-Bereich öffnen"
                  >
                    Kunden-Admin
                  </button>
                  <Link
                    to={`/avatar/${tenant.slug}`}
                    className="flex items-center gap-1 px-3 py-2 text-sm text-blue-600 hover:bg-blue-50 rounded-lg border border-blue-200"
                  >
                    Avatar testen
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
