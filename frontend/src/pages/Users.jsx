import { useState } from 'react'
import { Plus } from 'lucide-react'
import { api, errMsg, fmt } from '../api'
import { useAuth } from '../context/AuthContext'
import { useApp } from '../context/AppContext'
import { useFetch } from '../hooks/useFetch'
import { Card, PageHeader, DataTable, Badge, Modal, Field, Input, Select, ErrorBox, Avatar } from '../components/ui'

export default function Users() {
  const { is, user: me } = useAuth()
  const { toast } = useApp()
  const admin = is('ADMIN')
  const users = useFetch('/users')
  const emps = useFetch('/employees', { size: 200 }, { enabled: admin })
  const [form, setForm] = useState(null)
  const [err, setErr] = useState('')
  const patch = async (u, body) => { try { await api.patch(`/users/${u.id}`, body); toast('User updated', 'success'); users.reload() } catch (x) { toast(errMsg(x), 'error') } }
  const create = async (e) => {
    e.preventDefault(); setErr('')
    try { await api.post('/users', { ...form, employee_id: form.employee_id ? Number(form.employee_id) : null }); setForm(null); users.reload(); toast('User created', 'success') } catch (x) { setErr(errMsg(x)) }
  }
  return (
    <div>
      <PageHeader title="User Management" subtitle={admin ? 'Create accounts, assign roles (RBAC) and activate/deactivate users' : 'Read-only view (Admin can edit)'} actions={admin && <button className="btn-primary" onClick={() => setForm({ full_name: '', email: '', password: '', role: 'EMPLOYEE', employee_id: '' })}><Plus size={16} />New user</button>} />
      <Card pad={false}><ErrorBox error={users.error} />
        <DataTable loading={users.loading} rows={users.data} columns={[
          { key: 'full_name', label: 'User', render: (u) => <div className="flex items-center gap-3"><Avatar name={u.full_name} /><div><div className="font-medium">{u.full_name}</div><div className="text-xs text-slate-400">{u.email}</div></div></div> },
          { key: 'role', label: 'Role', render: (u) => admin && u.id !== me.id ? <Select className="!w-36 !py-1" options={['ADMIN', 'HR', 'MANAGER', 'EMPLOYEE']} value={u.role} onChange={(e) => patch(u, { role: e.target.value })} /> : <Badge tone="info">{u.role}</Badge> },
          { key: 'is_active', label: 'Status', render: (u) => <Badge tone={u.is_active ? 'active' : 'terminated'}>{u.is_active ? 'active' : 'disabled'}</Badge> },
          { key: 'last_login', label: 'Last login', render: (u) => fmt.dt(u.last_login) },
          { key: 'a', label: '', render: (u) => admin && u.id !== me.id && <button className="btn-ghost !px-2 !py-1 text-xs" onClick={() => patch(u, { is_active: !u.is_active })}>{u.is_active ? 'Deactivate' : 'Activate'}</button> }]} /></Card>
      {form && <Modal open onClose={() => setForm(null)} title="New user" footer={<><button className="btn-ghost" onClick={() => setForm(null)}>Cancel</button><button form="uf" className="btn-primary">Create</button></>}>
        <form id="uf" onSubmit={create} className="space-y-3"><ErrorBox error={err} />
          <Field label="Full name"><Input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></Field>
          <Field label="Email"><Input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
          <Field label="Temporary password" hint="Min 8 chars, letters and digits"><Input type="password" required minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3"><Field label="Role"><Select options={['ADMIN', 'HR', 'MANAGER', 'EMPLOYEE']} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} /></Field>
            <Field label="Linked employee"><Select placeholder="– none –" options={(emps.data?.items || []).map((e) => ({ value: e.id, label: `${e.first_name} ${e.last_name}` }))} value={form.employee_id} onChange={(e) => setForm({ ...form, employee_id: e.target.value })} /></Field></div></form></Modal>}
    </div>
  )
}
