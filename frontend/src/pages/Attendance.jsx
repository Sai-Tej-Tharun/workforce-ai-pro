import { useState } from 'react'
import { LogIn, LogOut, Plus } from 'lucide-react'
import { api, errMsg, fmt, download } from '../api'
import { useAuth } from '../context/AuthContext'
import { useApp } from '../context/AppContext'
import { useFetch } from '../hooks/useFetch'
import { Card, PageHeader, Tabs, DataTable, Pagination, Badge, Select, Input, Field, Modal, ErrorBox, StatCard } from '../components/ui'
import { Clock, Timer, UserX } from 'lucide-react'

const now = new Date()
export default function Attendance() {
  const { is } = useAuth()
  const { toast } = useApp()
  const hr = is('ADMIN', 'HR'), staff = is('ADMIN', 'HR', 'MANAGER')
  const [tab, setTab] = useState('records')
  const [page, setPage] = useState(1)
  const [flt, setFlt] = useState({ status: '', date_from: '', date_to: '' })
  const [rep, setRep] = useState({ month: now.getMonth() + 1, year: now.getFullYear() })
  const today = useFetch('/attendance/today')
  const recs = useFetch('/attendance', { ...Object.fromEntries(Object.entries(flt).filter(([, v]) => v)), page, size: 15 })
  const report = useFetch('/attendance/report', rep, { enabled: tab === 'report' })
  const shifts = useFetch('/shifts')
  const emps = useFetch('/employees', { size: 200, status: 'active' }, { enabled: hr && tab === 'shifts' })
  const [asg, setAsg] = useState({ employee_id: '', shift_id: '' })
  const [shiftForm, setShiftForm] = useState(null)
  const [err, setErr] = useState('')
  const rec = today.data?.record

  const act = async (kind) => {
    try { await api.post(`/attendance/check-${kind}`, {}); toast(kind === 'in' ? 'Checked in' : 'Checked out', 'success'); today.reload(); recs.reload() } catch (x) { toast(errMsg(x), 'error') }
  }
  const saveShift = async (e) => {
    e.preventDefault(); setErr('')
    try { await api.post('/shifts', { ...shiftForm, standard_hours: Number(shiftForm.standard_hours) }); setShiftForm(null); shifts.reload(); toast('Shift created', 'success') } catch (x) { setErr(errMsg(x)) }
  }
  const assign = async () => { try { await api.post('/shifts/assign', { employee_id: Number(asg.employee_id), shift_id: Number(asg.shift_id) }); toast('Shift assigned', 'success') } catch (x) { toast(errMsg(x), 'error') } }
  const hm = (v) => (v ? new Date(v).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '–')

  return (
    <div>
      <PageHeader title="Attendance & Shifts" subtitle="Check-in/out, working hours, overtime and monthly reports"
        actions={staff && <button className="btn-ghost" onClick={() => download('/reports/attendance', { format: 'xlsx', ...rep })}>Export Excel</button>} />
      {today.data?.linked && (
        <Card className="mb-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div><div className="text-sm text-slate-500">Today · {new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}</div>
              <div className="mt-1 flex items-center gap-3 text-lg font-semibold">{rec ? <><Badge>{rec.status}</Badge> In {hm(rec.check_in)}{rec.check_out && <> · Out {hm(rec.check_out)} · {rec.working_hours}h</>}</> : 'Not checked in yet'}</div></div>
            <div className="flex gap-2"><button className="btn-primary" disabled={!!rec} onClick={() => act('in')}><LogIn size={16} />Check in</button>
              <button className="btn-ghost" disabled={!rec || !!rec?.check_out} onClick={() => act('out')}><LogOut size={16} />Check out</button></div>
          </div>
        </Card>)}
      <Tabs value={tab} onChange={setTab} tabs={[{ value: 'records', label: 'Records' }, { value: 'report', label: 'Monthly report' }, { value: 'shifts', label: 'Shifts' }]} />
      {tab === 'records' && <Card pad={false}>
        <div className="flex flex-wrap gap-3 border-b border-slate-100 p-4">
          <Select className="!w-40" placeholder="Any status" options={['present', 'late', 'absent', 'half_day']} value={flt.status} onChange={(e) => { setFlt({ ...flt, status: e.target.value }); setPage(1) }} />
          <Input className="!w-44" type="date" value={flt.date_from} onChange={(e) => { setFlt({ ...flt, date_from: e.target.value }); setPage(1) }} />
          <Input className="!w-44" type="date" value={flt.date_to} onChange={(e) => { setFlt({ ...flt, date_to: e.target.value }); setPage(1) }} />
        </div>
        <ErrorBox error={recs.error} />
        <DataTable loading={recs.loading} rows={recs.data?.items} columns={[
          { key: 'work_date', label: 'Date', render: (r) => fmt.date(r.work_date) }, ...(staff ? [{ key: 'employee_name', label: 'Employee' }] : []),
          { key: 'check_in', label: 'In', render: (r) => hm(r.check_in) }, { key: 'check_out', label: 'Out', render: (r) => hm(r.check_out) },
          { key: 'working_hours', label: 'Hours' }, { key: 'overtime_hours', label: 'Overtime', render: (r) => r.overtime_hours > 0 ? <b className="text-amber-600">{r.overtime_hours}h</b> : '–' },
          { key: 'status', label: 'Status', render: (r) => <Badge>{r.status}</Badge> }]} />
        <Pagination page={page} size={15} total={recs.data?.total} onPage={setPage} />
      </Card>}
      {tab === 'report' && <Card pad={false}>
        <div className="flex gap-3 border-b border-slate-100 p-4"><Select className="!w-40" options={Array.from({ length: 12 }, (_, i) => ({ value: i + 1, label: new Date(2000, i).toLocaleString(undefined, { month: 'long' }) }))} value={rep.month} onChange={(e) => setRep({ ...rep, month: Number(e.target.value) })} />
          <Input className="!w-28" type="number" value={rep.year} onChange={(e) => setRep({ ...rep, year: Number(e.target.value) })} /></div>
        <DataTable loading={report.loading} rows={report.data} rowKey="employee_id" columns={[
          { key: 'employee_name', label: 'Employee', render: (r) => <><b>{r.employee_name}</b> <span className="text-xs text-slate-400">{r.employee_code}</span></> },
          { key: 'days_present', label: 'Present' }, { key: 'late_days', label: 'Late', render: (r) => r.late_days > 3 ? <b className="text-amber-600">{r.late_days}</b> : r.late_days },
          { key: 'absent_days', label: 'Absent', render: (r) => r.absent_days > 1 ? <b className="text-rose-600">{r.absent_days}</b> : r.absent_days },
          { key: 'total_hours', label: 'Total hours' }, { key: 'overtime_hours', label: 'Overtime (h)' }]} /></Card>}
      {tab === 'shifts' && <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Shifts" actions={hr && <button className="btn-primary !py-1" onClick={() => setShiftForm({ name: '', start_time: '09:00', end_time: '17:00', standard_hours: 8 })}><Plus size={14} />New</button>} pad={false}>
          <DataTable rows={shifts.data} columns={[{ key: 'name', label: 'Name', render: (r) => <b>{r.name}</b> }, { key: 't', label: 'Time', render: (r) => `${r.start_time.slice(0, 5)} – ${r.end_time.slice(0, 5)}` }, { key: 'standard_hours', label: 'Std hours' }]} /></Card>
        {hr && <Card title="Assign shift"><div className="space-y-3">
          <Field label="Employee"><Select placeholder="Select…" options={(emps.data?.items || []).map((e) => ({ value: e.id, label: `${e.first_name} ${e.last_name}` }))} value={asg.employee_id} onChange={(e) => setAsg({ ...asg, employee_id: e.target.value })} /></Field>
          <Field label="Shift"><Select placeholder="Select…" options={(shifts.data || []).map((s) => ({ value: s.id, label: s.name }))} value={asg.shift_id} onChange={(e) => setAsg({ ...asg, shift_id: e.target.value })} /></Field>
          <button className="btn-primary" disabled={!asg.employee_id || !asg.shift_id} onClick={assign}>Assign</button></div></Card>}
      </div>}
      {shiftForm && <Modal open onClose={() => setShiftForm(null)} title="New shift" footer={<><button className="btn-ghost" onClick={() => setShiftForm(null)}>Cancel</button><button form="shf" className="btn-primary">Save</button></>}>
        <form id="shf" onSubmit={saveShift} className="space-y-3"><ErrorBox error={err} />
          <Field label="Name"><Input required value={shiftForm.name} onChange={(e) => setShiftForm({ ...shiftForm, name: e.target.value })} /></Field>
          <div className="grid grid-cols-3 gap-3"><Field label="Start"><Input type="time" value={shiftForm.start_time} onChange={(e) => setShiftForm({ ...shiftForm, start_time: e.target.value })} /></Field>
            <Field label="End"><Input type="time" value={shiftForm.end_time} onChange={(e) => setShiftForm({ ...shiftForm, end_time: e.target.value })} /></Field>
            <Field label="Std hours"><Input type="number" step="0.5" value={shiftForm.standard_hours} onChange={(e) => setShiftForm({ ...shiftForm, standard_hours: e.target.value })} /></Field></div></form></Modal>}
    </div>
  )
}
