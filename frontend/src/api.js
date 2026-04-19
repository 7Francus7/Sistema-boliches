import { getKV } from './db.js'

const BASE = import.meta.env.VITE_API_BASE || ''

async function request(path, { method = 'GET', body, auth = true, raw = false } = {}) {
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
  return raw ? res.text() : res.json()
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

  // Turnos
  openShift: (device_id, event_id, opening_cash) =>
    request('/shifts/open', { method: 'POST', body: { device_id, event_id, opening_cash } }),
  closeShift: (shift_id, closing_cash, notes) =>
    request(`/shifts/${shift_id}/close`, { method: 'POST', body: { closing_cash, notes } }),
  currentShift: (device_id) =>
    request(`/shifts/current?device_id=${device_id}`),
  listShifts: () => request('/shifts'),
  shiftCloseReport: (shift_id) => request(`/analytics/shift-close/${shift_id}`),

  // Cashless
  createTab: (code, holder_name, initial_load) =>
    request('/tabs', { method: 'POST', body: { code, holder_name, initial_load } }),
  loadTab: (tab_id, amount) =>
    request(`/tabs/${tab_id}/load`, { method: 'POST', body: { amount } }),
  tabByCode: (code) => request(`/tabs/by-code/${encodeURIComponent(code)}`),
  closeTab: (tab_id) => request(`/tabs/${tab_id}/close`, { method: 'POST' }),
  listTabs: (status) => request(`/tabs${status ? `?status_filter=${status}` : ''}`),

  // Promoters
  listPromoters: () => request('/promoters'),
  createPromoter: (p) => request('/promoters', { method: 'POST', body: p }),
  togglePromoter: (id) =>
    request(`/promoters/${id}/toggle`, { method: 'POST' }),
  attributeTicket: (promoter_id, ticket_id) =>
    request(`/promoters/${promoter_id}/attribute-ticket`, { method: 'POST', body: { ticket_id } }),
  commissions: () => request('/analytics/commissions'),

  // Suppliers / Purchases
  listSuppliers: () => request('/suppliers'),
  createSupplier: (s) => request('/suppliers', { method: 'POST', body: s }),
  createPurchase: (p) => request('/purchases', { method: 'POST', body: p }),
  listPurchases: () => request('/purchases'),

  // Alertas
  lowStock: () => request('/analytics/low-stock'),
  salesCsv: () => request('/analytics/sales.csv', { raw: true }),
}
