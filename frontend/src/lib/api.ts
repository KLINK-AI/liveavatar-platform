/**
 * API client for the LiveAvatar Platform backend.
 */

const API_BASE = '/api/v1'

interface RequestOptions {
  method?: string
  body?: any
  apiKey?: string
  token?: string
}

async function apiRequest(endpoint: string, options: RequestOptions = {}) {
  const { method = 'GET', body, apiKey, token } = options

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  if (apiKey) headers['X-API-Key'] = apiKey
  if (token) headers['Authorization'] = `Bearer ${token}`

  const response = await fetch(`${API_BASE}${endpoint}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

// --- Session API ---
export const sessionApi = {
  create: (apiKey: string, avatarId?: string) =>
    apiRequest('/sessions/', {
      method: 'POST',
      apiKey,
      body: { avatar_id: avatarId },
    }),

  get: (sessionId: string, apiKey: string) =>
    apiRequest(`/sessions/${sessionId}`, { apiKey }),

  stop: (sessionId: string, apiKey: string) =>
    apiRequest(`/sessions/${sessionId}/stop`, { method: 'POST', apiKey }),

  keepAlive: (sessionId: string, apiKey: string) =>
    apiRequest(`/sessions/${sessionId}/keep-alive`, { method: 'POST', apiKey }),
}

// --- Conversation API ---
export const conversationApi = {
  sendMessage: (sessionId: string, message: string, apiKey: string) =>
    apiRequest(`/conversations/${sessionId}/message`, {
      method: 'POST',
      apiKey,
      body: { message, send_to_avatar: true },
    }),

  getHistory: (sessionId: string, apiKey: string) =>
    apiRequest(`/conversations/${sessionId}/history`, { apiKey }),
}

// --- Tenant API ---
export const tenantApi = {
  getBySlug: (slug: string) =>
    apiRequest(`/tenants/by-slug/${slug}`),

  list: (token: string) =>
    apiRequest('/tenants/', { token }),

  create: (data: any, token: string) =>
    apiRequest('/tenants/', { method: 'POST', token, body: data }),

  update: (id: string, data: any, token: string) =>
    apiRequest(`/tenants/${id}`, { method: 'PUT', token, body: data }),
}

// --- Knowledge Base API ---
export const knowledgeApi = {
  list: (apiKey: string) =>
    apiRequest('/knowledge/', { apiKey }),

  create: (name: string, description: string, apiKey: string) =>
    apiRequest('/knowledge/', {
      method: 'POST',
      apiKey,
      body: { name, description },
    }),

  listDocuments: (kbId: string, apiKey: string) =>
    apiRequest(`/knowledge/${kbId}/documents`, { apiKey }),

  indexUrl: (kbId: string, url: string, crawlSite: boolean, apiKey: string) =>
    apiRequest(`/knowledge/${kbId}/urls`, {
      method: 'POST',
      apiKey,
      body: { url, crawl_site: crawlSite },
    }),

  deleteDocument: (kbId: string, docId: string, apiKey: string) =>
    apiRequest(`/knowledge/${kbId}/documents/${docId}`, {
      method: 'DELETE',
      apiKey,
    }),

  search: (kbId: string, query: string, apiKey: string) =>
    apiRequest(`/knowledge/${kbId}/search`, {
      method: 'POST',
      apiKey,
      body: { query },
    }),
}

// --- Admin API ---
export const adminApi = {
  login: (slug: string, apiKey: string) =>
    apiRequest('/admin/auth/token', {
      method: 'POST',
      body: { tenant_slug: slug, api_key: apiKey },
    }),

  getStats: (token: string) =>
    apiRequest('/admin/stats', { token }),

  getTenantStats: (slug: string, token: string) =>
    apiRequest(`/admin/stats/${slug}`, { token }),
}

// --- WebSocket for streaming ---
export function createConversationSocket(
  sessionId: string,
  apiKey: string,
  onToken: (token: string) => void,
  onAvatarSent: (sentence: string) => void,
  onDone: (fullResponse: string) => void,
  onError: (error: string) => void,
) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const ws = new WebSocket(
    `${protocol}//${window.location.host}/api/v1/conversations/${sessionId}/stream`
  )

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    switch (data.type) {
      case 'token':
        onToken(data.content)
        break
      case 'avatar_sent':
        onAvatarSent(data.sentence)
        break
      case 'done':
        onDone(data.full_response)
        break
      case 'error':
        onError(data.message)
        break
    }
  }

  return {
    send: (message: string) => {
      ws.send(JSON.stringify({ message, api_key: apiKey }))
    },
    close: () => ws.close(),
  }
}
