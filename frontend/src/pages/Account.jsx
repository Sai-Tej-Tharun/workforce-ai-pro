import { useState } from 'react'
import { api, errMsg, fmt } from '../api'
import { useAuth } from '../context/AuthContext'
import { useApp } from '../context/AppContext'
import { useFetch } from '../hooks/useFetch'
import { Card, PageHeader, Field, Input, Badge, ErrorBox, Avatar, DataTable } from '../components/ui'

export default function Account() {
  const { user } = useAuth()
  const { toast } = useApp()
  const [f, setF] = useState({ current_password: '', new_password: '' })
  const [err, setErr] = useState('')
  const { data: act } = useFetch('/audit/my-activity', { limit: 10 })
  const submit = async (e) => {
    e.preventDefault(); setErr('')
    try { await api.post('/auth/change-password', f); toast('Password changed', 'success'); setF({ current_password: '', new_password: '' }) } catch (x) { setErr(errMsg(x)) }
  }
  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <PageHeader title="My account" subtitle="Profile, security and recent activity" />
      <div className="grid gap-5 md:grid-cols-2">
        <Card title="Profile">
          <div className="flex items-center gap-4"><Avatar name={user.full_name} size={56} />
            <div><div className="font-semibold">{user.full_name}</div><div className="text-sm text-slate-500">{user.email}</div><div className="mt-1"><Badge tone="info">{user.role}</Badge></div></div></div>
          <div className="mt-4 text-xs text-slate-400">Last sign-in: {fmt.dt(user.last_login)}</div>
        </Card>
        <Card title="Change password">
          <form onSubmit={submit} className="space-y-3"><ErrorBox error={err} />
            <Field label="Current password"><Input type="password" required value={f.current_password} onChange={(e) => setF({ ...f, current_password: e.target.value })} /></Field>
            <Field label="New password" hint="Min 8 characters, letters and digits"><Input type="password" required minLength={8} value={f.new_password} onChange={(e) => setF({ ...f, new_password: e.target.value })} /></Field>
            <button className="btn-primary">Update password</button></form>
        </Card>
      </div>
      <Card title="My recent activity" pad={false}>
        <DataTable rows={act || []} columns={[
          { key: 'created_at', label: 'When', render: (r) => fmt.dt(r.created_at) }, { key: 'action', label: 'Action', render: (r) => <Badge tone="info">{r.action}</Badge> },
          { key: 'entity', label: 'Entity' }, { key: 'ip_address', label: 'IP' }]} />
      </Card>
    </div>
  )
}
