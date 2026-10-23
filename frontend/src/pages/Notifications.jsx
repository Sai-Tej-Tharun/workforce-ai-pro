import { useState } from 'react'
import { Check, Trash2, Send } from 'lucide-react'
import { api, errMsg, fmt } from '../api'
import { useAuth } from '../context/AuthContext'
import { useApp, useLive } from '../context/AppContext'
import { useFetch } from '../hooks/useFetch'
import { Card, PageHeader, Tabs, Badge, Pagination, Empty, Loading, Select, Input, Field, Modal, ErrorBox, DataTable, cx } from '../components/ui'

export default function Notifications() {
  const { is } = useAuth()
  const { toast, refreshUnread, setUnread } = useApp()
  const staff = is('ADMIN', 'HR', 'MANAGER'), hr = is('ADMIN', 'HR')
  const [tab, setTab] = useState('inbox')
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [page, setPage] = useState(1)
  const [alertStatus, setAlertStatus] = useState('')
  const [send, setSend] = useState(null)
  const [err, setErr] = useState('')
  const n = useFetch('/notifications', { unread_only: unreadOnly || undefined, page, size: 12 })
  const alerts = useFetch('/alerts', { status: alertStatus || undefined, size: 50 }, { enabled: staff && tab === 'alerts' })
  const people = useFetch('/chat/contacts', {}, { enabled: !!send })
  useLive(['notification'], () => { if (page === 1) n.reload() })
  const read = async (x) => { if (x.is_read) return; await api.patch(`/notifications/${x.id}/read`); refreshUnread(); n.reload() }
  const readAll = async () => { await api.post('/notifications/read-all'); setUnread(0); n.reload() }
  const del = async (x) => { await api.delete(`/notifications/${x.id}`); refreshUnread(); n.reload() }
  const setAlert = async (a, status) => { try { await api.patch(`/alerts/${a.id}`, { status }); alerts.reload() } catch (x) { toast(errMsg(x), 'error') } }
  const doSend = async (e) => {
    e.preventDefault(); setErr('')
    try { const { data } = await api.post('/notifications/send', { ...send, user_id: send.user_id ? Number(send.user_id) : null }); toast(`Sent to ${data.sent} user(s)`, 'success'); setSend(null) } catch (x) { setErr(errMsg(x)) }
  }
  const PR = { critical: 'critical', high: 'high', medium: 'medium', low: 'low' }
  return (
    <div>
      <PageHeader title="Notifications & Alerts" subtitle="In-app notifications, read status and alert history" actions={<>
        {hr && <button className="btn-ghost" onClick={() => setSend({ user_id: '', title: '', message: '', priority: 'low' })}><Send size={15} />Send notification</button>}
        <button className="btn-ghost" onClick={readAll}><Check size={15} />Mark all read</button></>} />
      <Tabs value={tab} onChange={setTab} tabs={[{ value: 'inbox', label: 'Inbox' }, ...(staff ? [{ value: 'alerts', label: 'AI alert history' }] : [])]} />
      {tab === 'inbox' && <Card pad={false}>
        <div className="border-b border-slate-100 p-3"><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={unreadOnly} onChange={(e) => { setUnreadOnly(e.target.checked); setPage(1) }} />Unread only</label></div>
        {n.loading && !n.data ? <Loading /> : !n.data?.items.length ? <Empty title="No notifications" hint="You're all caught up." /> :
          <ul className="divide-y divide-slate-100">{n.data.items.map((x) => (
            <li key={x.id} onClick={() => read(x)} className={cx('flex cursor-pointer items-start gap-3 px-5 py-3.5 hover:bg-slate-50', !x.is_read && 'bg-brand-50/40')}>
              <span className={cx('mt-1.5 h-2 w-2 shrink-0 rounded-full', x.is_read ? 'bg-transparent' : 'bg-brand-600')} />
              <div className="min-w-0 flex-1"><div className="flex items-center gap-2"><span className="font-medium text-slate-900">{x.title}</span><Badge tone={PR[x.priority]}>{x.priority}</Badge><Badge tone="info">{x.category}</Badge></div>
                <div className="text-sm text-slate-600">{x.message}</div><div className="mt-0.5 text-xs text-slate-400">{fmt.dt(x.created_at)}</div></div>
              <button className="rounded p-1.5 text-slate-300 hover:bg-rose-50 hover:text-rose-600" onClick={(e) => { e.stopPropagation(); del(x) }} aria-label="Delete"><Trash2 size={15} /></button></li>))}</ul>}
        <Pagination page={page} size={12} total={n.data?.total} onPage={setPage} /></Card>}
      {tab === 'alerts' && <Card pad={false}>
        <div className="border-b border-slate-100 p-3"><Select className="!w-44" placeholder="All statuses" options={['open', 'acknowledged', 'resolved']} value={alertStatus} onChange={(e) => setAlertStatus(e.target.value)} /></div>
        <DataTable loading={alerts.loading} rows={alerts.data?.items} empty={<Empty title="No alerts" hint="AI alerts are raised when employees enter high risk." />} columns={[
          { key: 'severity', label: 'Priority', render: (r) => <Badge tone={r.severity}>{r.severity}</Badge> }, { key: 'alert_type', label: 'Type', render: (r) => <Badge tone="info">{r.alert_type}</Badge> },
          { key: 'message', label: 'Message', render: (r) => <span className="text-slate-700">{r.message}</span>, className: 'max-w-md' }, { key: 'status', label: 'Status', render: (r) => <Badge>{r.status}</Badge> },
          { key: 'created_at', label: 'Raised', render: (r) => fmt.ago(r.created_at) },
          { key: 'a', label: '', render: (r) => r.status !== 'resolved' && <div className="flex gap-1">{r.status === 'open' && <button className="btn-ghost !px-2 !py-1 text-xs" onClick={() => setAlert(r, 'acknowledged')}>Acknowledge</button>}<button className="btn-ghost !px-2 !py-1 text-xs text-emerald-600" onClick={() => setAlert(r, 'resolved')}>Resolve</button></div> }]} /></Card>}
      {send && <Modal open onClose={() => setSend(null)} title="Send notification" footer={<><button className="btn-ghost" onClick={() => setSend(null)}>Cancel</button><button form="sn" className="btn-primary">Send</button></>}>
        <form id="sn" onSubmit={doSend} className="space-y-3"><ErrorBox error={err} />
          <Field label="Recipient"><Select placeholder="Everyone (broadcast)" options={(people.data || []).map((p) => ({ value: p.id, label: `${p.full_name} (${p.role})` }))} value={send.user_id} onChange={(e) => setSend({ ...send, user_id: e.target.value })} /></Field>
          <Field label="Title"><Input required maxLength={200} value={send.title} onChange={(e) => setSend({ ...send, title: e.target.value })} /></Field>
          <Field label="Message"><Input required maxLength={600} value={send.message} onChange={(e) => setSend({ ...send, message: e.target.value })} /></Field>
          <Field label="Priority"><Select options={['low', 'medium', 'high', 'critical']} value={send.priority} onChange={(e) => setSend({ ...send, priority: e.target.value })} /></Field></form></Modal>}
    </div>
  )
}
