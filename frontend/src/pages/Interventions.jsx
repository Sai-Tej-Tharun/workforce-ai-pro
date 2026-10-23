import { useState } from 'react'
import { Plus, Sparkles } from 'lucide-react'
import { api, errMsg, fmt } from '../api'
import { useApp, useLive } from '../context/AppContext'
import { useFetch } from '../hooks/useFetch'
import { Card, PageHeader, StatCard, DataTable, Pagination, Badge, Select, Field, Input, Modal, ErrorBox, Empty, Tabs } from '../components/ui'
import { HandHelping, CheckCircle2, AlarmClock, Percent } from 'lucide-react'

function Detail({ id, onClose, onChanged }) {
  const { toast } = useApp()
  const { data: iv, reload } = useFetch(`/interventions/${id}`)
  const [note, setNote] = useState('')
  const [outcome, setOutcome] = useState('')
  const upd = async (body) => { try { await api.patch(`/interventions/${id}`, body); setNote(''); reload(); onChanged() } catch (x) { toast(errMsg(x), 'error') } }
  if (!iv) return null
  const closed = ['completed', 'dismissed'].includes(iv.status)
  return (
    <Modal open onClose={onClose} wide title={iv.title}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2"><Badge>{iv.status}</Badge><Badge tone={iv.priority}>{iv.priority}</Badge>{iv.auto_generated && <Badge tone="info"><Sparkles size={11} className="mr-1" />AI-generated</Badge>}{iv.overdue && <Badge tone="high">overdue</Badge>}
          <span className="text-sm text-slate-500">{iv.employee_name} · {iv.department} · follow-up {fmt.date(iv.follow_up_date)}</span></div>
        <pre className="whitespace-pre-wrap rounded-lg bg-slate-50 p-4 font-sans text-sm text-slate-700">{iv.recommendation}</pre>
        {!closed && <div className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 p-3">
          <Field label="Add note / log action"><Input className="!w-72" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Stay interview held" /></Field>
          <button className="btn-ghost" disabled={!note} onClick={() => upd({ note })}>Log note</button>
          {iv.status === 'open' && <button className="btn-primary" onClick={() => upd({ status: 'in_progress' })}>Start</button>}
          <Field label="Outcome"><Select placeholder="–" options={['retained', 'left', 'unknown']} value={outcome} onChange={(e) => setOutcome(e.target.value)} /></Field>
          <button className="btn-primary" onClick={() => upd({ status: 'completed', outcome: outcome || 'unknown', note: note || undefined })}>Complete</button>
          <button className="btn-ghost" onClick={() => upd({ status: 'dismissed', note: note || 'Dismissed' })}>Dismiss</button></div>}
        {closed && <div className="text-sm text-slate-500">Closed {fmt.dt(iv.closed_at)} {iv.outcome && <>· outcome <b>{iv.outcome}</b></>}</div>}
        <div><div className="mb-2 text-xs font-semibold uppercase text-slate-400">Activity log</div>
          <ul className="space-y-1.5 text-sm">{iv.logs.map((l) => <li key={l.id} className="flex gap-3"><span className="w-36 shrink-0 text-xs text-slate-400">{fmt.dt(l.created_at)}</span><Badge tone="info">{l.action}</Badge><span className="text-slate-600">{l.note}</span></li>)}</ul></div>
      </div>
    </Modal>
  )
}

