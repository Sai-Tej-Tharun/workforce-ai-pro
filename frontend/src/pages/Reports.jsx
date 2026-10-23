import { useState } from 'react'
import { FileSpreadsheet, FileText, FileDown, Users, Brain, Wallet, Clock, CalendarDays } from 'lucide-react'
import { download, errMsg } from '../api'
import { useAuth } from '../context/AuthContext'
import { useApp } from '../context/AppContext'
import { useFetch } from '../hooks/useFetch'
import { Card, PageHeader, Select, Input, Field } from '../components/ui'

const now = new Date()
export default function Reports() {
  const { is } = useAuth()
  const { toast } = useApp()
  const hr = is('ADMIN', 'HR')
  const [p, setP] = useState({ month: now.getMonth() + 1, year: now.getFullYear(), department_id: '', risk_level: '' })
  const [busy, setBusy] = useState('')
  const depts = useFetch('/departments')
  const run = async (path, fmt, params) => {
    setBusy(path + fmt)
    try { await download(path, { format: fmt, ...params }); toast('Report downloaded', 'success') } catch (x) { toast(errMsg(x) === 'Request failed (403)' ? 'Not permitted' : 'Export failed', 'error') } finally { setBusy('') }
  }
  const clean = (o) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== ''))
  const REPORTS = [
    { path: '/reports/employees', title: 'Employee report', icon: Users, desc: 'Headcount list with department, role, tenure and status', params: clean({ department_id: p.department_id }), show: true },
    { path: '/reports/attrition', title: 'Attrition risk report', icon: Brain, desc: 'Risk %, level, confidence and top drivers for every active employee', params: clean({ risk_level: p.risk_level }), show: true },
    { path: '/reports/attendance', title: 'Attendance report', icon: Clock, desc: 'Monthly present / late / absent days, hours and overtime', params: clean({ month: p.month, year: p.year, department_id: p.department_id }), show: true },
    { path: '/reports/payroll', title: 'Payroll report', icon: Wallet, desc: 'Salary breakdown, tax, deductions and net pay for a period', params: { month: p.month, year: p.year }, show: hr },
    { path: '/reports/leave', title: 'Leave report', icon: CalendarDays, desc: 'Approved leave days per employee and type', params: { year: p.year }, show: hr },
  ].filter((r) => r.show)
  return (
    <div>
      <PageHeader title="Reports & Export" subtitle="Generate analytics reports as Excel, PDF or CSV (every export is audit-logged)" />
      <Card title="Parameters" className="mb-5"><div className="flex flex-wrap gap-3">
        <Field label="Month"><Select className="!w-40" options={Array.from({ length: 12 }, (_, i) => ({ value: i + 1, label: new Date(2000, i).toLocaleString(undefined, { month: 'long' }) }))} value={p.month} onChange={(e) => setP({ ...p, month: Number(e.target.value) })} /></Field>
        <Field label="Year"><Input className="!w-24" type="number" value={p.year} onChange={(e) => setP({ ...p, year: Number(e.target.value) })} /></Field>
        <Field label="Department"><Select className="!w-48" placeholder="All" options={(depts.data || []).map((d) => ({ value: d.id, label: d.name }))} value={p.department_id} onChange={(e) => setP({ ...p, department_id: e.target.value })} /></Field>
        <Field label="Risk level (attrition)"><Select className="!w-36" placeholder="All" options={['high', 'medium', 'low']} value={p.risk_level} onChange={(e) => setP({ ...p, risk_level: e.target.value })} /></Field></div></Card>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{REPORTS.map((r) => (
        <div key={r.path} className="card p-5"><div className="mb-3 flex items-center gap-3"><div className="rounded-xl bg-indigo-50 p-2.5 text-indigo-600"><r.icon size={20} /></div><div className="font-semibold">{r.title}</div></div>
          <p className="mb-4 min-h-10 text-sm text-slate-500">{r.desc}</p>
          <div className="flex gap-2">{[['xlsx', FileSpreadsheet, 'Excel'], ['pdf', FileText, 'PDF'], ['csv', FileDown, 'CSV']].map(([f, I, l]) => (
            <button key={f} className="btn-ghost flex-1 !px-2" disabled={!!busy} onClick={() => run(r.path, f, r.params)}><I size={15} />{busy === r.path + f ? '…' : l}</button>))}</div></div>))}</div>
    </div>
  )
}
