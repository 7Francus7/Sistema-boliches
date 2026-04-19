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

  registerDevice: (label, type) =>
    request('/devices/register', { method: 'POST', body: { label, type } }),
  heartbeat: (deviceId) =>
    request('/devices/heartbeat', { method: 'POST', body: { device_id: deviceId } }),

  listProducts: () => request('/products'),
  createProduct: (p) => request('/products', { method: 'POST', body: p }),
  updateProduct: (id, p) => request(`/products/${id}`, { method: 'PUT', body: p }),
  adjustStock: (id, qty_delta, reason) =>
    request(`/products/${id}/stock`, { method: 'POST', body: { qty_delta, reason } }),
}