export default function Interventions() {
  const { toast } = useApp()
  const [status, setStatus] = useState('')
  const [overdue, setOverdue] = useState(false)
  const [page, setPage] = useState(1)
  const [view, setView] = useState(null)
  const [form, setForm] = useState(null)
  const [err, setErr] = useState('')
  const list = useFetch('/interventions', { status: status || undefined, overdue: overdue || undefined, page, size: 12 })
  const stats = useFetch('/interventions/stats')
  const emps = useFetch('/employees', { size: 200, status: 'active' }, { enabled: !!form })
  useLive(['risk_update'], () => { list.reload(); stats.reload() })
  const s = stats.data
  const suggest = async (id) => {
    if (!id) return setForm({ ...form, employee_id: '' })
    try { const { data } = await api.get(`/interventions/suggest/${id}`); setForm({ ...form, employee_id: id, title: `Retention plan: ${data.actions[0]?.title || 'check-in'}`, recommendation: data.actions.map((a, i) => `${i + 1}. ${a.title} – ${a.action}`).join('\n') }) } catch { setForm({ ...form, employee_id: id }) }
  }
  const save = async (e) => {
    e.preventDefault(); setErr('')
    try { await api.post('/interventions', { ...form, employee_id: Number(form.employee_id), follow_up_date: form.follow_up_date || null }); setForm(null); list.reload(); stats.reload(); toast('Intervention created', 'success') } catch (x) { setErr(errMsg(x)) }
  }
  return (
    <div>
      <PageHeader title="HR Interventions" subtitle="AI-triggered retention workflows, follow-ups and outcomes" actions={<button className="btn-primary" onClick={() => setForm({ employee_id: '', title: '', recommendation: '', priority: 'high', follow_up_date: '' })}><Plus size={16} />New intervention</button>} />
      {s && <div className="mb-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><StatCard label="Open / in progress" value={s.open + s.in_progress} icon={HandHelping} tone="amber" /><StatCard label="Overdue follow-ups" value={s.overdue} icon={AlarmClock} tone={s.overdue ? 'rose' : 'slate'} />
        <StatCard label="Completed" value={s.completed} icon={CheckCircle2} tone="emerald" /><StatCard label="Retention success" value={s.retention_success_rate == null ? '–' : `${s.retention_success_rate}%`} hint={`${s.retained} retained · ${s.left} left`} icon={Percent} tone="sky" /></div>}
      <Card pad={false}>
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 p-4"><Select className="!w-44" placeholder="All statuses" options={['open', 'in_progress', 'completed', 'dismissed']} value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }} />
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={overdue} onChange={(e) => { setOverdue(e.target.checked); setPage(1) }} />Overdue only</label></div>
        <ErrorBox error={list.error} />
        <DataTable loading={list.loading} rows={list.data?.items} onRowClick={(r) => setView(r.id)} empty={<Empty title="No interventions" hint="They are created automatically when an employee enters high risk." />} columns={[
          { key: 'employee_name', label: 'Employee', render: (r) => <div><b>{r.employee_name}</b><div className="text-xs text-slate-400">{r.department}</div></div> },
          { key: 'title', label: 'Plan', render: (r) => <span className="flex items-center gap-1.5">{r.auto_generated && <Sparkles size={13} className="text-brand-600" />}{r.title}</span>, className: 'max-w-sm' },
          { key: 'priority', label: 'Priority', render: (r) => <Badge tone={r.priority}>{r.priority}</Badge> }, { key: 'status', label: 'Status', render: (r) => <Badge>{r.status}</Badge> },
          { key: 'follow_up_date', label: 'Follow-up', render: (r) => <span className={r.overdue ? 'font-medium text-rose-600' : ''}>{fmt.date(r.follow_up_date)}{r.overdue && ' ⚠'}</span> }, { key: 'outcome', label: 'Outcome', render: (r) => r.outcome ? <Badge tone={r.outcome === 'retained' ? 'low' : r.outcome === 'left' ? 'high' : 'info'}>{r.outcome}</Badge> : '–' }]} />
        <Pagination page={page} size={12} total={list.data?.total} onPage={setPage} /></Card>
      {view && <Detail id={view} onClose={() => setView(null)} onChanged={() => { list.reload(); stats.reload() }} />}
      {form && <Modal open onClose={() => setForm(null)} title="New intervention" footer={<><button className="btn-ghost" onClick={() => setForm(null)}>Cancel</button><button form="ivf" className="btn-primary">Create</button></>}>
        <form id="ivf" onSubmit={save} className="space-y-3"><ErrorBox error={err} />
          <Field label="Employee" hint="Selecting an employee pre-fills AI-suggested actions from their risk drivers"><Select required placeholder="Select…" options={(emps.data?.items || []).map((e) => ({ value: e.id, label: `${e.first_name} ${e.last_name}` }))} value={form.employee_id} onChange={(e) => suggest(e.target.value)} /></Field>
          <Field label="Title"><Input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
          <Field label="Plan / recommendation"><textarea required rows={5} className="input" value={form.recommendation} onChange={(e) => setForm({ ...form, recommendation: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3"><Field label="Priority"><Select options={['low', 'medium', 'high', 'critical']} value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} /></Field>
            <Field label="Follow-up date"><Input type="date" value={form.follow_up_date} onChange={(e) => setForm({ ...form, follow_up_date: e.target.value })} /></Field></div></form></Modal>}
    </div>
  )
}
