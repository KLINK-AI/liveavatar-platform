/**
 * Tenant Manager — Create and manage white-label tenants.
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Settings, Database, ArrowLeft } from 'lucide-react'
import { tenantApi } from '../../lib/api'

export default function TenantManager() {
  const token = localStorage.getItem('admin_token') || ''
  const [tenants, setTenants] = useState<any[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({
    name: '',
    slug: '',
    heygen_avatar_id: '',
    llm_provider: 'openai',
    llm_model: 'gpt-4o',
    system_prompt: '',
  })

  useEffect(() => {
    if (token) {
      tenantApi.list(token).then(setTenants).catch(console.error)
    }
  }, [token])

  const handleCreate = async () => {
    try {
      await tenantApi.create(form, token)
      setShowCreate(false)
      setForm({ name: '', slug: '', heygen_avatar_id: '', llm_provider: 'openai', llm_model: 'gpt-4o', system_prompt: '' })
      // Reload
      const updated = await tenantApi.list(token)
      setTenants(updated)
    } catch (e: any) {
      alert(`Fehler: ${e.message}`)
    }
  }

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
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            <Plus className="w-4 h-4" /> Neuer Mandant
          </button>
        </div>

        {/* Create Form */}
        {showCreate && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">Neuen Mandanten anlegen</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="z.B. Stadt Büttelborn"
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 focus:border-blue-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Slug (URL)</label>
                <input
                  type="text"
                  value={form.slug}
                  onChange={(e) => setForm({ ...form, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') })}
                  placeholder="z.B. buettelborn"
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 focus:border-blue-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">HeyGen Avatar ID</label>
                <input
                  type="text"
                  value={form.heygen_avatar_id}
                  onChange={(e) => setForm({ ...form, heygen_avatar_id: e.target.value })}
                  placeholder="Avatar ID aus HeyGen"
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 focus:border-blue-500 outline-none"
                />
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
                <label className="block text-sm font-medium text-gray-700 mb-1">System Prompt</label>
                <textarea
                  value={form.system_prompt}
                  onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
                  placeholder="Du bist der virtuelle Bürgermeister von Büttelborn..."
                  rows={4}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 focus:border-blue-500 outline-none"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-4">
              <button
                onClick={handleCreate}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Anlegen
              </button>
              <button
                onClick={() => setShowCreate(false)}
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
                  <p className="text-xs text-gray-400 mt-1 font-mono">
                    API Key: {tenant.api_key?.substring(0, 16)}...
                  </p>
                </div>
                <div className="flex items-center gap-2">
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
