import { getKV } from './db.js'

const BASE = import.meta.env.VITE_API_BASE || ''

async function request(path, { method = 'GET', body, auth = true } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (auth) {
    const token = await getKV('token')
    if (token) headers.Authorization = `Bearer ${token}`
  }
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`${res.status}: ${text || res.statusText}`)
  }
  return res.json()
}

export const api = {
  login: (email, password) => request('/auth/login', { method: 'POST', body: { email, password }, auth: false }),
  bootstrap: () => request('/bootstrap'),
  syncBatch: (deviceId, ops) => request('/sync/batch', { method: 'POST', body: { device_id: deviceId, ops } }),
  dashboard: () => request('/analytics/dashboard'),
}
