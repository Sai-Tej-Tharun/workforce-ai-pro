import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import axios from 'axios'
import { api, tokens } from '../api'
import { useAuth } from './AuthContext'
import { CheckCircle2, AlertTriangle, Info, XCircle, Bell } from 'lucide-react'

const Ctx = createContext(null)
export const useApp = () => useContext(Ctx)

/** Subscribe to realtime WebSocket events of one or more types. */
export function useLive(types, handler) {
  const { subscribe } = useApp()
  const ref = useRef(handler)
  ref.current = handler
  useEffect(() => subscribe([].concat(types), (m) => ref.current(m)), [subscribe]) // eslint-disable-line react-hooks/exhaustive-deps
}

const ICONS = { success: CheckCircle2, error: XCircle, warning: AlertTriangle, info: Info, alert: Bell }
const TONE = {
  success: 'border-emerald-200 bg-emerald-50 text-emerald-800', error: 'border-rose-200 bg-rose-50 text-rose-800',
  warning: 'border-amber-200 bg-amber-50 text-amber-800', info: 'border-sky-200 bg-sky-50 text-sky-800',
  alert: 'border-indigo-200 bg-indigo-50 text-indigo-800',
}

export function AppProvider({ children }) {
  const { user } = useAuth()
  const [toasts, setToasts] = useState([])
  const [unread, setUnread] = useState(0)
  const [wsState, setWsState] = useState('offline')
  const listeners = useRef(new Set())

  const toast = useCallback((message, type = 'info', title) => {
    const id = Math.random().toString(36).slice(2)
    setToasts((t) => [...t.slice(-3), { id, message, type, title }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5000)
  }, [])

  const subscribe = useCallback((types, fn) => {
    const l = { types, fn }
    listeners.current.add(l)
    return () => listeners.current.delete(l)
  }, [])

  const refreshUnread = useCallback(() => {
    if (!tokens.access) return
    api.get('/notifications/unread-count').then(({ data }) => setUnread(data.unread)).catch(() => {})
  }, [])

  useEffect(() => {
    if (!user) { setUnread(0); return }
    refreshUnread()
    let ws, timer, ping, stopped = false, attempt = 0
    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/api/ws?token=${tokens.access}`)
      ws.onopen = () => { attempt = 0; setWsState('live'); ping = setInterval(() => ws.readyState === 1 && ws.send('ping'), 25000) }
      ws.onmessage = (ev) => {
        let m; try { m = JSON.parse(ev.data) } catch { return }
        if (m.type === 'notification') {
          setUnread((n) => n + 1)
          const p = m.data.priority
          toast(m.data.message, p === 'critical' || p === 'high' ? 'warning' : 'alert', m.data.title)
        }
        listeners.current.forEach((l) => l.types.includes(m.type) && l.fn(m))
      }
      ws.onclose = async (ev) => {
        clearInterval(ping); setWsState('offline')
        if (stopped) return
        if (ev.code === 4401 && tokens.refresh) {  // token expired -> refresh then reconnect
          try { const { data } = await axios.post('/api/auth/refresh', { refresh_token: tokens.refresh }); tokens.set(data) } catch { return }
        }
        timer = setTimeout(connect, Math.min(1000 * 2 ** attempt++, 15000))
      }
    }
    connect()
    return () => { stopped = true; clearTimeout(timer); clearInterval(ping); ws && ws.close() }
  }, [user?.id, toast, refreshUnread]) // eslint-disable-line react-hooks/exhaustive-deps

  const value = useMemo(() => ({ toast, unread, setUnread, refreshUnread, subscribe, wsState }), [toast, unread, refreshUnread, subscribe, wsState])
  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="fixed right-4 top-4 z-[100] flex w-80 flex-col gap-2" role="status" aria-live="polite">
        {toasts.map((t) => {
          const Icon = ICONS[t.type] || Info
          return (
            <div key={t.id} className={`toast-in flex gap-2.5 rounded-lg border p-3 shadow-lg ${TONE[t.type] || TONE.info}`}>
              <Icon size={18} className="mt-0.5 shrink-0" />
              <div className="min-w-0 text-sm">{t.title && <div className="font-semibold">{t.title}</div>}<div className="break-words">{t.message}</div></div>
            </div>
          )
        })}
      </div>
    </Ctx.Provider>
  )
}
