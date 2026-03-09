import { Routes, Route } from 'react-router-dom'
import AvatarPage from './pages/AvatarPage'
import AdminDashboard from './pages/admin/Dashboard'
import TenantManager from './pages/admin/TenantManager'
import KnowledgeBasePage from './pages/admin/KnowledgeBase'

function App() {
  return (
    <Routes>
      {/* Public: Avatar widget (accessed via tenant slug) */}
      <Route path="/avatar/:tenantSlug" element={<AvatarPage />} />

      {/* Admin Dashboard */}
      <Route path="/admin" element={<AdminDashboard />} />
      <Route path="/admin/tenants" element={<TenantManager />} />
      <Route path="/admin/knowledge/:tenantId" element={<KnowledgeBasePage />} />

      {/* Default: Landing */}
      <Route path="/" element={
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <div className="text-center">
            <h1 className="text-4xl font-bold text-gray-900 mb-4">
              LiveAvatar Platform
            </h1>
            <p className="text-lg text-gray-600 mb-8">
              White-Label Video-Avatar Plattform mit KI-gestützter Kommunikation
            </p>
            <div className="space-x-4">
              <a href="/admin" className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                Admin Dashboard
              </a>
            </div>
          </div>
        </div>
      } />
    </Routes>
  )
}

export default App
