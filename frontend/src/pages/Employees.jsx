import { useState } from 'react'
import { Plus, Search, SlidersHorizontal, Brain, Pencil, UserX, FlaskConical } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine } from 'recharts'
import { api, errMsg, fmt } from '../api'
import { useAuth } from '../context/AuthContext'
import { useApp } from '../context/AppContext'
import { useFetch, useDebounced } from '../hooks/useFetch'
import { Card, PageHeader, DataTable, Pagination, Badge, RiskBadge, Modal, Field, Input, Select, Avatar, ErrorBox, Confirm, Loading, Empty, Progress } from '../components/ui'

const blank = { first_name: '', last_name: '', email: '', phone: '', gender: 'Female', age: 30, marital_status: 'Single', education: 3, department_id: '', role_id: '', manager_id: '', shift_id: '',
  hire_date: new Date().toISOString().slice(0, 10), monthly_salary: 4000, job_level: 1, distance_from_home: 5, years_at_company: 0, years_since_promotion: 0, total_working_years: 0,
  num_companies_worked: 1, overtime: false, job_satisfaction: 3, environment_satisfaction: 3, work_life_balance: 3, training_times_last_year: 2, performance_rating: 3, stock_option_level: 0 }
const NUMERIC = ['age', 'education', 'monthly_salary', 'job_level', 'distance_from_home', 'years_at_company', 'years_since_promotion', 'total_working_years', 'num_companies_worked', 'job_satisfaction', 'environment_satisfaction', 'work_life_balance', 'training_times_last_year', 'performance_rating', 'stock_option_level']
const IDS = ['department_id', 'role_id', 'manager_id', 'shift_id']

