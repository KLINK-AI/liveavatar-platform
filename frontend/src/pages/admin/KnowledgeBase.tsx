/**
 * Knowledge Base Management — Upload documents, add URLs, manage RAG sources.
 */

import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Upload, Globe, Trash2, Search, Plus } from 'lucide-react'
import { knowledgeApi } from '../../lib/api'

export default function KnowledgeBasePage() {
  const { tenantId } = useParams<{ tenantId: string }>()
  const token = localStorage.getItem('admin_token') || ''

  const [kbs, setKbs] = useState<any[]>([])
  const [selectedKb, setSelectedKb] = useState<any>(null)
  const [documents, setDocuments] = useState<any[]>([])
  const [showNewKb, setShowNewKb] = useState(false)
  const [newKbName, setNewKbName] = useState('')
  const [urlInput, setUrlInput] = useState('')
  const [crawlSite, setCrawlSite] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (token) {
      knowledgeApi.list(token).then(setKbs).catch(console.error)
    }
  }, [token])

  useEffect(() => {
    if (selectedKb && token) {
      knowledgeApi.listDocuments(selectedKb.id, token).then(setDocuments).catch(console.error)
    }
  }, [selectedKb, token])

  const handleCreateKb = async () => {
    if (!newKbName) return
    try {
      const kb = await knowledgeApi.create(newKbName, '', token)
      setKbs([...kbs, kb])
      setShowNewKb(false)
      setNewKbName('')
    } catch (e: any) {
      alert(e.message)
    }
  }

  const handleIndexUrl = async () => {
    if (!selectedKb || !urlInput) return
    setIsLoading(true)
    try {
      await knowledgeApi.indexUrl(selectedKb.id, urlInput, crawlSite, token)
      setUrlInput('')
      // Reload documents
      const docs = await knowledgeApi.listDocuments(selectedKb.id, token)
      setDocuments(docs)
    } catch (e: any) {
      alert(e.message)
    } finally {
      setIsLoading(false)
    }
  }

  const handleDeleteDoc = async (docId: string) => {
    if (!selectedKb) return
    try {
      await knowledgeApi.deleteDocument(selectedKb.id, docId, token)
      setDocuments(documents.filter(d => d.id !== docId))
    } catch (e: any) {
      alert(e.message)
    }
  }

  const handleSearch = async () => {
    if (!selectedKb || !searchQuery) return
    try {
      const result = await knowledgeApi.search(selectedKb.id, searchQuery, token)
      setSearchResults(result.results)
    } catch (e: any) {
      alert(e.message)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <Link to="/admin/tenants" className="p-2 hover:bg-gray-200 rounded-lg">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">Wissensbasis</h1>
        </div>

        <div className="grid grid-cols-3 gap-6">
          {/* KB List */}
          <div className="col-span-1">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-semibold">Datenbanken</h2>
                <button onClick={() => setShowNewKb(true)} className="p-1 hover:bg-gray-100 rounded">
                  <Plus className="w-4 h-4" />
                </button>
              </div>

              {showNewKb && (
                <div className="mb-4 space-y-2">
                  <input
                    type="text"
                    value={newKbName}
                    onChange={(e) => setNewKbName(e.target.value)}
                    placeholder="Name der Wissensbasis"
                    className="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 outline-none"
                  />
                  <button onClick={handleCreateKb} className="w-full py-2 text-sm bg-blue-600 text-white rounded-lg">
                    Erstellen
                  </button>
                </div>
              )}

              <div className="space-y-1">
                {kbs.map((kb) => (
                  <button
                    key={kb.id}
                    onClick={() => setSelectedKb(kb)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm ${
                      selectedKb?.id === kb.id ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50'
                    }`}
                  >
                    {kb.name}
                    <span className="text-xs text-gray-400 ml-2">{kb.document_count} Docs</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* KB Details */}
          <div className="col-span-2">
            {selectedKb ? (
              <div className="space-y-6">
                {/* Add URL */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                  <h3 className="font-semibold mb-3 flex items-center gap-2">
                    <Globe className="w-4 h-4" /> URL indexieren
                  </h3>
                  <div className="flex gap-3">
                    <input
                      type="url"
                      value={urlInput}
                      onChange={(e) => setUrlInput(e.target.value)}
                      placeholder="https://example.com"
                      className="flex-1 px-3 py-2 rounded-lg border border-gray-300 outline-none text-sm"
                    />
                    <label className="flex items-center gap-2 text-sm text-gray-600">
                      <input
                        type="checkbox"
                        checked={crawlSite}
                        onChange={(e) => setCrawlSite(e.target.checked)}
                      />
                      Ganze Website
                    </label>
                    <button
                      onClick={handleIndexUrl}
                      disabled={isLoading || !urlInput}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm disabled:opacity-50"
                    >
                      {isLoading ? 'Läuft...' : 'Indexieren'}
                    </button>
                  </div>
                </div>

                {/* Documents */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                  <h3 className="font-semibold mb-3">Dokumente ({documents.length})</h3>
                  <div className="space-y-2">
                    {documents.map((doc) => (
                      <div key={doc.id} className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg">
                        <div>
                          <span className="text-sm font-medium">{doc.name}</span>
                          <span className="text-xs text-gray-400 ml-2">
                            {doc.type} | {doc.chunks} Chunks | {doc.status}
                          </span>
                        </div>
                        <button
                          onClick={() => handleDeleteDoc(doc.id)}
                          className="p-1 text-red-400 hover:text-red-600"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Search Test */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                  <h3 className="font-semibold mb-3 flex items-center gap-2">
                    <Search className="w-4 h-4" /> Suche testen
                  </h3>
                  <div className="flex gap-3 mb-4">
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Testfrage eingeben..."
                      className="flex-1 px-3 py-2 rounded-lg border border-gray-300 outline-none text-sm"
                    />
                    <button
                      onClick={handleSearch}
                      className="px-4 py-2 bg-gray-800 text-white rounded-lg text-sm"
                    >
                      Suchen
                    </button>
                  </div>
                  {searchResults.length > 0 && (
                    <div className="space-y-3">
                      {searchResults.map((r, i) => (
                        <div key={i} className="p-3 bg-blue-50 rounded-lg text-sm">
                          <div className="flex justify-between mb-1">
                            <span className="text-xs text-blue-600">Score: {r.score.toFixed(3)}</span>
                            <span className="text-xs text-gray-400">{r.source}</span>
                          </div>
                          <p className="text-gray-700">{r.text.substring(0, 300)}...</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center text-gray-400">
                Wählen Sie eine Wissensbasis aus oder erstellen Sie eine neue.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
