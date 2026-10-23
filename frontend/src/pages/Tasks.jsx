import { useState } from 'react'
import { Plus, AlertTriangle, Trash2 } from 'lucide-react'
import { api, errMsg, fmt } from '../api'
import { useAuth } from '../context/AuthContext'
import { useApp } from '../context/AppContext'
import { useFetch } from '../hooks/useFetch'
import { PageHeader, Badge, Modal, Field, Input, Select, ErrorBox, StatCard, Empty, Loading } from '../components/ui'
import { ListChecks, Clock, CheckCircle2, CalendarX } from 'lucide-react'

const COLS = [['todo', 'To do'], ['in_progress', 'In progress'], ['done', 'Done']]
export default function Tasks() {
  const { is } = useAuth()
  const { toast } = useApp()
  const staff = is('ADMIN', 'HR', 'MANAGER')
  const tasks = useFetch('/tasks', { size: 200 })
  const stats = useFetch('/tasks/stats')
  const people = useFetch('/chat/contacts', {}, { enabled: staff })
  const [form, setForm] = useState(null)
  const [err, setErr] = useState('')
  const reload = () => { tasks.reload(); stats.reload() }
  const move = async (t, status) => { try { await api.patch(`/tasks/${t.id}`, { status }); reload() } catch (x) { toast(errMsg(x), 'error') } }
  const del = async (t) => { try { await api.delete(`/tasks/${t.id}`); reload() } catch (x) { toast(errMsg(x), 'error') } }
  const save = async (e) => {
    e.preventDefault(); setErr('')
    try { await api.post('/tasks', { ...form, assigned_to: form.assigned_to ? Number(form.assigned_to) : null, due_date: form.due_date || null }); setForm(null); reload(); toast('Task created', 'success') } catch (x) { setErr(errMsg(x)) }
  }
  const prio = { critical: 'critical', high: 'high', medium: 'medium', low: 'low' }
  const s = stats.data
  const items = tasks.data?.items || []
  return (
    <div>
      <PageHeader title="Tasks & Workflow" subtitle="HR task assignment, status tracking and due-date monitoring" actions={staff && <button className="btn-primary" onClick={() => setForm({ title: '', description: '', priority: 'medium', assigned_to: '', due_date: '' })}><Plus size={16} />New task</button>} />
      {s && <div className="mb-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><StatCard label="To do" value={s.todo} icon={ListChecks} /><StatCard label="In progress" value={s.in_progress} icon={Clock} tone="sky" /><StatCard label="Done" value={s.done} icon={CheckCircle2} tone="emerald" /><StatCard label="Overdue" value={s.overdue} icon={CalendarX} tone={s.overdue ? 'rose' : 'slate'} /></div>}
      <ErrorBox error={tasks.error} onRetry={tasks.reload} />
      {tasks.loading && !tasks.data ? <Loading /> : <div className="grid gap-4 lg:grid-cols-3">
        {COLS.map(([key, label]) => { const col = items.filter((t) => t.status === key); return (
          <div key={key} className="rounded-xl bg-slate-100/70 p-3"><div className="mb-3 flex items-center justify-between px-1 text-sm font-semibold text-slate-600">{label}<span className="rounded-full bg-white px-2 text-xs">{col.length}</span></div>
            <div className="space-y-2.5">{col.length === 0 && <Empty title="No tasks" />}{col.map((t) => (
              <div key={t.id} className={`card p-3 ${t.overdue ? 'border-rose-200' : ''}`}>
                <div className="flex items-start justify-between gap-2"><div className="font-medium text-slate-800">{t.title}</div><Badge tone={prio[t.priority]}>{t.priority}</Badge></div>
                {t.description && <div className="mt-1 text-xs text-slate-500">{t.description}</div>}
                <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400"><span>{t.assignee_name || 'Unassigned'}</span>
                  {t.due_date && <span className={t.overdue ? 'flex items-center gap-1 font-medium text-rose-600' : t.due_soon ? 'font-medium text-amber-600' : ''}>{t.overdue && <AlertTriangle size={12} />}Due {fmt.date(t.due_date)}</span>}</div>
                <div className="mt-2 flex gap-1.5">{COLS.filter(([k]) => k !== key).map(([k, l]) => <button key={k} className="btn-ghost !px-2 !py-0.5 text-xs" onClick={() => move(t, k)}>→ {l}</button>)}
                  {staff && <button className="ml-auto rounded p-1 text-slate-300 hover:text-rose-600" onClick={() => del(t)} aria-label="Delete task"><Trash2 size={14} /></button>}</div>
              </div>))}</div></div>) })}</div>}
      {form && <Modal open onClose={() => setForm(null)} title="New task" footer={<><button className="btn-ghost" onClick={() => setForm(null)}>Cancel</button><button form="tf" className="btn-primary">Create</button></>}>
        <form id="tf" onSubmit={save} className="space-y-3"><ErrorBox error={err} />
          <Field label="Title"><Input required minLength={2} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
          <Field label="Description"><Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
          <div className="grid grid-cols-3 gap-3"><Field label="Assignee"><Select placeholder="–" options={(people.data || []).map((p) => ({ value: p.id, label: p.full_name }))} value={form.assigned_to} onChange={(e) => setForm({ ...form, assigned_to: e.target.value })} /></Field>
            <Field label="Priority"><Select options={['low', 'medium', 'high', 'critical']} value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} /></Field>
            <Field label="Due"><Input type="date" min={new Date().toISOString().slice(0, 10)} value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} /></Field></div></form></Modal>}
    </div>
  )
}