function EmployeeForm({ initial, onClose, onSaved }) {
  const { toast } = useApp()
  const editing = !!initial?.id
  const [f, setF] = useState(() => ({ ...blank, ...Object.fromEntries(Object.entries(initial || {}).filter(([k]) => k in blank).map(([k, v]) => [k, v ?? ''])) }))
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const { data: depts } = useFetch('/departments')
  const { data: roles } = useFetch('/roles', { department_id: f.department_id || undefined })
  const { data: shifts } = useFetch('/shifts')
  const { data: mgrs } = useFetch('/employees', { size: 200, status: 'active' })
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  const num = (k, label, props = {}) => <Field label={label}><Input type="number" step="any" value={f[k]} onChange={set(k)} {...props} /></Field>
  const submit = async (e) => {
    e.preventDefault(); setErr(''); setBusy(true)
    const body = { ...f }
    NUMERIC.forEach((k) => (body[k] = Number(body[k])))
    IDS.forEach((k) => (body[k] = body[k] === '' ? null : Number(body[k])))
    try {
      if (editing) { delete body.hire_date; await api.patch(`/employees/${initial.id}`, body) } else await api.post('/employees', body)
      toast(editing ? 'Employee updated – risk recalculated' : 'Employee created', 'success'); onSaved()
    } catch (x) { setErr(errMsg(x)) } finally { setBusy(false) }
  }
  const opt = (arr, l) => (arr || []).map((x) => ({ value: x.id, label: l(x) }))
  return (
    <Modal open onClose={onClose} wide title={editing ? `Edit ${initial.first_name} ${initial.last_name}` : 'New employee'}
      footer={<><button className="btn-ghost" onClick={onClose}>Cancel</button><button form="empform" className="btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Save'}</button></>}>
      <form id="empform" onSubmit={submit} className="space-y-5">
        <ErrorBox error={err} />
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="First name"><Input required value={f.first_name} onChange={set('first_name')} /></Field>
          <Field label="Last name"><Input required value={f.last_name} onChange={set('last_name')} /></Field>
          <Field label="Email"><Input type="email" required value={f.email} onChange={set('email')} /></Field>
          <Field label="Phone"><Input value={f.phone} onChange={set('phone')} /></Field>
          <Field label="Gender"><Select options={['Female', 'Male', 'Other']} value={f.gender} onChange={set('gender')} /></Field>
          {num('age', 'Age', { min: 16, max: 75 })}
          <Field label="Marital status"><Select options={['Single', 'Married', 'Divorced']} value={f.marital_status} onChange={set('marital_status')} /></Field>
          <Field label="Department"><Select placeholder="– none –" options={opt(depts, (d) => d.name)} value={f.department_id} onChange={set('department_id')} /></Field>
          <Field label="Role"><Select placeholder="– none –" options={opt(roles, (r) => r.title)} value={f.role_id} onChange={set('role_id')} /></Field>
          <Field label="Manager"><Select placeholder="– none –" options={opt(mgrs?.items, (m) => `${m.first_name} ${m.last_name}`)} value={f.manager_id} onChange={set('manager_id')} /></Field>
          <Field label="Shift"><Select placeholder="– none –" options={opt(shifts, (s) => s.name)} value={f.shift_id} onChange={set('shift_id')} /></Field>
          {!editing && <Field label="Hire date"><Input type="date" value={f.hire_date} onChange={set('hire_date')} /></Field>}
          {num('monthly_salary', 'Monthly salary', { min: 0 })}
        </div>
        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">AI model attributes</div>
          <div className="grid gap-3 sm:grid-cols-4">
            {num('job_level', 'Job level (1-5)', { min: 1, max: 5 })}{num('years_at_company', 'Years at company', { min: 0 })}{num('years_since_promotion', 'Years since promotion', { min: 0 })}{num('total_working_years', 'Total experience (y)', { min: 0 })}
            {num('num_companies_worked', 'Past employers', { min: 0 })}{num('distance_from_home', 'Commute (km)', { min: 0 })}{num('training_times_last_year', 'Trainings last year', { min: 0 })}{num('stock_option_level', 'Stock options (0-3)', { min: 0, max: 3 })}
            {num('job_satisfaction', 'Job satisfaction (1-4)', { min: 1, max: 4 })}{num('environment_satisfaction', 'Environment sat. (1-4)', { min: 1, max: 4 })}{num('work_life_balance', 'Work-life balance (1-4)', { min: 1, max: 4 })}{num('performance_rating', 'Performance (1-4)', { min: 1, max: 4 })}
            <label className="flex items-center gap-2 pt-6 text-sm"><input type="checkbox" checked={f.overtime} onChange={set('overtime')} /> Regular overtime</label>
          </div>
        </div>
      </form>
    </Modal>
  )
}

function Row({ k, v }) { return <div className="flex justify-between gap-3 border-b border-slate-50 py-1.5 text-sm"><span className="text-slate-500">{k}</span><span className="text-right font-medium text-slate-800">{v ?? '–'}</span></div> }

function WhatIf({ emp, onResult }) {
  const [o, setO] = useState({ overtime: emp.overtime, job_satisfaction: emp.job_satisfaction, monthly_income: emp.monthly_salary, years_since_promotion: emp.years_since_promotion })
  const [res, setRes] = useState(null)
  const [busy, setBusy] = useState(false)
  const run = async () => {
    setBusy(true)
    try { const { data } = await api.post('/ai/predict/what-if', { employee_id: emp.id, overrides: { ...o, monthly_income: Number(o.monthly_income), years_since_promotion: Number(o.years_since_promotion), job_satisfaction: Number(o.job_satisfaction) } }); setRes(data) } finally { setBusy(false) }
  }
  return (
    <div className="rounded-lg border border-indigo-100 bg-indigo-50/40 p-4">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-indigo-900"><FlaskConical size={16} />What-if simulator <span className="text-xs font-normal text-slate-500">(nothing is saved)</span></div>
      <div className="grid gap-3 sm:grid-cols-4">
        <label className="flex items-center gap-2 pt-5 text-sm"><input type="checkbox" checked={!!o.overtime} onChange={(e) => setO({ ...o, overtime: e.target.checked })} />Overtime</label>
        <Field label="Job satisfaction"><Select options={[1, 2, 3, 4]} value={o.job_satisfaction} onChange={(e) => setO({ ...o, job_satisfaction: e.target.value })} /></Field>
        <Field label="Monthly salary"><Input type="number" value={o.monthly_income} onChange={(e) => setO({ ...o, monthly_income: e.target.value })} /></Field>
        <Field label="Yrs since promo"><Input type="number" step="0.5" value={o.years_since_promotion} onChange={(e) => setO({ ...o, years_since_promotion: e.target.value })} /></Field>
      </div>
      <div className="mt-3 flex items-center gap-4"><button className="btn-primary" onClick={run} disabled={busy}>{busy ? 'Simulating…' : 'Simulate'}</button>
        {res && <div className="text-sm">Risk <b>{fmt.pct(res.before)}</b> → <b className={res.after < res.before ? 'text-emerald-600' : 'text-rose-600'}>{fmt.pct(res.after)}</b> <span className="text-slate-500">({res.change_pct_points > 0 ? '+' : ''}{res.change_pct_points} pts)</span></div>}</div>
    </div>
  )
}

function Profile({ id, onClose, onEdit, onChanged }) {
  const { is } = useAuth()
  const { toast } = useApp()
  const staff = is('ADMIN', 'HR', 'MANAGER')
  const hr = is('ADMIN', 'HR')
  const { data: e, loading, reload } = useFetch(`/employees/${id}`)
  const { data: hist, reload: reloadHist } = useFetch(`/ai/predictions/employee/${id}`, { limit: 20 }, { enabled: staff })
  const { data: rec } = useFetch(`/recommendations/employee/${id}`)
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const recalc = async () => { try { await api.post(`/ai/predict/employee/${id}`); toast('Risk recalculated', 'success'); reload(); reloadHist(); onChanged() } catch (x) { toast(errMsg(x), 'error') } }
  const terminate = async () => { setBusy(true); try { await api.post(`/employees/${id}/terminate`); toast('Employee terminated', 'info'); setConfirm(false); reload(); onChanged() } finally { setBusy(false) } }
  const latest = hist?.[0]
  return (
    <Modal open onClose={onClose} wide title="Employee profile">
      {loading && !e ? <Loading /> : e && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-4"><Avatar name={`${e.first_name} ${e.last_name}`} size={56} />
              <div><div className="text-lg font-semibold">{e.first_name} {e.last_name}</div><div className="text-sm text-slate-500">{e.role_title || 'No role'} · {e.department_name || 'No department'} · {e.employee_code}</div></div></div>
            <div className="flex items-center gap-2"><Badge>{e.status}</Badge>
              {hr && <><button className="btn-ghost" onClick={() => onEdit(e)}><Pencil size={15} />Edit</button>{e.status !== 'terminated' && <button className="btn-ghost text-rose-600" onClick={() => setConfirm(true)}><UserX size={15} />Terminate</button>}</>}</div>
          </div>
          <div className="grid gap-x-8 sm:grid-cols-2">
            <div><Row k="Email" v={e.email} /><Row k="Phone" v={e.phone} /><Row k="Age / Gender" v={`${e.age} / ${e.gender || '–'}`} /><Row k="Marital status" v={e.marital_status} /><Row k="Hire date" v={fmt.date(e.hire_date)} /><Row k="Shift" v={e.shift_name} /></div>
            <div>{hr && <Row k="Monthly salary" v={fmt.money(e.monthly_salary)} />}<Row k="Tenure" v={`${e.years_at_company} yrs`} /><Row k="Since promotion" v={`${e.years_since_promotion} yrs`} /><Row k="Job satisfaction" v={`${e.job_satisfaction}/4`} /><Row k="Work-life balance" v={`${e.work_life_balance}/4`} /><Row k="Overtime" v={e.overtime ? 'Yes' : 'No'} /></div>
          </div>
          {staff && (
            <div className="space-y-4">
              <div className="flex items-center justify-between"><h3 className="flex items-center gap-2 font-semibold"><Brain size={18} className="text-brand-600" />Attrition risk</h3>
                {e.status !== 'terminated' && <button className="btn-ghost" onClick={recalc}>Recalculate</button>}</div>
              {!latest ? <Empty title="No prediction yet" hint="Train a model and run predictions." /> : (
                <div className="grid gap-5 lg:grid-cols-2">
                  <div className="space-y-3">
                    <div className="flex items-end gap-4"><div className="text-4xl font-semibold">{latest.risk_percentage}%</div><RiskBadge level={latest.risk_level} /><div className="pb-1 text-xs text-slate-500">confidence {latest.confidence_percentage}%</div></div>
                    <div><div className="mb-1 text-xs font-semibold uppercase text-slate-400">Top risk drivers</div>
                      {latest.top_factors.length === 0 ? <div className="text-sm text-slate-400">No significant drivers</div> : latest.top_factors.map((f) => (
                        <div key={f.feature} className="mb-2"><div className="flex justify-between text-sm"><span>{f.label} <span className="text-slate-400">({typeof f.value === 'number' ? f.value : f.value})</span></span><span className="font-medium text-rose-600">+{f.impact} pts</span></div><Progress value={Math.min(100, f.impact * 4)} tone="rose" /></div>))}</div>
                    {latest.recommended_actions?.length > 0 && <div><div className="mb-1 text-xs font-semibold uppercase text-slate-400">Recommended actions</div>
                      <ul className="space-y-1.5 text-sm">{latest.recommended_actions.map((a) => <li key={a.title} className="rounded-lg bg-slate-50 p-2"><b>{a.title}</b> – <span className="text-slate-600">{a.action}</span></li>)}</ul></div>}
                  </div>
                  <div><div className="mb-1 text-xs font-semibold uppercase text-slate-400">Risk history</div>
                    <div className="h-48"><ResponsiveContainer><LineChart data={[...hist].reverse().map((p, i) => ({ i: i + 1, risk: p.risk_percentage }))}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="i" fontSize={11} /><YAxis domain={[0, 100]} fontSize={11} /><Tooltip formatter={(v) => `${v}%`} /><ReferenceLine y={60} stroke="#ef4444" strokeDasharray="4 4" /><Line type="monotone" dataKey="risk" stroke="#6366f1" strokeWidth={2} dot={{ r: 2 }} /></LineChart></ResponsiveContainer></div></div>
                </div>)}
              {latest && e.status !== 'terminated' && <WhatIf emp={e} />}
            </div>
          )}
          {rec?.improvement_suggestions?.length > 0 && (
            <div><h3 className="mb-2 font-semibold">Improvement suggestions</h3>
              <ul className="space-y-1.5 text-sm">{rec.improvement_suggestions.map((s, i) => <li key={i} className="flex gap-2 rounded-lg bg-slate-50 p-2"><Badge tone={s.priority === 'high' ? 'high' : s.priority === 'medium' ? 'medium' : 'low'}>{s.area}</Badge><span>{s.recommendation}</span></li>)}</ul></div>)}
          <Confirm open={confirm} onCancel={() => setConfirm(false)} onConfirm={terminate} busy={busy} title="Terminate employee" message="This marks the employee as terminated and closes open interventions as 'left'." />
        </div>)}
    </Modal>
  )
}

