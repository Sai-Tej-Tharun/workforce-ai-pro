import { useState } from 'react'
import { Plus, Star, Trash2 } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { api, errMsg, fmt } from '../api'
import { useAuth } from '../context/AuthContext'
import { useApp } from '../context/AppContext'
import { useFetch } from '../hooks/useFetch'
import { Card, PageHeader, Tabs, DataTable, Pagination, Badge, Select, Input, Field, Modal, ErrorBox, Progress, Empty } from '../components/ui'

const Stars = ({ n }) => <span className="inline-flex text-amber-400">{[1, 2, 3, 4, 5].map((i) => <Star key={i} size={14} fill={i <= n ? 'currentColor' : 'none'} />)}</span>

export default function Performance() {
  const { is, user } = useAuth()
  const { toast } = useApp()
  const staff = is('ADMIN', 'HR', 'MANAGER')
  const [tab, setTab] = useState('reviews')
  const [page, setPage] = useState(1)
  const [emp, setEmp] = useState(staff ? '' : String(user.employee_id || ''))
  const [form, setForm] = useState(null)
  const [err, setErr] = useState('')
  const emps = useFetch('/employees', { size: 200, status: 'active' })
  const reviews = useFetch('/performance/reviews', { employee_id: emp || undefined, page, size: 10 })
  const goals = useFetch('/performance/goals', { employee_id: emp || undefined })
  const summary = useFetch(`/performance/summary/${emp}`, {}, { enabled: !!emp })
  const eOpts = (emps.data?.items || []).map((e) => ({ value: e.id, label: `${e.first_name} ${e.last_name}` }))
  const today = new Date()
  const period = `${today.getFullYear()}-Q${Math.ceil((today.getMonth() + 1) / 3)}`

  const save = async (e) => {
    e.preventDefault(); setErr('')
    try {
      if (form.kind === 'review') await api.post('/performance/reviews', { employee_id: Number(form.employee_id), period: form.period, rating: Number(form.rating), strengths: form.strengths || null, improvements: form.improvements || null, comments: form.comments || null })
      else await api.post('/performance/goals', { employee_id: Number(form.employee_id), title: form.title, description: form.description || null, due_date: form.due_date || null, progress: 0 })
      toast('Saved', 'success'); setForm(null); reviews.reload(); goals.reload(); summary.reload()
    } catch (x) { setErr(errMsg(x)) }
  }
  const setProgress = async (g, progress) => { try { await api.patch(`/performance/goals/${g.id}`, { progress }); goals.reload() } catch (x) { toast(errMsg(x), 'error') } }
  const delGoal = async (g) => { try { await api.delete(`/performance/goals/${g.id}`); goals.reload() } catch (x) { toast(errMsg(x), 'error') } }

  return (
    <div>
      <PageHeader title="Performance" subtitle="Reviews, ratings, history and goal tracking" actions={<>
        {staff && <button className="btn-primary" onClick={() => setForm({ kind: 'review', employee_id: emp, period, rating: 3 })}><Plus size={16} />New review</button>}
        <button className="btn-ghost" onClick={() => setForm({ kind: 'goal', employee_id: emp || user.employee_id || '' })}><Plus size={16} />New goal</button></>} />
      {staff && <div className="mb-4 max-w-xs"><Select placeholder="All employees" options={eOpts} value={emp} onChange={(e) => { setEmp(e.target.value); setPage(1) }} /></div>}
      {emp && summary.data && <div className="mb-5 grid gap-5 lg:grid-cols-3">
        <Card title="Average rating"><div className="flex items-center gap-3"><span className="text-3xl font-semibold">{summary.data.average_rating ?? '–'}</span>{summary.data.average_rating && <Stars n={Math.round(summary.data.average_rating)} />}</div>
          <div className="mt-2 text-xs text-slate-400">Goal completion {summary.data.goal_completion ?? '–'}%</div></Card>
        <Card title="Rating history" className="lg:col-span-2"><div className="h-28"><ResponsiveContainer><LineChart data={summary.data.history}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="period" fontSize={11} /><YAxis domain={[1, 5]} fontSize={11} /><Tooltip /><Line type="monotone" dataKey="rating" stroke="#6366f1" strokeWidth={2} /></LineChart></ResponsiveContainer></div></Card></div>}
      <Tabs value={tab} onChange={setTab} tabs={[{ value: 'reviews', label: 'Reviews', count: reviews.data?.total }, { value: 'goals', label: 'Goals', count: goals.data?.length }]} />
      {tab === 'reviews' && <Card pad={false}><ErrorBox error={reviews.error} />
        <DataTable loading={reviews.loading} rows={reviews.data?.items} empty={<Empty title="No reviews yet" />} columns={[
          { key: 'employee_name', label: 'Employee', render: (r) => <b>{r.employee_name}</b> }, { key: 'period', label: 'Period' }, { key: 'rating', label: 'Rating', render: (r) => <Stars n={r.rating} /> },
          { key: 'strengths', label: 'Strengths' }, { key: 'improvements', label: 'To improve' }, { key: 'created_at', label: 'Date', render: (r) => fmt.date(r.created_at) }]} />
        <Pagination page={page} size={10} total={reviews.data?.total} onPage={setPage} /></Card>}
      {tab === 'goals' && (!goals.data?.length ? <Card><Empty title="No goals" /></Card> : <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {goals.data.map((g) => <div key={g.id} className="card p-4"><div className="flex items-start justify-between gap-2"><div><div className="font-medium">{g.title}</div><div className="text-xs text-slate-400">{g.employee_name} · due {fmt.date(g.due_date)}</div></div><Badge>{g.status}</Badge></div>
          <div className="mt-3"><Progress value={g.progress} tone={g.status === 'at_risk' ? 'rose' : g.progress === 100 ? 'emerald' : 'brand'} /></div>
          <div className="mt-2 flex items-center gap-2"><input type="range" min="0" max="100" step="10" value={g.progress} className="flex-1" onChange={(e) => setProgress(g, Number(e.target.value))} aria-label="Progress" /><span className="w-10 text-right text-sm">{g.progress}%</span>
            <button className="rounded p-1 text-slate-400 hover:text-rose-600" onClick={() => delGoal(g)} aria-label="Delete goal"><Trash2 size={15} /></button></div></div>)}</div>)}
      {form && <Modal open onClose={() => setForm(null)} title={form.kind === 'review' ? 'New performance review' : 'New goal'} footer={<><button className="btn-ghost" onClick={() => setForm(null)}>Cancel</button><button form="pf" className="btn-primary">Save</button></>}>
        <form id="pf" onSubmit={save} className="space-y-3"><ErrorBox error={err} />
          {(staff || form.kind === 'review') && <Field label="Employee"><Select required placeholder="Select…" options={eOpts} value={form.employee_id} onChange={(e) => setForm({ ...form, employee_id: e.target.value })} /></Field>}
          {form.kind === 'review' ? <>
            <div className="grid grid-cols-2 gap-3"><Field label="Period"><Input required value={form.period} onChange={(e) => setForm({ ...form, period: e.target.value })} /></Field>
              <Field label="Rating (1-5)"><Select options={[1, 2, 3, 4, 5]} value={form.rating} onChange={(e) => setForm({ ...form, rating: e.target.value })} /></Field></div>
            <Field label="Strengths"><Input value={form.strengths || ''} onChange={(e) => setForm({ ...form, strengths: e.target.value })} /></Field>
            <Field label="Improvements"><Input value={form.improvements || ''} onChange={(e) => setForm({ ...form, improvements: e.target.value })} /></Field>
            <Field label="Comments" hint="Saving a review updates the employee's performance rating and recalculates attrition risk"><Input value={form.comments || ''} onChange={(e) => setForm({ ...form, comments: e.target.value })} /></Field></> : <>
            <Field label="Goal"><Input required value={form.title || ''} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
            <Field label="Description"><Input value={form.description || ''} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
            <Field label="Due date"><Input type="date" value={form.due_date || ''} onChange={(e) => setForm({ ...form, due_date: e.target.value })} /></Field></>}
        </form></Modal>}
    </div>
  )
}
