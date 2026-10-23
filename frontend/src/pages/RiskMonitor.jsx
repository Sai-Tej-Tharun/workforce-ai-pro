import { useState } from 'react'
import { Zap, TrendingUp, TrendingDown, ArrowRight } from 'lucide-react'
import { api, errMsg, fmt } from '../api'
import { useApp, useLive } from '../context/AppContext'
import { useFetch } from '../hooks/useFetch'
import { Card, PageHeader, StatCard, DataTable, Pagination, RiskBadge, Badge, Select, Field, Input, Modal, ErrorBox, Empty, RiskBar, Tabs } from '../components/ui'
import { ShieldAlert, Bell, Activity } from 'lucide-react'

const EVENTS = [
  ['overtime_spike', 'Overtime spike (hours)', 4], ['satisfaction_drop', 'Satisfaction drop (levels)', 2], ['unplanned_absence', 'Unplanned absence', null],
  ['late_arrival', 'Late arrival', null], ['promotion_denied', 'Promotion denied (years added)', 2], ['salary_change', 'Salary change (%)', -10], ['training_completed', 'Training completed', null], ['manager_change', 'Manager change', null]]

function Simulator({ onClose, onDone }) {
  const { toast } = useApp()
  const emps = useFetch('/employees', { size: 200, status: 'active' })
  const [f, setF] = useState({ employee_id: '', event_type: 'overtime_spike', value: 4 })
  const [res, setRes] = useState(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const ev = EVENTS.find((e) => e[0] === f.event_type)
  const run = async () => {
    setBusy(true); setErr(''); setRes(null)
    try { const { data } = await api.post('/monitoring/activity', { employee_id: Number(f.employee_id), event_type: f.event_type, value: ev[2] === null ? undefined : Number(f.value) }); setRes(data); onDone(); if (data.alerts_created) toast('High-risk alert triggered', 'warning') } catch (x) { setErr(errMsg(x)) } finally { setBusy(false) }
  }
  return (
    <Modal open onClose={onClose} wide title="Simulate employee activity" footer={<button className="btn-ghost" onClick={onClose}>Close</button>}>
      <p className="mb-4 text-sm text-slate-500">Triggers the full pipeline: activity → risk recalculation → high-risk detection → HR alert → intervention → monitoring log → dashboards.</p>
      <div className="grid gap-3 sm:grid-cols-4"><div className="sm:col-span-2"><Field label="Employee"><Select placeholder="Select…" options={(emps.data?.items || []).map((e) => ({ value: e.id, label: `${e.first_name} ${e.last_name} – ${e.risk_level ? Math.round(e.risk_score * 100) + '%' : 'n/a'}` }))} value={f.employee_id} onChange={(e) => setF({ ...f, employee_id: e.target.value })} /></Field></div>
        <Field label="Activity"><Select options={EVENTS.map(([v, l]) => ({ value: v, label: l.replace(/ \(.*\)/, '') }))} value={f.event_type} onChange={(e) => setF({ ...f, event_type: e.target.value, value: EVENTS.find((x) => x[0] === e.target.value)[2] ?? '' })} /></Field>
        {ev[2] !== null ? <Field label={ev[1].match(/\((.*)\)/)?.[1]}><Input type="number" step="any" value={f.value} onChange={(e) => setF({ ...f, value: e.target.value })} /></Field> : <div />}</div>
      <button className="btn-primary mt-4" disabled={!f.employee_id || busy} onClick={run}><Zap size={15} />{busy ? 'Processing…' : 'Apply activity'}</button>
      <div className="mt-3"><ErrorBox error={err} /></div>
      {res && <div className="mt-4 space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm">
        <div className="text-slate-500">Effect: {res.effect}</div>
        <div className="flex items-center gap-3 text-base">{res.before ? <RiskBadge level={res.before.level} score={res.before.score} /> : 'new'}<ArrowRight size={16} /><RiskBadge level={res.after.risk_level} score={res.after.risk_score} /></div>
        {res.after.top_factors.length > 0 && <div className="flex flex-wrap gap-1">{res.after.top_factors.map((x) => <Badge key={x.feature} tone="info">{x.label} +{x.impact}</Badge>)}</div>}
        {res.alerts_created > 0 ? <div className="font-medium text-rose-600">⚠ {res.alerts_created} alert(s) raised · intervention workflow initiated · HR notified</div> : <div className="text-slate-500">No new alerts.</div>}</div>}
    </Modal>
  )
}

export default function RiskMonitor() {
  const [tab, setTab] = useState('high')
  const [days, setDays] = useState(7)
  const [page, setPage] = useState(1)
  const [sim, setSim] = useState(false)
  const high = useFetch('/monitoring/high-risk', { limit: 50 })
  const changes = useFetch('/monitoring/risk-changes', { days })
  const logs = useFetch('/monitoring/logs', { page, size: 15 })
  const inst = useFetch('/monitoring/instability')
  const alerts = useFetch('/alerts', { status: 'open', size: 1 })
  const reloadAll = () => { high.reload(); changes.reload(); logs.reload(); inst.reload(); alerts.reload() }
  useLive(['risk_update'], reloadAll)
  const mv = (rows, up) => (rows?.length ? rows.map((r) => <div key={r.employee_id} className="flex items-center justify-between border-b border-slate-50 py-2 text-sm"><span className="font-medium">{r.employee_name}</span>
    <span className="flex items-center gap-2 text-slate-500">{fmt.pct(r.start)} → {fmt.pct(r.end)}<b className={up ? 'text-rose-600' : 'text-emerald-600'}>{up ? '+' : ''}{(r.delta * 100).toFixed(1)} pts</b></span></div>) : <Empty title="No movement" />)
  return (
    <div>
      <PageHeader title="Risk Monitor" subtitle="High-risk watchlist, risk change tracking, instability detection and monitoring logs" actions={<button className="btn-primary" onClick={() => setSim(true)}><Zap size={15} />Simulate activity</button>} />
      <div className="mb-5 grid gap-4 sm:grid-cols-3">
        <StatCard label="High-risk employees" value={high.data?.length} icon={ShieldAlert} tone="rose" /><StatCard label="Open alerts" value={alerts.data?.total} icon={Bell} tone="amber" />
        <StatCard label="Unstable departments" value={inst.data?.length} hint="late / absence / overtime / risk spikes" icon={Activity} tone={inst.data?.length ? 'rose' : 'emerald'} /></div>
      {inst.data?.length > 0 && <Card title="Workforce instability detected" className="mb-5"><div className="space-y-2">{inst.data.map((d) => <div key={d.department_id} className="flex gap-3 rounded-lg bg-rose-50 p-3 text-sm"><Badge tone={d.severity}>{d.severity}</Badge><div><b>{d.department}</b><ul className="list-inside list-disc text-slate-600">{d.signals.map((s) => <li key={s}>{s}</li>)}</ul></div></div>)}</div></Card>}
      <Tabs value={tab} onChange={setTab} tabs={[{ value: 'high', label: 'High-risk watchlist', count: high.data?.length }, { value: 'changes', label: 'Risk changes' }, { value: 'logs', label: 'Monitoring logs' }]} />
      {tab === 'high' && <Card pad={false}><ErrorBox error={high.error} /><DataTable loading={high.loading} rows={high.data} rowKey="employee_id" empty={<Empty title="No high-risk employees" hint="Great news – or train/run the model." />} columns={[
        { key: 'employee_name', label: 'Employee', render: (r) => <div><b>{r.employee_name}</b><div className="text-xs text-slate-400">{r.department}</div></div> }, { key: 'risk', label: 'Risk', render: (r) => <RiskBar score={r.risk_score} /> },
        { key: 'f', label: 'Drivers', render: (r) => <div className="flex flex-wrap gap-1">{r.top_factors.map((f) => <Badge key={f.feature} tone="high">{f.label} +{f.impact}</Badge>)}</div> },
        { key: 'a', label: 'Suggested action', render: (r) => <span className="text-xs text-slate-600">{r.recommended_actions?.[0]?.title}</span> }, { key: 't', label: 'Since', render: (r) => <span className="text-xs text-slate-400">{fmt.ago(r.created_at)}</span> }]} /></Card>}
      {tab === 'changes' && <div><div className="mb-3 max-w-[10rem]"><Select options={[{ value: 1, label: 'Last 24 hours' }, { value: 7, label: 'Last 7 days' }, { value: 30, label: 'Last 30 days' }]} value={days} onChange={(e) => setDays(Number(e.target.value))} /></div>
        <div className="grid gap-5 lg:grid-cols-2"><Card title="Rising risk" actions={<TrendingUp size={16} className="text-rose-500" />}>{mv(changes.data?.up, true)}</Card><Card title="Improving" actions={<TrendingDown size={16} className="text-emerald-500" />}>{mv(changes.data?.down, false)}</Card></div></div>}
      {tab === 'logs' && <Card pad={false}><DataTable loading={logs.loading} rows={logs.data?.items} columns={[
        { key: 'created_at', label: 'Time', render: (r) => fmt.dt(r.created_at) }, { key: 'employee_name', label: 'Employee', render: (r) => <b>{r.employee_name}</b> },
        { key: 'event', label: 'Event', render: (r) => <Badge tone={r.event === 'entered_high_risk' ? 'high' : r.event === 'left_high_risk' ? 'low' : 'info'}>{r.event}</Badge> },
        { key: 'change', label: 'Risk change', render: (r) => <span className="tabular-nums">{r.old_score == null ? '–' : fmt.pct(r.old_score)} → {fmt.pct(r.new_score)} {r.delta != null && <b className={r.delta > 0 ? 'text-rose-600' : 'text-emerald-600'}>({r.delta > 0 ? '+' : ''}{(r.delta * 100).toFixed(1)})</b>}</span> },
        { key: 'trigger', label: 'Trigger', render: (r) => <span className="text-xs text-slate-500">{r.trigger}</span> }]} /><Pagination page={page} size={15} total={logs.data?.total} onPage={setPage} /></Card>}
      {sim && <Simulator onClose={() => setSim(false)} onDone={reloadAll} />}
    </div>
  )
}