export default function Employees() {
  const { is } = useAuth()
  const hr = is('ADMIN', 'HR'), staff = is('ADMIN', 'HR', 'MANAGER')
  const [q, setQ] = useState({ search: '', department_id: '', status: 'active', risk_level: '', overtime: '', min_salary: '', max_salary: '', min_late_days: '' })
  const [adv, setAdv] = useState(false)
  const [page, setPage] = useState(1)
  const [sort, setSort] = useState({ key: 'id', order: 'asc' })
  const [form, setForm] = useState(null)
  const [view, setView] = useState(null)
  const search = useDebounced(q.search)
  const params = { ...Object.fromEntries(Object.entries({ ...q, search }).filter(([, v]) => v !== '')), page, size: 15, sort: sort.key, order: sort.order }
  const { data, loading, error, reload } = useFetch('/employees', params)
  const { data: depts } = useFetch('/departments')
  const set = (k) => (e) => { setQ({ ...q, [k]: e.target.value }); setPage(1) }
  const cols = [
    { key: 'name', label: 'Employee', sortKey: 'name', render: (r) => <div className="flex items-center gap-3"><Avatar name={`${r.first_name} ${r.last_name}`} /><div><div className="font-medium text-slate-900">{r.first_name} {r.last_name}</div><div className="text-xs text-slate-400">{r.employee_code} · {r.email}</div></div></div> },
    { key: 'dept', label: 'Department', render: (r) => <div>{r.department_name || '–'}<div className="text-xs text-slate-400">{r.role_title}</div></div> },
    ...(hr ? [{ key: 'salary', label: 'Salary', sortKey: 'salary', render: (r) => fmt.money(r.monthly_salary) }] : []),
    { key: 'tenure', label: 'Tenure', sortKey: 'tenure', render: (r) => `${r.years_at_company}y` },
    { key: 'status', label: 'Status', render: (r) => <Badge>{r.status}</Badge> },
    ...(staff ? [{ key: 'risk', label: 'Attrition risk', render: (r) => <RiskBadge level={r.risk_level} score={r.risk_score} /> }] : []),
  ]
  return (
    <div>
      <PageHeader title="Employees" subtitle="Search, filter and manage employee profiles" actions={hr && <button className="btn-primary" onClick={() => setForm({})}><Plus size={16} />New employee</button>} />
      <Card pad={false}>
        <div className="space-y-3 border-b border-slate-100 p-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative min-w-60 flex-1"><Search size={16} className="absolute left-3 top-3 text-slate-400" /><Input className="!pl-9" placeholder="Search name, email or code…" value={q.search} onChange={set('search')} /></div>
            <Select className="!w-48" placeholder="All departments" options={(depts || []).map((d) => ({ value: d.id, label: d.name }))} value={q.department_id} onChange={set('department_id')} />
            <Select className="!w-36" placeholder="Any status" options={['active', 'terminated', 'on_leave']} value={q.status} onChange={set('status')} />
            {staff && <Select className="!w-36" placeholder="Any risk" options={['high', 'medium', 'low']} value={q.risk_level} onChange={set('risk_level')} />}
            {staff && <button className="btn-ghost" onClick={() => setAdv(!adv)}><SlidersHorizontal size={16} />More filters</button>}
          </div>
          {adv && <div className="grid gap-3 sm:grid-cols-4">
            <Field label="Overtime"><Select placeholder="Any" options={[{ value: 'true', label: 'Yes' }, { value: 'false', label: 'No' }]} value={q.overtime} onChange={set('overtime')} /></Field>
            {hr && <Field label="Min salary"><Input type="number" value={q.min_salary} onChange={set('min_salary')} /></Field>}
            {hr && <Field label="Max salary"><Input type="number" value={q.max_salary} onChange={set('max_salary')} /></Field>}
            <Field label="Min late days (30d)"><Input type="number" min="1" value={q.min_late_days} onChange={set('min_late_days')} /></Field></div>}
        </div>
        <ErrorBox error={error} onRetry={reload} />
        <DataTable columns={cols} rows={data?.items} loading={loading} sort={sort} onSort={(k) => setSort((s) => ({ key: k, order: s.key === k && s.order === 'asc' ? 'desc' : 'asc' }))}
          onRowClick={(r) => setView(r.id)} empty={<Empty title="No employees match" hint="Try clearing some filters." />} />
        <Pagination page={page} size={15} total={data?.total} onPage={setPage} />
      </Card>
      {form && <EmployeeForm initial={form} onClose={() => setForm(null)} onSaved={() => { setForm(null); reload() }} />}
      {view && <Profile id={view} onClose={() => setView(null)} onEdit={(e) => { setView(null); setForm(e) }} onChanged={reload} />}
    </div>
  )
}
