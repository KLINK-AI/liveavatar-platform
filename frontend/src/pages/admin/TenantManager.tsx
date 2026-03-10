/**
 * Tenant Manager — Create, edit, and manage white-label tenants.
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Pencil, Database, ArrowLeft, X, Check } from 'lucide-react'
import { tenantApi } from '../../lib/api'

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
}

export default function TenantManager() {
  const token = localStorage.getItem('admin_token') || ''
  const [tenants, setTenants] = useState<any[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [editingTenant, setEditingTenant] = useState<any>(null)
  const [form, setForm] = useState<TenantForm>({ ...emptyForm })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (token) {
      tenantApi.list(token).then(setTenants).catch(console.error)
    }
  }, [token])

  const handleCreate = async () => {
    setSaving(true)
    try {
      const data: any = { ...form }
      // Remove empty optional fields
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
      llm_api_key: '', // Don't pre-fill — show placeholder with masked value
      system_prompt: tenant.system_prompt || '',
      elevenlabs_api_key: '', // Don't pre-fill — show placeholder with masked value
      elevenlabs_voice_id: tenant.elevenlabs_voice_id || '',
      stt_provider: tenant.stt_provider || 'deepgram',
    })
    setShowCreate(false)
  }

  const handleUpdate = async () => {
    if (!editingTenant) return
    setSaving(true)
    try {
      const data: any = { ...form }
      delete data.slug // Slug can't be changed
      // Don't send empty API key fields (would overwrite existing)
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

              {/* Avatar Settings */}
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

              {/* LLM Settings */}
              <div className="col-span-2 mt-2">
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

              {/* TTS / STT Settings */}
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
                  {tenant.elevenlabs_api_key_masked && (
                    <p className="text-xs text-green-600 mt-1">
                      ElevenLabs Key: {tenant.elevenlabs_api_key_masked}
                      {tenant.elevenlabs_voice_id && ` | Voice: ${tenant.elevenlabs_voice_id}`}
                    </p>
                  )}
                  <p className="text-xs text-gray-400 mt-1 font-mono">
                    API Key: {tenant.api_key?.substring(0, 16)}...
                  </p>
                </div>
                <div className="flex items-center gap-2">
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
