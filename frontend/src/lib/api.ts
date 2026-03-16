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

  // Session creation can take up to 90s (LiveAvatar API is slow).
  // Use AbortController to prevent infinite hangs.
  const isSessionCreate = endpoint === '/sessions/' && method === 'POST'
  const controller = new AbortController()
  const timeoutMs = isSessionCreate ? 90000 : 30000
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
  } catch (e: any) {
    if (e.name === 'AbortError') {
      throw new Error(
        isSessionCreate
          ? 'Avatar-Server antwortet nicht. Bitte versuchen Sie es erneut.'
          : 'Anfrage hat zu lange gedauert.'
      )
    }
    throw e
  } finally {
    clearTimeout(timeoutId)
  }
}

/**
 * Upload a file via multipart/form-data (for document uploads).
 */
async function apiUpload(endpoint: string, file: File, token: string) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
    body: formData,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

// --- Session API ---
export const sessionApi = {
  create: (apiKey: string, options?: { avatarId?: string; language?: string }) =>
    apiRequest('/sessions/', {
      method: 'POST',
      apiKey,
      body: {
        avatar_id: options?.avatarId,
        language: options?.language || 'de',
      },
    }),

  get: (sessionId: string, apiKey: string) =>
    apiRequest(`/sessions/${sessionId}`, { apiKey }),

  stop: (sessionId: string, apiKey: string) =>
    apiRequest(`/sessions/${sessionId}/stop`, { method: 'POST', apiKey }),

  keepAlive: (sessionId: string, apiKey: string) =>
    apiRequest(`/sessions/${sessionId}/keep-alive`, { method: 'POST', apiKey }),

  sendGreeting: (sessionId: string, apiKey: string, language: string) =>
    apiRequest(`/sessions/${sessionId}/greeting?language=${language}`, {
      method: 'POST',
      apiKey,
    }),
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
  list: (token: string) =>
    apiRequest('/knowledge/', { token }),

  create: (name: string, description: string, token: string) =>
    apiRequest('/knowledge/', {
      method: 'POST',
      token,
      body: { name, description },
    }),

  listDocuments: (kbId: string, token: string) =>
    apiRequest(`/knowledge/${kbId}/documents`, { token }),

  uploadDocument: (kbId: string, file: File, token: string) =>
    apiUpload(`/knowledge/${kbId}/documents`, file, token),

  indexUrl: (kbId: string, url: string, crawlSite: boolean, token: string) =>
    apiRequest(`/knowledge/${kbId}/urls`, {
      method: 'POST',
      token,
      body: { url, crawl_site: crawlSite },
    }),

  deleteDocument: (kbId: string, docId: string, token: string) =>
    apiRequest(`/knowledge/${kbId}/documents/${docId}`, {
      method: 'DELETE',
      token,
    }),

  search: (kbId: string, query: string, token: string) =>
    apiRequest(`/knowledge/${kbId}/search`, {
      method: 'POST',
      token,
      body: { query },
    }),
}

// --- Admin API ---
export const adminApi = {
  login: (username: string, password: string) =>
    apiRequest('/admin/auth/token', {
      method: 'POST',
      body: { username, password },
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
