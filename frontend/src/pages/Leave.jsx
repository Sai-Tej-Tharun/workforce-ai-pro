import { useState } from 'react'
import { Plus, Check, X } from 'lucide-react'
import { api, errMsg, fmt } from '../api'
import { useAuth } from '../context/AuthContext'
import { useApp } from '../context/AppContext'
import { useFetch } from '../hooks/useFetch'
import { Card, PageHeader, Tabs, DataTable, Pagination, Badge, Select, Input, Field, Modal, ErrorBox, Progress, Empty } from '../components/ui'

export default function Leave() {
  const { is, user } = useAuth()
  const { toast } = useApp()
  const staff = is('ADMIN', 'HR', 'MANAGER'), hr = is('ADMIN', 'HR')
  const [tab, setTab] = useState('requests')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [apply, setApply] = useState(null)
  const [review, setReview] = useState(null)
  const [err, setErr] = useState('')
  const list = useFetch('/leave', { status: status || undefined, page, size: 12 })
  const policies = useFetch('/leave/policies')
  const bal = useFetch('/leave/balance', {}, { enabled: !!user.employee_id })
  const report = useFetch('/leave/report', {}, { enabled: hr && tab === 'report' })
  const reload = () => { list.reload(); bal.reload() }
  const submit = async (e) => {
    e.preventDefault(); setErr('')
    try { await api.post('/leave', apply); toast('Leave request submitted', 'success'); setApply(null); reload() } catch (x) { setErr(errMsg(x)) }
  }
  const doReview = async () => {
    try { await api.patch(`/leave/${review.row.id}/review`, { action: review.action, comment: review.comment || null }); toast(`Request ${review.action}d`, 'success'); setReview(null); reload() } catch (x) { toast(errMsg(x), 'error'); setReview(null) }
  }
  const cancel = async (id) => { try { await api.post(`/leave/${id}/cancel`); reload() } catch (x) { toast(errMsg(x), 'error') } }
  const today = new Date().toISOString().slice(0, 10)
  return (
    <div>
      <PageHeader title="Leave Management" subtitle="Apply, approve and track leave" actions={user.employee_id && <button className="btn-primary" onClick={() => setApply({ leave_type: 'Annual', start_date: today, end_date: today, reason: '' })}><Plus size={16} />Apply for leave</button>} />
      {bal.data && <div className="mb-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{bal.data.map((b) => (
        <div key={b.leave_type} className="card p-4"><div className="flex justify-between text-sm"><span className="font-medium">{b.leave_type}</span><span className="text-slate-500">{b.remaining} / {b.quota} left</span></div>
          <div className="mt-2"><Progress value={(b.used + b.pending) / (b.quota || 1) * 100} tone={b.remaining <= 1 ? 'rose' : 'brand'} /></div>
          <div className="mt-1.5 text-xs text-slate-400">{b.used} used · {b.pending} pending</div></div>))}</div>}
      <Tabs value={tab} onChange={setTab} tabs={[{ value: 'requests', label: 'Requests' }, { value: 'policies', label: 'Policies' }, ...(hr ? [{ value: 'report', label: 'Report' }] : [])]} />
      {tab === 'requests' && <Card pad={false}>
        <div className="border-b border-slate-100 p-4"><Select className="!w-44" placeholder="All statuses" options={['pending', 'approved', 'rejected', 'cancelled']} value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }} /></div>
        <ErrorBox error={list.error} />
        <DataTable loading={list.loading} rows={list.data?.items} empty={<Empty title="No leave requests" />} columns={[
          ...(staff ? [{ key: 'employee_name', label: 'Employee', render: (r) => <b>{r.employee_name}</b> }] : []), { key: 'leave_type', label: 'Type' },
          { key: 'dates', label: 'Dates', render: (r) => `${fmt.date(r.start_date)} – ${fmt.date(r.end_date)}` }, { key: 'days', label: 'Days' }, { key: 'reason', label: 'Reason', render: (r) => <span className="text-slate-500">{r.reason || '–'}</span> },
          { key: 'status', label: 'Status', render: (r) => <Badge>{r.status}</Badge> },
          { key: 'act', label: '', render: (r) => r.status === 'pending' && <div className="flex gap-1">
            {staff && r.employee_id !== user.employee_id && <><button className="btn-ghost !px-2 !py-1 text-emerald-600" onClick={() => setReview({ row: r, action: 'approve' })}><Check size={14} />Approve</button>
              <button className="btn-ghost !px-2 !py-1 text-rose-600" onClick={() => setReview({ row: r, action: 'reject' })}><X size={14} />Reject</button></>}
            {r.employee_id === user.employee_id && <button className="btn-ghost !px-2 !py-1" onClick={() => cancel(r.id)}>Cancel</button>}</div> }]} />
        <Pagination page={page} size={12} total={list.data?.total} onPage={setPage} /></Card>}
      {tab === 'policies' && <Card pad={false}><DataTable rows={policies.data} columns={[{ key: 'leave_type', label: 'Leave type', render: (r) => <b>{r.leave_type}</b> }, { key: 'annual_quota', label: 'Annual quota (days)' },
        { key: 'carry_forward', label: 'Carry forward', render: (r) => (r.carry_forward ? 'Yes' : 'No') }, { key: 'description', label: 'Description' }]} /></Card>}
      {tab === 'report' && <Card title={`Approved leave ${report.data?.year || ''}`} pad={false}>
        <DataTable loading={report.loading} rowKey="employee_code" rows={report.data?.rows?.map((r, i) => ({ ...r, id: i }))} columns={[{ key: 'employee_name', label: 'Employee' }, { key: 'leave_type', label: 'Type' }, { key: 'days', label: 'Days' }, { key: 'requests', label: 'Requests' }]} />
        {report.data?.by_type && <div className="flex gap-6 border-t border-slate-100 p-4 text-sm">{report.data.by_type.map((t) => <span key={t.leave_type}><b>{t.leave_type}</b>: {t.days} days</span>)}</div>}</Card>}
      {apply && <Modal open onClose={() => setApply(null)} title="Apply for leave" footer={<><button className="btn-ghost" onClick={() => setApply(null)}>Cancel</button><button form="lv" className="btn-primary">Submit</button></>}>
        <form id="lv" onSubmit={submit} className="space-y-3"><ErrorBox error={err} />
          <Field label="Leave type"><Select options={(policies.data || []).map((p) => p.leave_type)} value={apply.leave_type} onChange={(e) => setApply({ ...apply, leave_type: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3"><Field label="From"><Input type="date" required min={today} value={apply.start_date} onChange={(e) => setApply({ ...apply, start_date: e.target.value, end_date: e.target.value > apply.end_date ? e.target.value : apply.end_date })} /></Field>
            <Field label="To"><Input type="date" required min={apply.start_date} value={apply.end_date} onChange={(e) => setApply({ ...apply, end_date: e.target.value })} /></Field></div>
          <Field label="Reason"><Input maxLength={500} value={apply.reason} onChange={(e) => setApply({ ...apply, reason: e.target.value })} /></Field>
          <p className="text-xs text-slate-400">Weekends are excluded automatically. Balance is checked on submit.</p></form></Modal>}
      {review && <Modal open onClose={() => setReview(null)} title={`${review.action === 'approve' ? 'Approve' : 'Reject'} leave`} footer={<><button className="btn-ghost" onClick={() => setReview(null)}>Cancel</button><button className={review.action === 'approve' ? 'btn-primary' : 'btn-danger'} onClick={doReview}>Confirm</button></>}>
        <p className="mb-3 text-sm text-slate-600">{review.row.employee_name} · {review.row.days} day(s) {review.row.leave_type}</p>
        <Field label="Comment (optional)"><Input value={review.comment || ''} onChange={(e) => setReview({ ...review, comment: e.target.value })} /></Field></Modal>}
    </div>
  )
}
