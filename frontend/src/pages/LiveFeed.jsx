import { useEffect, useState } from 'react'
import { Radio, Activity, AlertTriangle, Info, Siren } from 'lucide-react'
import { api, fmt } from '../api'
import { useApp, useLive } from '../context/AppContext'
import { useFetch } from '../hooks/useFetch'
import { Card, PageHeader, Badge, Select, Loading, Empty, StatCard, cx } from '../components/ui'

const ICON = { info: Info, warning: AlertTriangle, critical: Siren }
const TONE = { info: 'text-sky-500 bg-sky-50', warning: 'text-amber-500 bg-amber-50', critical: 'text-rose-600 bg-rose-50' }
export default function LiveFeed() {
  const { wsState } = useApp()
  const [sev, setSev] = useState('')
  const [items, setItems] = useState([])
  const [fresh, setFresh] = useState(new Set())
  const feed = useFetch('/monitoring/feed', { limit: 60, severity: sev || undefined })
  useEffect(() => { if (feed.data) setItems(feed.data) }, [feed.data])
  useLive(['activity'], ({ data }) => {
    if (sev && data.severity !== sev) return
    setItems((l) => [data, ...l.filter((x) => x.id !== data.id)].slice(0, 100))
    setFresh((s) => new Set(s).add(data.id)); setTimeout(() => setFresh((s) => { const n = new Set(s); n.delete(data.id); return n }), 4000)
  })
  const counts = items.reduce((a, x) => ({ ...a, [x.severity]: (a[x.severity] || 0) + 1 }), {})
  const scan = async () => { await api.post('/monitoring/instability/scan').catch(() => {}); feed.reload() }
  return (
    <div>
      <PageHeader title="Live Workforce Feed" subtitle="Real-time stream of employee activity, risk alerts and system events (WebSocket)"
        actions={<><Badge tone={wsState === 'live' ? 'low' : 'terminated'}><Radio size={11} className="mr-1" />{wsState === 'live' ? 'streaming' : 'offline – polling disabled'}</Badge><Select className="!w-36" placeholder="All severities" options={['info', 'warning', 'critical']} value={sev} onChange={(e) => setSev(e.target.value)} /></>} />
      <div className="mb-5 grid gap-4 sm:grid-cols-3"><StatCard label="Events shown" value={items.length} icon={Activity} /><StatCard label="Warnings" value={counts.warning || 0} icon={AlertTriangle} tone="amber" /><StatCard label="Critical" value={counts.critical || 0} icon={Siren} tone="rose" /></div>
      <Card pad={false}>{feed.loading && !items.length ? <Loading /> : !items.length ? <Empty title="No events yet" hint="Check-ins, leave requests, simulated activity and AI alerts appear here instantly." /> :
        <ul className="divide-y divide-slate-100">{items.map((e) => { const I = ICON[e.severity] || Info; return (
          <li key={e.id} className={cx('flex items-start gap-3 px-5 py-3 transition-colors', fresh.has(e.id) && 'bg-brand-50')}>
            <div className={cx('mt-0.5 rounded-lg p-1.5', TONE[e.severity])}><I size={16} /></div>
            <div className="min-w-0 flex-1"><div className="text-sm text-slate-800">{e.description}</div><div className="mt-0.5 flex items-center gap-2 text-xs text-slate-400"><Badge tone="info">{e.event_type}</Badge>{fmt.ago(e.created_at)}</div></div></li>) })}</ul>}</Card>
    </div>
  )
}
