import axios from 'axios'

const KEY = { access: 'wf_access', refresh: 'wf_refresh', user: 'wf_user' }
export const tokens = {
  get access() { return localStorage.getItem(KEY.access) },
  get refresh() { return localStorage.getItem(KEY.refresh) },
  get user() { try { return JSON.parse(localStorage.getItem(KEY.user)) } catch { return null } },
  set({ access_token, refresh_token, user }) {
    if (access_token) localStorage.setItem(KEY.access, access_token)
    if (refresh_token) localStorage.setItem(KEY.refresh, refresh_token)
    if (user) localStorage.setItem(KEY.user, JSON.stringify(user))
  },
  clear() { Object.values(KEY).forEach((k) => localStorage.removeItem(k)) },
}

export const api = axios.create({ baseURL: '/api', timeout: 60000 })

api.interceptors.request.use((cfg) => {
  if (tokens.access) cfg.headers.Authorization = `Bearer ${tokens.access}`
  return cfg
})

// Token-expiry handling: on 401 try one silent refresh (shared across concurrent requests), then log out.
let refreshing = null
const AUTH_PATHS = ['/auth/login', '/auth/refresh', '/auth/register', '/auth/forgot-password', '/auth/reset-password']
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const cfg = error.config
    const status = error.response?.status
    const isAuthCall = AUTH_PATHS.some((p) => cfg?.url?.includes(p))
    if (status === 401 && !cfg._retry && !isAuthCall && tokens.refresh) {
      cfg._retry = true
      try {
        refreshing = refreshing || axios.post('/api/auth/refresh', { refresh_token: tokens.refresh }).finally(() => { refreshing = null })
        const { data } = await refreshing
        tokens.set(data)
        cfg.headers.Authorization = `Bearer ${data.access_token}`
        return api(cfg)
      } catch {
        tokens.clear()
        window.dispatchEvent(new Event('wf:logout'))
      }
    } else if (status === 401 && !isAuthCall) {
      tokens.clear()
      window.dispatchEvent(new Event('wf:logout'))
    }
    return Promise.reject(error)
  },
)

export function errMsg(e) {
  const d = e?.response?.data?.detail
  if (!e?.response) return e?.code === 'ECONNABORTED' ? 'Request timed out' : 'Cannot reach the server'
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((x) => `${(x.loc || []).slice(1).join('.')}: ${x.msg}`).join('; ')
  if (d?.message) return d.message + (d.missing ? `: ${d.missing.join(', ')}` : '')
  return `Request failed (${e.response.status})`
}

export async function download(path, params = {}, fallbackName = 'download') {
  const res = await api.get(path, { params, responseType: 'blob' })
  const cd = res.headers['content-disposition'] || ''
  const name = /filename="?([^";]+)"?/.exec(cd)?.[1] || fallbackName
  const url = URL.createObjectURL(res.data)
  const a = Object.assign(document.createElement('a'), { href: url, download: name })
  document.body.appendChild(a); a.click(); a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}

export const fmt = {
  money: (v) => (v == null ? '–' : Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })),
  money2: (v) => (v == null ? '–' : Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })),
  pct: (v, d = 0) => (v == null ? '–' : `${(v * 100).toFixed(d)}%`),
  date: (v) => (v ? new Date(v.endsWith?.('Z') || v.length <= 10 ? v : v + 'Z').toLocaleDateString() : '–'),
  dt: (v) => (v ? new Date(typeof v === 'string' && v.length > 10 && !v.endsWith('Z') ? v + 'Z' : v).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '–'),
  ago(v) {
    if (!v) return ''
    const t = new Date(typeof v === 'string' && v.length > 10 && !v.endsWith('Z') ? v + 'Z' : v).getTime()
    const s = Math.max(0, (Date.now() - t) / 1000)
    if (s < 60) return 'just now'
    if (s < 3600) return `${Math.floor(s / 60)}m ago`
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`
    return `${Math.floor(s / 86400)}d ago`
  },
}
