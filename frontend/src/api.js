export const API = import.meta.env.VITE_API || 'http://localhost:8000'

const TOKEN_KEY = 'material-setu.token'

let token = null
try {
  // Clear any old permanent localStorage token so fresh visits always require login
  localStorage.removeItem(TOKEN_KEY)
  token = sessionStorage.getItem(TOKEN_KEY)
} catch {
  token = null
}

const listeners = new Set()

export function onAuthChange(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export function getToken() {
  return token
}

export function setToken(next) {
  token = next || null
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    /* private mode — token stays in memory only */
  }
  for (const fn of listeners) fn(token)
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function json(res) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    if (res.status === 401) setToken(null)
    throw new ApiError(body.detail || `${res.status} ${res.statusText}`, res.status)
  }
  return res.status === 204 ? null : res.json()
}

function headers(extra) {
  const h = { ...extra }
  if (token) h.Authorization = `Bearer ${token}`
  return h
}

const get = (path) => fetch(`${API}${path}`, { headers: headers() }).then(json)

const post = (path, body) =>
  fetch(`${API}${path}`, {
    method: 'POST',
    headers: headers(body === undefined ? {} : { 'Content-Type': 'application/json' }),
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then(json)

const patch = (path, body) =>
  fetch(`${API}${path}`, {
    method: 'PATCH',
    headers: headers({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  }).then(json)

const del = (path) =>
  fetch(`${API}${path}`, { method: 'DELETE', headers: headers() }).then(json)

export const api = {
  health: () => fetch(`${API}/health`).then(json),

  register: (payload) => post('/auth/register', payload),
  login: (payload) => post('/auth/login', payload),
  me: () => get('/auth/me'),
  users: () => get('/auth/users'),
  setUserRole: (id, role) => patch(`/auth/users/${id}`, { role }),

  stats: () => get('/stats'),
  materials: () => get('/materials'),
  matches: () => get('/matches'),
  nmc: () => get('/nmc'),
  opportunities: () => get('/procurement/opportunities'),
  bulkIngestProcurement: (rows) => post('/procurement/ingest', rows),
  clearProcurement: () => post('/procurement/clear'),
  audit: (limit = 60) => get(`/audit?limit=${limit}`),
  standardize: (material) => post('/materials/standardize', material),
  ingest: (material) => post('/materials/ingest', [material]),
  bulkIngest: (rows) => post('/materials/bulk-ingest', rows),
  runMatching: (threshold = 0.6) => post(`/matches/run?threshold=${threshold}`),
  decide: (id, decision, note) =>
    post(`/matches/${id}/decision`, { decision, note: note || null }),

  attachments: (materialId) => get(`/materials/${materialId}/attachments`),
  uploadAttachment: (materialId, file) => {
    const body = new FormData()
    body.append('file', file)
    return fetch(`${API}/materials/${materialId}/attachments`, {
      method: 'POST',
      headers: headers(),
      body,
    }).then(json)
  },
  deleteAttachment: (id) => del(`/attachments/${id}`),
  attachmentBlob: (id) =>
    fetch(`${API}/attachments/${id}`, { headers: headers() }).then((res) => {
      if (!res.ok) throw new ApiError('Could not load attachment', res.status)
      return res.blob()
    }),
}

export const ATTACHMENT_ACCEPT =
  'image/png,image/jpeg,image/webp,image/gif,application/pdf,' +
  'application/vnd.openxmlformats-officedocument.presentationml.presentation'

export const ATTACHMENT_MAX_BYTES = 15 * 1024 * 1024

export function formatBytes(n) {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

export const SECTORS = ['Oil & Gas', 'Power', 'Steel', 'Mining', 'Heavy Engineering']

export const FAMILIES = [
  'Bearing', 'Cable', 'Valve', 'Fastener', 'Pipe', 'Motor', 'Plate',
  'Electrical', 'Instrument', 'Gasket', 'Seal', 'Hose', 'Filter', 'Grease',
]

const SECTOR_VAR = {
  'Oil & Gas': 'var(--sector-oil)',
  Power: 'var(--sector-power)',
  Steel: 'var(--sector-steel)',
  Mining: 'var(--sector-mining)',
  'Heavy Engineering': 'var(--sector-heavy)',
}
export const sectorColor = (s) => SECTOR_VAR[s] || 'var(--sector-other)'
