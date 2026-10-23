import { useState } from 'react'
import { Download, Pencil } from 'lucide-react'
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from 'recharts'
import { api, errMsg, fmt, download } from '../api'
import { useAuth } from '../context/AuthContext'
import { useApp } from '../context/AppContext'
import { useFetch } from '../hooks/useFetch'
import { Card, PageHeader, DataTable, Pagination, Badge, Select, Input, Field, Modal, ErrorBox, Tabs, StatCard } from '../components/ui'
import { Wallet, Receipt, Gift } from 'lucide-react'

const now = new Date()
const MONTHS = Array.from({ length: 12 }, (_, i) => ({ value: i + 1, label: new Date(2000, i).toLocaleString(undefined, { month: 'long' }) }))
export default function Payroll() {
  const { is } = useAuth()
  const { toast } = useApp()
  const hr = is('ADMIN', 'HR')
  const [period, setPeriod] = useState({ month: now.getMonth() + 1, year: now.getFullYear() })
  const [list, setList] = useState({ month: '', year: now.getFullYear() })
  const [page, setPage] = useState(1)
  const [gen, setGen] = useState({ bonus: 0, incentive: 0 })
  const [edit, setEdit] = useState(null)
  const [tab, setTab] = useState('records')
  const [err, setErr] = useState('')
  const recs = useFetch('/payroll', { month: list.month || undefined, year: list.year || undefined, page, size: 12 })
  const summary = useFetch('/payroll/summary', { year: list.year }, { enabled: hr })
  const generate = async () => {
    try { const { data } = await api.post('/payroll/generate', { ...period, bonus: Number(gen.bonus), incentive: Number(gen.incentive) }); toast(`Generated ${data.created} payslips (${data.skipped_existing} already existed)`, 'success'); recs.reload(); summary.reload() } catch (x) { toast(errMsg(x), 'error') }
  }
  const save = async (e) => {
    e.preventDefault(); setErr('')
    try { await api.patch(`/payroll/${edit.id}`, { bonus: Number(edit.bonus), incentive: Number(edit.incentive), other_deductions: Number(edit.other_deductions), status: edit.status }); setEdit(null); recs.reload(); toast('Payroll updated', 'success') } catch (x) { setErr(errMsg(x)) }
  }
  const tot = summary.data?.reduce((a, r) => ({ gross: a.gross + r.gross, net: a.net + r.net, bonus: a.bonus + r.bonus_incentive }), { gross: 0, net: 0, bonus: 0 })
  return (
    <div>
      <PageHeader title="Payroll" subtitle={hr ? 'Generate payroll, review salary breakdown and download payslips' : 'Your salary breakdown and payslips'}
        actions={hr && <button className="btn-ghost" onClick={() => download('/reports/payroll', { format: 'xlsx', ...period })}><Download size={16} />Export {MONTHS[period.month - 1].label}</button>} />
      {hr && <>
        <div className="mb-5 grid gap-4 sm:grid-cols-3"><StatCard label={`Gross ${list.year}`} value={fmt.money(tot?.gross)} icon={Wallet} /><StatCard label={`Net paid ${list.year}`} value={fmt.money(tot?.net)} icon={Receipt} tone="emerald" /><StatCard label="Bonus & incentives" value={fmt.money(tot?.bonus)} icon={Gift} tone="amber" /></div>
        <Card title="Generate payroll" subtitle="Calculates basic/HRA/allowances, overtime pay, progressive tax and PF. Existing payslips are never overwritten." className="mb-5">
          <div className="flex flex-wrap items-end gap-3">
            <Field label="Month"><Select className="!w-40" options={MONTHS} value={period.month} onChange={(e) => setPeriod({ ...period, month: Number(e.target.value) })} /></Field>
            <Field label="Year"><Input className="!w-24" type="number" value={period.year} onChange={(e) => setPeriod({ ...period, year: Number(e.target.value) })} /></Field>
            <Field label="Bonus (each)"><Input className="!w-28" type="number" min="0" value={gen.bonus} onChange={(e) => setGen({ ...gen, bonus: e.target.value })} /></Field>
            <Field label="Incentive (each)"><Input className="!w-28" type="number" min="0" value={gen.incentive} onChange={(e) => setGen({ ...gen, incentive: e.target.value })} /></Field>
            <button className="btn-primary" onClick={generate}>Generate</button></div></Card>
        <Tabs value={tab} onChange={setTab} tabs={[{ value: 'records', label: 'Payslips' }, { value: 'chart', label: 'Monthly overview' }]} /></>}
      {tab === 'chart' && hr ? <Card title={`Payroll by month – ${list.year}`}><div className="h-72"><ResponsiveContainer><BarChart data={(summary.data || []).map((r) => ({ ...r, name: MONTHS[r.month - 1].label.slice(0, 3) }))}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="name" fontSize={11} /><YAxis fontSize={11} tickFormatter={(v) => `${Math.round(v / 1000)}k`} /><Tooltip formatter={(v) => fmt.money(v)} /><Legend />
        <Bar dataKey="gross" fill="#6366f1" /><Bar dataKey="deductions" fill="#f59e0b" /><Bar dataKey="net" fill="#10b981" /></BarChart></ResponsiveContainer></div></Card> : (
        <Card pad={false}>
          <div className="flex gap-3 border-b border-slate-100 p-4"><Select className="!w-40" placeholder="All months" options={MONTHS} value={list.month} onChange={(e) => { setList({ ...list, month: e.target.value }); setPage(1) }} />
            <Input className="!w-24" type="number" value={list.year} onChange={(e) => { setList({ ...list, year: e.target.value }); setPage(1) }} /></div>
          <ErrorBox error={recs.error} />
          <DataTable loading={recs.loading} rows={recs.data?.items} columns={[
            ...(hr ? [{ key: 'employee_name', label: 'Employee', render: (r) => <><b>{r.employee_name}</b> <span className="text-xs text-slate-400">{r.employee_code}</span></> }] : []),
            { key: 'period', label: 'Period', render: (r) => `${MONTHS[r.month - 1].label.slice(0, 3)} ${r.year}` }, { key: 'basic', label: 'Basic', render: (r) => fmt.money(r.basic) },
            { key: 'extras', label: 'OT+Bonus', render: (r) => fmt.money(r.overtime_pay + r.bonus + r.incentive) }, { key: 'gross', label: 'Gross', render: (r) => fmt.money(r.gross) },
            { key: 'tax', label: 'Tax', render: (r) => fmt.money(r.tax) }, { key: 'total_deductions', label: 'Deductions', render: (r) => fmt.money(r.total_deductions) },
            { key: 'net_pay', label: 'Net pay', render: (r) => <b>{fmt.money(r.net_pay)}</b> }, { key: 'status', label: 'Status', render: (r) => <Badge>{r.status}</Badge> },
            { key: 'a', label: '', render: (r) => <div className="flex gap-1"><button className="rounded p-1.5 text-slate-500 hover:bg-slate-100" title="Download payslip PDF" onClick={() => download(`/payroll/${r.id}/payslip`)}><Download size={15} /></button>
              {hr && r.status !== 'paid' && <button className="rounded p-1.5 text-slate-500 hover:bg-slate-100" onClick={() => setEdit(r)} title="Edit"><Pencil size={15} /></button>}</div> }]} />
          <Pagination page={page} size={12} total={recs.data?.total} onPage={setPage} /></Card>)}
      {edit && <Modal open onClose={() => setEdit(null)} title={`Edit payroll – ${edit.employee_name}`} footer={<><button className="btn-ghost" onClick={() => setEdit(null)}>Cancel</button><button form="pe" className="btn-primary">Save</button></>}>
        <form id="pe" onSubmit={save} className="space-y-3"><ErrorBox error={err} />
          <div className="grid grid-cols-3 gap-3"><Field label="Bonus"><Input type="number" min="0" value={edit.bonus} onChange={(e) => setEdit({ ...edit, bonus: e.target.value })} /></Field>
            <Field label="Incentive"><Input type="number" min="0" value={edit.incentive} onChange={(e) => setEdit({ ...edit, incentive: e.target.value })} /></Field>
            <Field label="Other deductions"><Input type="number" min="0" value={edit.other_deductions} onChange={(e) => setEdit({ ...edit, other_deductions: e.target.value })} /></Field></div>
          <Field label="Status"><Select options={['generated', 'paid']} value={edit.status} onChange={(e) => setEdit({ ...edit, status: e.target.value })} /></Field>
          <p className="text-xs text-slate-400">Tax and gross are recalculated on save. Paid payroll is locked.</p></form></Modal>}
    </div>
  )
}
