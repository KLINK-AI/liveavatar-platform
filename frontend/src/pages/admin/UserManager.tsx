/**
 * User Manager — Create, edit, and manage platform users.
 *
 * Superadmin-only page for managing:
 * - Tenant-Admin users (customer access to /tenant-admin)
 * - Superadmin users (platform operators)
 *
 * Each tenant_admin user is linked to a specific tenant and can only
 * access that tenant's data in the Kunden-Admin panel.
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft, Plus, Pencil, Trash2, X, Check, Users,
  Shield, ShieldCheck, Mail, Eye, EyeOff, UserCheck, UserX
} from 'lucide-react'
import { adminApi, tenantApi } from '../../lib/api'

interface UserData {
  id: string
  email: string
  display_name: string
  role: string
  tenant_id: string | null
  tenant_name: string | null
  is_active: boolean
  last_login: string | null
  created_at: string
}

interface TenantOption {
  id: string
  name: string
  slug: string
}

interface UserForm {
  email: string
  display_name: string
  password: string
  role: string
  tenant_id: string
}

const emptyForm: UserForm = {
  email: '',
  display_name: '',
  password: '',
  role: 'tenant_admin',
  tenant_id: '',
}

export default function UserManager() {
  const [token] = useState(() => localStorage.getItem('admin_token') || '')
  const [users, setUsers] = useState<UserData[]>([])
  const [tenants, setTenants] = useState<TenantOption[]>([])
  const [loading, setLoading] = useState(true)

  const [showCreate, setShowCreate] = useState(false)
  const [editingUser, setEditingUser] = useState<UserData | null>(null)
  const [form, setForm] = useState<UserForm>({ ...emptyForm })
  const [saving, setSaving] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

  // Load users and tenants
  useEffect(() => {
    if (!token) return
    Promise.all([
      adminApi.listUsers(token),
      tenantApi.list(token),
    ]).then(([userList, tenantList]) => {
      setUsers(userList)
      setTenants(tenantList)
    }).catch(console.error).finally(() => setLoading(false))
  }, [token])

  const refreshUsers = async () => {
    try {
      const userList = await adminApi.listUsers(token)
      setUsers(userList)
    } catch (e) {
      console.error(e)
    }
  }

  const handleCreate = async () => {
    if (!form.email || !form.password || !form.display_name) {
      alert('Bitte alle Pflichtfelder ausfüllen.')
      return
    }
    if (form.role === 'tenant_admin' && !form.tenant_id) {
      alert('Bitte einen Mandanten zuweisen.')
      return
    }
    setSaving(true)
    try {
      await adminApi.createUser({
        email: form.email,
        password: form.password,
        display_name: form.display_name,
        role: form.role,
        tenant_id: form.role === 'tenant_admin' ? form.tenant_id : undefined,
      }, token)
      setShowCreate(false)
      setForm({ ...emptyForm })
      await refreshUsers()
    } catch (e: any) {
      alert(`Fehler: ${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleEdit = (user: UserData) => {
    setEditingUser(user)
    setForm({
      email: user.email,
      display_name: user.display_name,
      password: '',
      role: user.role,
      tenant_id: user.tenant_id || '',
    })
    setShowCreate(false)
  }

  const handleUpdate = async () => {
    if (!editingUser) return
    setSaving(true)
    try {
      const data: any = {}
      if (form.email !== editingUser.email) data.email = form.email
      if (form.display_name !== editingUser.display_name) data.display_name = form.display_name
      if (form.password) data.password = form.password
      if (form.role !== editingUser.role) data.role = form.role
      if (form.role === 'tenant_admin' && form.tenant_id !== editingUser.tenant_id) {
        data.tenant_id = form.tenant_id
      }

      if (Object.keys(data).length === 0) {
        setEditingUser(null)
        return
      }

      await adminApi.updateUser(editingUser.id, data, token)
      setEditingUser(null)
      setForm({ ...emptyForm })
      await refreshUsers()
    } catch (e: any) {
      alert(`Fehler: ${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (userId: string) => {
    try {
      await adminApi.deleteUser(userId, token)
      setDeleteConfirm(null)
      await refreshUsers()
    } catch (e: any) {
      alert(`Fehler: ${e.message}`)
    }
  }

  const handleToggleActive = async (user: UserData) => {
    try {
      await adminApi.updateUser(user.id, { is_active: !user.is_active }, token)
      await refreshUsers()
    } catch (e: any) {
      alert(`Fehler: ${e.message}`)
    }
  }

  const getTenantName = (tenantId: string | null) => {
    if (!tenantId) return null
    const t = tenants.find(t => t.id === tenantId)
    return t ? t.name : tenantId.substring(0, 8) + '...'
  }

  if (!token) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">Nicht angemeldet. <a href="/admin" className="text-blue-600 underline">Zum Login</a></p>
      </div>
    )
  }

  // ─── Form Component ───
  const UserFormPanel = ({ isEdit }: { isEdit: boolean }) => (
    <div className="bg-white rounded-2xl shadow-lg p-6 mb-6 border border-blue-100">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-gray-900">
          {isEdit ? `Benutzer bearbeiten: ${editingUser?.display_name}` : 'Neuen Benutzer anlegen'}
        </h2>
        <button
          onClick={() => { setShowCreate(false); setEditingUser(null); setForm({ ...emptyForm }) }}
          className="text-gray-400 hover:text-gray-600"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Display Name */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Anzeigename *</label>
          <input
            type="text"
            value={form.display_name}
            onChange={(e) => setForm({ ...form, display_name: e.target.value })}
            placeholder="z.B. Marcus Kretschmer"
            className="w-full px-3 py-2 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {/* Email */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">E-Mail *</label>
          <input
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="admin@gemeinde.de"
            className="w-full px-3 py-2 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {/* Password */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Passwort {isEdit ? '(leer lassen = unverändert)' : '*'}
          </label>
          <div className="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              placeholder={isEdit ? 'Neues Passwort eingeben...' : 'Passwort setzen'}
              className="w-full px-3 py-2 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent pr-10"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Role */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Rolle *</label>
          <select
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
            className="w-full px-3 py-2 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="tenant_admin">Kunden-Admin</option>
            <option value="superadmin">Superadmin</option>
          </select>
        </div>

        {/* Tenant Assignment (only for tenant_admin) */}
        {form.role === 'tenant_admin' && (
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">Mandant zuweisen *</label>
            <select
              value={form.tenant_id}
              onChange={(e) => setForm({ ...form, tenant_id: e.target.value })}
              className="w-full px-3 py-2 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">— Mandant wählen —</option>
              {tenants.map(t => (
                <option key={t.id} value={t.id}>{t.name} ({t.slug})</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-2 mt-6">
        <button
          onClick={() => { setShowCreate(false); setEditingUser(null); setForm({ ...emptyForm }) }}
          className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 rounded-lg border border-gray-200"
        >
          Abbrechen
        </button>
        <button
          onClick={isEdit ? handleUpdate : handleCreate}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 text-sm text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50"
        >
          <Check className="w-4 h-4" />
          {saving ? 'Speichern...' : isEdit ? 'Aktualisieren' : 'Benutzer anlegen'}
        </button>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Link to="/admin/tenants" className="text-gray-400 hover:text-gray-600">
              <ArrowLeft className="w-6 h-6" />
            </Link>
            <h1 className="text-2xl font-bold text-gray-900">Benutzer-Verwaltung</h1>
          </div>
          <button
            onClick={() => { setShowCreate(true); setEditingUser(null); setForm({ ...emptyForm }) }}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            <Plus className="w-5 h-5" /> Neuer Benutzer
          </button>
        </div>

        {/* Create/Edit Form */}
        {showCreate && <UserFormPanel isEdit={false} />}
        {editingUser && <UserFormPanel isEdit={true} />}

        {/* User List */}
        {loading ? (
          <div className="text-center py-12 text-gray-400">Lade Benutzer...</div>
        ) : users.length === 0 ? (
          <div className="text-center py-12">
            <Users className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">Noch keine Benutzer angelegt.</p>
            <p className="text-sm text-gray-400 mt-1">Lege einen Kunden-Admin an, damit dein Kunde auf den Kunden-Admin-Bereich zugreifen kann.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {users.map(user => (
              <div
                key={user.id}
                className={`bg-white rounded-xl border p-4 ${!user.is_active ? 'opacity-60 border-gray-200' : 'border-gray-100'}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    {/* Role Icon */}
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                      user.role === 'superadmin'
                        ? 'bg-purple-100 text-purple-600'
                        : 'bg-blue-100 text-blue-600'
                    }`}>
                      {user.role === 'superadmin'
                        ? <ShieldCheck className="w-5 h-5" />
                        : <Shield className="w-5 h-5" />
                      }
                    </div>

                    {/* Info */}
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-gray-900">{user.display_name}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          user.role === 'superadmin'
                            ? 'bg-purple-100 text-purple-700'
                            : 'bg-blue-100 text-blue-700'
                        }`}>
                          {user.role === 'superadmin' ? 'Superadmin' : 'Kunden-Admin'}
                        </span>
                        {!user.is_active && (
                          <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700 font-medium">
                            Deaktiviert
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-sm text-gray-500 mt-0.5">
                        <span className="flex items-center gap-1">
                          <Mail className="w-3.5 h-3.5" /> {user.email}
                        </span>
                        {user.tenant_name && (
                          <span className="text-blue-600 font-medium">{user.tenant_name}</span>
                        )}
                        {user.last_login && (
                          <span className="text-gray-400">
                            Letzter Login: {new Date(user.last_login).toLocaleDateString('de-DE')}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleToggleActive(user)}
                      className={`p-2 rounded-lg text-sm ${
                        user.is_active
                          ? 'text-gray-400 hover:bg-gray-50 hover:text-orange-600'
                          : 'text-green-600 hover:bg-green-50'
                      }`}
                      title={user.is_active ? 'Deaktivieren' : 'Aktivieren'}
                    >
                      {user.is_active ? <UserX className="w-4 h-4" /> : <UserCheck className="w-4 h-4" />}
                    </button>
                    <button
                      onClick={() => handleEdit(user)}
                      className="p-2 text-gray-400 hover:bg-gray-50 hover:text-blue-600 rounded-lg"
                      title="Bearbeiten"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                    {deleteConfirm === user.id ? (
                      <div className="flex items-center gap-1 ml-1">
                        <button
                          onClick={() => handleDelete(user.id)}
                          className="px-2 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700"
                        >
                          Ja, löschen
                        </button>
                        <button
                          onClick={() => setDeleteConfirm(null)}
                          className="px-2 py-1 text-xs text-gray-500 hover:bg-gray-100 rounded"
                        >
                          Abbrechen
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setDeleteConfirm(user.id)}
                        className="p-2 text-gray-400 hover:bg-red-50 hover:text-red-600 rounded-lg"
                        title="Löschen"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
