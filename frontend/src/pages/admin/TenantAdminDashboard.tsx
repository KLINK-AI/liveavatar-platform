/**
 * Tenant Admin Dashboard — Customer-facing admin panel.
 *
 * Accessible via /tenant-admin (separate from master admin).
 * Provides:
 * - Test Query: Chat with LLM+RAG without avatar (test KB quality)
 * - Chat Logs: All questions/answers with RAG sources + timing
 * - Analytics: Document usage, query volume, token consumption
 *
 * Note: System Prompt is managed in the Master Admin area only (not accessible to customers).
 *
 * Reference: buergerguide.botgenossen.cloud/admin/rag
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  MessageSquare, FileText, BarChart3, LogOut,
  Send, Loader2, Search, ChevronDown, ChevronRight,
  Clock, Database, Zap, AlertCircle
} from 'lucide-react'
import { tenantAdminApi } from '../../lib/api'

type Tab = 'test-query' | 'chat-logs' | 'analytics'

// ─── Login Form ───
function LoginForm({ onLogin }: { onLogin: (token: string, user: any) => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await tenantAdminApi.login(email, password)
      onLogin(res.access_token, res)
    } catch (err: any) {
      setError(err.message || 'Login fehlgeschlagen')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-md">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Kunden-Admin</h1>
        <p className="text-gray-500 mb-6">Melden Sie sich an, um Ihre Wissensdatenbank zu verwalten.</p>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <input
            type="email"
            placeholder="E-Mail"
            value={email}
            onChange={e => setEmail(e.target.value)}
            className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:border-blue-500 focus:outline-none"
            required
          />
          <input
            type="password"
            placeholder="Passwort"
            value={password}
            onChange={e => setPassword(e.target.value)}
            className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:border-blue-500 focus:outline-none"
            required
          />
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Anmelden...' : 'Anmelden'}
          </button>
        </div>
      </form>
    </div>
  )
}

// ─── Test Query Tab ───
function TestQueryTab({ token }: { token: string }) {
  const [query, setQuery] = useState('')
  const [language, setLanguage] = useState('de')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [history, setHistory] = useState<any[]>([])
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim() || loading) return
    setLoading(true)
    try {
      const res = await tenantAdminApi.testQuery(query.trim(), language, token)
      const entry = { query: query.trim(), ...res, timestamp: new Date().toISOString() }
      setResult(entry)
      setHistory(prev => [entry, ...prev])
      setQuery('')
    } catch (err: any) {
      setResult({ error: err.message })
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold mb-4">Test Query — Wissensdatenbank testen</h2>
        <p className="text-sm text-gray-500 mb-4">
          Stellen Sie Testfragen, um die Qualität der Antworten zu prüfen. Kein Video-Avatar nötig.
        </p>

        <form onSubmit={handleSubmit} className="flex gap-3">
          <select
            value={language}
            onChange={e => setLanguage(e.target.value)}
            className="px-3 py-2 rounded-lg border border-gray-300 text-sm"
          >
            <option value="de">DE</option>
            <option value="en">EN</option>
            <option value="fr">FR</option>
            <option value="es">ES</option>
          </select>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Testfrage eingeben..."
            className="flex-1 px-4 py-2 rounded-lg border border-gray-300 focus:border-blue-500 focus:outline-none"
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            Fragen
          </button>
        </form>
      </div>

      {/* Result */}
      {result && !result.error && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
          <div>
            <h3 className="text-sm font-medium text-gray-500 mb-1">Antwort</h3>
            <p className="text-gray-900">{result.response}</p>
          </div>

          {result.rag_used && result.sources?.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-500 mb-2">RAG-Quellen</h3>
              <div className="space-y-2">
                {result.sources.map((s: any, i: number) => (
                  <div key={i} className="flex items-center gap-3 p-2 bg-blue-50 rounded-lg text-sm">
                    <Database className="w-4 h-4 text-blue-600 flex-shrink-0" />
                    <span className="flex-1 text-blue-900">{s.source}</span>
                    <span className="text-blue-600 font-mono">
                      {(s.score * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex gap-6 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" /> {result.duration_total_ms}ms
            </span>
            <span>{result.llm_model}</span>
            {result.tokens && (
              <span>{result.tokens.prompt_tokens + result.tokens.completion_tokens} Tokens</span>
            )}
            {result.rag_used ? (
              <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded">RAG</span>
            ) : (
              <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded">Kein RAG</span>
            )}
          </div>
        </div>
      )}

      {result?.error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700">
          <AlertCircle className="w-4 h-4 inline mr-2" />
          {result.error}
        </div>
      )}

      {/* History */}
      {history.length > 1 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-sm font-medium text-gray-500 mb-3">Verlauf ({history.length})</h3>
          <div className="space-y-3 max-h-80 overflow-y-auto">
            {history.slice(1).map((h, i) => (
              <div key={i} className="p-3 bg-gray-50 rounded-lg text-sm">
                <div className="font-medium text-gray-700">{h.query}</div>
                <div className="text-gray-500 mt-1 line-clamp-2">{h.response}</div>
                <div className="flex gap-3 mt-1 text-xs text-gray-400">
                  <span>{h.duration_total_ms}ms</span>
                  {h.rag_used && <span className="text-green-600">RAG</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Chat Logs Tab ───
function ChatLogsTab({ token }: { token: string }) {
  const [logs, setLogs] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [ragOnly, setRagOnly] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const fetchLogs = useCallback(async () => {
    setLoading(true)
    try {
      const res = await tenantAdminApi.getChatLogs(token, {
        page,
        per_page: 25,
        search: search || undefined,
        rag_only: ragOnly || undefined,
      })
      setLogs(res)
    } catch (err) {
      console.error('Failed to fetch logs:', err)
    } finally {
      setLoading(false)
    }
  }, [token, page, search, ragOnly])

  useEffect(() => { fetchLogs() }, [fetchLogs])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    fetchLogs()
  }

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
        <form onSubmit={handleSearch} className="flex gap-3 items-center">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-3 text-gray-400" />
            <input
              type="text"
              placeholder="In Fragen suchen..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:border-blue-500 focus:outline-none text-sm"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={ragOnly}
              onChange={e => { setRagOnly(e.target.checked); setPage(1) }}
              className="rounded"
            />
            Nur RAG
          </label>
          <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
            Suchen
          </button>
        </form>
      </div>

      {loading ? (
        <div className="text-center py-12">
          <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-500" />
        </div>
      ) : logs?.items?.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          Keine Chat-Logs vorhanden.
        </div>
      ) : (
        <>
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 divide-y divide-gray-100">
            {logs?.items?.map((log: any) => (
              <div key={log.id}>
                <button
                  onClick={() => setExpandedId(expandedId === log.id ? null : log.id)}
                  className="w-full p-4 text-left hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-start gap-3">
                    {expandedId === log.id ? (
                      <ChevronDown className="w-4 h-4 text-gray-400 mt-1 flex-shrink-0" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-gray-400 mt-1 flex-shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs text-gray-400">
                          {new Date(log.created_at).toLocaleString('de-DE')}
                        </span>
                        {log.rag_used && (
                          <span className="px-1.5 py-0.5 bg-green-100 text-green-700 rounded text-xs">RAG</span>
                        )}
                        {log.duration_total_ms && (
                          <span className="text-xs text-gray-400">{log.duration_total_ms}ms</span>
                        )}
                      </div>
                      <p className="text-sm text-gray-900 font-medium truncate">{log.user_message}</p>
                      <p className="text-sm text-gray-500 truncate mt-0.5">{log.bot_response}</p>
                    </div>
                  </div>
                </button>

                {expandedId === log.id && (
                  <div className="px-11 pb-4 space-y-3">
                    <div>
                      <h4 className="text-xs font-medium text-gray-500 mb-1">Benutzeranfrage</h4>
                      <p className="text-sm text-gray-900 bg-gray-50 rounded-lg p-3">{log.user_message}</p>
                    </div>
                    <div>
                      <h4 className="text-xs font-medium text-gray-500 mb-1">Bot-Antwort</h4>
                      <p className="text-sm text-gray-900 bg-blue-50 rounded-lg p-3">{log.bot_response}</p>
                    </div>

                    {log.rag_sources?.length > 0 && (
                      <div>
                        <h4 className="text-xs font-medium text-gray-500 mb-1">RAG-Ergebnisse</h4>
                        <div className="space-y-1">
                          {log.rag_sources.map((s: any, i: number) => (
                            <div key={i} className="flex items-center gap-2 p-2 bg-green-50 rounded text-sm">
                              <Database className="w-3 h-3 text-green-600" />
                              <span className="flex-1">{s.source}</span>
                              <span className="font-mono text-green-700">{(s.score * 100).toFixed(0)}%</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="flex gap-4 text-xs text-gray-500 pt-2 border-t border-gray-100">
                      {log.duration_total_ms != null && (
                        <span>Gesamt: {log.duration_total_ms}ms</span>
                      )}
                      {log.duration_rag_ms != null && <span>RAG: {log.duration_rag_ms}ms</span>}
                      {log.duration_llm_ms != null && <span>LLM: {log.duration_llm_ms}ms</span>}
                      {log.tokens_prompt != null && (
                        <span>Tokens: {log.tokens_prompt + (log.tokens_completion || 0)}</span>
                      )}
                      <span>{log.llm_model}</span>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Pagination */}
          {logs && logs.pages > 1 && (
            <div className="flex items-center justify-between text-sm text-gray-500">
              <span>Seite {logs.page} von {logs.pages} ({logs.total} Einträge)</span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1 rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
                >
                  Zurück
                </button>
                <button
                  onClick={() => setPage(p => Math.min(logs.pages, p + 1))}
                  disabled={page >= logs.pages}
                  className="px-3 py-1 rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
                >
                  Weiter
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ─── Analytics Tab ───
function AnalyticsTab({ token }: { token: string }) {
  const [overview, setOverview] = useState<any>(null)
  const [docAnalytics, setDocAnalytics] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      tenantAdminApi.getAnalyticsOverview(token, days),
      tenantAdminApi.getDocumentAnalytics(token, days),
    ])
      .then(([ov, da]) => {
        setOverview(ov)
        setDocAnalytics(da)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [token, days])

  if (loading) {
    return (
      <div className="text-center py-12">
        <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-500" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Period selector */}
      <div className="flex gap-2">
        {[7, 30, 90].map(d => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={`px-4 py-2 rounded-lg text-sm ${
              days === d ? 'bg-blue-600 text-white' : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
            }`}
          >
            {d} Tage
          </button>
        ))}
      </div>

      {/* Overview cards */}
      {overview && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Anfragen gesamt" value={overview.total_queries} icon={MessageSquare} color="blue" />
          <StatCard label="RAG-Nutzung" value={`${overview.rag_usage_rate}%`} icon={Database} color="green" />
          <StatCard
            label="Ø Antwortzeit"
            value={overview.avg_response_time_ms ? `${overview.avg_response_time_ms}ms` : '—'}
            icon={Zap}
            color="yellow"
          />
          <StatCard
            label="Tokens gesamt"
            value={overview.total_tokens?.total?.toLocaleString() || '0'}
            icon={BarChart3}
            color="purple"
          />
        </div>
      )}

      {/* Document usage ranking */}
      {docAnalytics?.documents?.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold mb-4">Dokumentnutzung</h3>
          <div className="space-y-3">
            {docAnalytics.documents.map((doc: any, i: number) => {
              const maxRefs = docAnalytics.documents[0]?.total_references || 1
              const widthPct = Math.max(5, (doc.total_references / maxRefs) * 100)
              return (
                <div key={i} className="flex items-center gap-3">
                  <span className="text-sm text-gray-500 w-6 text-right">{i + 1}.</span>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-gray-900">{doc.source}</span>
                      <span className="text-sm text-gray-500">{doc.total_references}x</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500 rounded-full"
                        style={{ width: `${widthPct}%` }}
                      />
                    </div>
                    <div className="flex gap-3 mt-1 text-xs text-gray-400">
                      <span>Confidence: {(doc.avg_confidence * 100).toFixed(0)}%</span>
                      <span>Zuletzt: {new Date(doc.last_used).toLocaleDateString('de-DE')}</span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {docAnalytics?.documents?.length === 0 && (
        <div className="text-center py-8 text-gray-500 bg-white rounded-xl border border-gray-200">
          Keine Dokumentnutzung im gewählten Zeitraum.
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value, icon: Icon, color }: {
  label: string; value: string | number; icon: any; color: string
}) {
  const colorMap: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    yellow: 'bg-yellow-50 text-yellow-600',
    purple: 'bg-purple-50 text-purple-600',
  }
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
      <div className="flex items-center gap-3 mb-2">
        <div className={`p-2 rounded-lg ${colorMap[color] || colorMap.blue}`}>
          <Icon className="w-4 h-4" />
        </div>
        <span className="text-sm text-gray-500">{label}</span>
      </div>
      <div className="text-2xl font-bold text-gray-900">{value}</div>
    </div>
  )
}

// ─── Main Dashboard ───
export default function TenantAdminDashboard() {
  const navigate = useNavigate()
  const [token, setToken] = useState<string | null>(localStorage.getItem('tenant_admin_token'))
  const [user, setUser] = useState<any>(null)
  const [activeTab, setActiveTab] = useState<Tab>('test-query')

  useEffect(() => {
    if (token) {
      tenantAdminApi.me(token)
        .then(setUser)
        .catch(() => {
          localStorage.removeItem('tenant_admin_token')
          setToken(null)
        })
    }
  }, [token])

  const handleLogin = (newToken: string, userData: any) => {
    localStorage.setItem('tenant_admin_token', newToken)
    setToken(newToken)
    setUser(userData)
  }

  const handleLogout = () => {
    localStorage.removeItem('tenant_admin_token')
    setToken(null)
    setUser(null)
  }

  if (!token) {
    return <LoginForm onLogin={handleLogin} />
  }

  const tabs: { id: Tab; label: string; icon: any }[] = [
    { id: 'test-query', label: 'Test Query', icon: MessageSquare },
    { id: 'chat-logs', label: 'Chat Logs', icon: FileText },
    { id: 'analytics', label: 'Analytik', icon: BarChart3 },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-gray-900">Wissensdatenbank Admin</h1>
            {user && (
              <p className="text-xs text-gray-500">{user.display_name || user.email}</p>
            )}
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-sm text-gray-500 hover:text-red-600"
          >
            <LogOut className="w-4 h-4" />
            Abmelden
          </button>
        </div>
      </header>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 flex gap-1">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <main className="max-w-6xl mx-auto px-4 py-6">
        {activeTab === 'test-query' && <TestQueryTab token={token} />}
        {activeTab === 'chat-logs' && <ChatLogsTab token={token} />}
        {activeTab === 'analytics' && <AnalyticsTab token={token} />}
      </main>
    </div>
  )
}
