/**
 * Admin Dashboard — Overview of the platform.
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Users, MessageCircle, Video, BarChart3, LogOut } from 'lucide-react'
import { adminApi, tenantApi } from '../../lib/api'

export default function AdminDashboard() {
  const [token, setToken] = useState(() => localStorage.getItem('admin_token') || '')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [stats, setStats] = useState<any>(null)
  const [tenants, setTenants] = useState<any[]>([])
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [loginError, setLoginError] = useState('')

  const handleLogin = async () => {
    setLoginError('')
    try {
      const result = await adminApi.login(username, password)
      setToken(result.access_token)
      localStorage.setItem('admin_token', result.access_token)
      setIsLoggedIn(true)
    } catch (e: any) {
      setLoginError('Benutzername oder Passwort falsch.')
    }
  }

  const handleLogout = () => {
    setToken('')
    localStorage.removeItem('admin_token')
    setIsLoggedIn(false)
    setStats(null)
    setTenants([])
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleLogin()
  }

  useEffect(() => {
    if (token) {
      setIsLoggedIn(true)
      adminApi.getStats(token).then(setStats).catch(() => {
        // Token expired or invalid — force re-login
        handleLogout()
      })
      tenantApi.list(token).then(setTenants).catch(console.error)
    }
  }, [token])

  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-md">
          <h1 className="text-2xl font-bold mb-2">Admin Login</h1>
          <p className="text-gray-500 mb-6 text-sm">LiveAvatar Platform Administration</p>
          {loginError && (
            <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
              {loginError}
            </div>
          )}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Benutzername</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Benutzername"
                className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:border-blue-500 outline-none"
                autoFocus
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Passwort</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Passwort"
                className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:border-blue-500 outline-none"
              />
            </div>
            <button
              onClick={handleLogin}
              className="w-full py-3 rounded-xl bg-blue-600 text-white font-medium hover:bg-blue-700"
            >
              Anmelden
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sidebar */}
      <div className="flex">
        <aside className="w-64 min-h-screen bg-white border-r border-gray-200 p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-8">LiveAvatar</h2>
          <nav className="space-y-2">
            <Link to="/admin" className="flex items-center gap-3 px-4 py-2 rounded-lg bg-blue-50 text-blue-600">
              <BarChart3 className="w-5 h-5" /> Dashboard
            </Link>
            <Link to="/admin/tenants" className="flex items-center gap-3 px-4 py-2 rounded-lg text-gray-600 hover:bg-gray-50">
              <Users className="w-5 h-5" /> Mandanten
            </Link>
          </nav>
          <div className="mt-auto pt-8">
            <button
              onClick={handleLogout}
              className="flex items-center gap-3 px-4 py-2 rounded-lg text-gray-500 hover:bg-gray-50 w-full text-sm"
            >
              <LogOut className="w-4 h-4" /> Abmelden
            </button>
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 p-8">
          <h1 className="text-2xl font-bold text-gray-900 mb-8">Dashboard</h1>

          {/* Stats Cards */}
          {stats && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
              <StatCard
                icon={<Users className="w-6 h-6" />}
                label="Mandanten"
                value={stats.tenants}
                color="blue"
              />
              <StatCard
                icon={<Video className="w-6 h-6" />}
                label="Gesamt Sessions"
                value={stats.total_sessions}
                color="green"
              />
              <StatCard
                icon={<Video className="w-6 h-6" />}
                label="Aktive Sessions"
                value={stats.active_sessions}
                color="yellow"
              />
              <StatCard
                icon={<MessageCircle className="w-6 h-6" />}
                label="Nachrichten"
                value={stats.total_messages}
                color="purple"
              />
            </div>
          )}

          {/* Tenant List */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-lg font-semibold">Mandanten</h2>
            </div>
            <div className="divide-y divide-gray-200">
              {tenants.map((tenant) => (
                <div key={tenant.id} className="p-6 flex items-center justify-between">
                  <div>
                    <h3 className="font-medium text-gray-900">{tenant.name}</h3>
                    <p className="text-sm text-gray-500">
                      {tenant.slug} | {tenant.llm_provider}/{tenant.llm_model}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                      tenant.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                    }`}>
                      {tenant.is_active ? 'Aktiv' : 'Inaktiv'}
                    </span>
                    <Link
                      to={`/avatar/${tenant.slug}`}
                      className="px-3 py-1 text-sm text-blue-600 hover:bg-blue-50 rounded-lg"
                    >
                      Avatar testen
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}

function StatCard({ icon, label, value, color }: {
  icon: React.ReactNode
  label: string
  value: number
  color: string
}) {
  const colorClasses: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    yellow: 'bg-yellow-50 text-yellow-600',
    purple: 'bg-purple-50 text-purple-600',
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className={`inline-flex p-3 rounded-lg mb-3 ${colorClasses[color]}`}>
        {icon}
      </div>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      <p className="text-sm text-gray-500">{label}</p>
    </div>
  )
}
