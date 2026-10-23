import { useState } from 'react'
import { ShieldAlert, Activity, Users, KeyRound } from 'lucide-react'
import { fmt } from '../api'
import { useFetch, useDebounced } from '../hooks/useFetch'
import { Card, PageHeader, DataTable, Pagination, Badge, Select, Input, StatCard, Modal, Tabs } from '../components/ui'

const TONE = { DELETE: 'high', LOGIN_FAILED: 'high', TERMINATE: 'high', CREATE: 'low', LOGIN: 'info', UPDATE: 'medium', EXPORT: 'info', TRAIN: 'info' }
export default function AuditLogs() {
  const [f, setF] = useState({ action: '', entity: '', search: '', date_from: '', date_to: '' })
  const [page, setPage] = useState(1)
  const [days, setDays] = useState(7)
  const [view, setView] = useState(null)
  const search = useDebounced(f.search)
  const logs = useFetch('/audit', { ...Object.fromEntries(Object.entries({ ...f, search }).filter(([, v]) => v)), page, size: 20 })
  const sum = useFetch('/audit/summary', { days })
  const s = sum.data
  const set = (k) => (e) => { setF({ ...f, [k]: e.target.value }); setPage(1) }
  return (
    <div>
      <PageHeader title="Audit Logs" subtitle="User activity, system audit trail and change monitoring" actions={<Select className="!w-36" options={[{ value: 1, label: 'Last 24h' }, { value: 7, label: 'Last 7 days' }, { value: 30, label: 'Last 30 days' }]} value={days} onChange={(e) => setDays(Number(e.target.value))} />} />
      {s && <div className="mb-5 grid gap-4 sm:grid-cols-3"><StatCard label="Events" value={s.by_action.reduce((a, x) => a + x.count, 0)} icon={Activity} /><StatCard label="Failed logins" value={s.failed_logins} icon={KeyRound} tone={s.failed_logins ? 'rose' : 'emerald'} /><StatCard label="Most active user" value={s.top_users[0]?.user?.split('@')[0] || '–'} hint={s.top_users[0] ? `${s.top_users[0].count} actions` : ''} icon={Users} tone="sky" /></div>}
      <Card pad={false}>
        <div className="flex flex-wrap gap-3 border-b border-slate-100 p-4">
          <Input className="!w-56" placeholder="Search user / record id…" value={f.search} onChange={set('search')} />
          <Select className="!w-40" placeholder="Any action" options={['LOGIN', 'LOGIN_FAILED', 'CREATE', 'UPDATE', 'DELETE', 'TERMINATE', 'EXPORT', 'TRAIN', 'UPLOAD', 'DOWNLOAD', 'APPROVE', 'REJECT', 'ACTIVITY']} value={f.action} onChange={set('action')} />
          <Select className="!w-44" placeholder="Any entity" options={['employee', 'user', 'department', 'leave_request', 'payroll', 'document', 'dataset', 'ml_model', 'intervention', 'task', 'report']} value={f.entity} onChange={set('entity')} />
          <Input className="!w-40" type="date" value={f.date_from} onChange={set('date_from')} /><Input className="!w-40" type="date" value={f.date_to} onChange={set('date_to')} /></div>
        <DataTable loading={logs.loading} rows={logs.data?.items} onRowClick={(r) => r.changes && setView(r)} columns={[
          { key: 'created_at', label: 'Time', render: (r) => fmt.dt(r.created_at) }, { key: 'user_email', label: 'User', render: (r) => r.user_email || <span className="text-slate-400">anonymous</span> },
          { key: 'action', label: 'Action', render: (r) => <Badge tone={TONE[r.action] || 'info'}>{r.action}</Badge> }, { key: 'entity', label: 'Entity', render: (r) => `${r.entity}${r.entity_id ? ` #${r.entity_id}` : ''}` },
          { key: 'changes', label: 'Changes', render: (r) => r.changes ? <span className="text-xs text-brand-600">{Object.keys(r.changes).slice(0, 3).join(', ')} →</span> : '–' }, { key: 'ip_address', label: 'IP', render: (r) => <span className="text-xs text-slate-400">{r.ip_address}</span> }]} />
        <Pagination page={page} size={20} total={logs.data?.total} onPage={setPage} /></Card>
      {view && <Modal open onClose={() => setView(null)} title={`${view.action} ${view.entity} #${view.entity_id ?? ''}`}>
        <div className="mb-2 text-xs text-slate-400">{fmt.dt(view.created_at)} · {view.user_email} · {view.ip_address}</div>
        <pre className="max-h-80 overflow-auto rounded-lg bg-slate-900 p-4 text-xs text-emerald-200">{JSON.stringify(view.changes, null, 2)}</pre></Modal>}
    </div>
  )
}
