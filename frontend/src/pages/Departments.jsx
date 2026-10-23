import { useState } from 'react'
import { Plus, Pencil, Trash2 } from 'lucide-react'
import { api, errMsg, fmt } from '../api'
import { useAuth } from '../context/AuthContext'
import { useApp } from '../context/AppContext'
import { useFetch } from '../hooks/useFetch'
import { Card, PageHeader, Tabs, DataTable, Modal, Field, Input, Select, ErrorBox, Confirm, RiskBar, Empty } from '../components/ui'

function CrudModal({ title, fields, initial, onClose, onSubmit }) {
  const [f, setF] = useState(initial)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e) => { e.preventDefault(); setBusy(true); setErr(''); try { await onSubmit(f) } catch (x) { setErr(errMsg(x)) } finally { setBusy(false) } }
  return (
    <Modal open onClose={onClose} title={title} footer={<><button className="btn-ghost" onClick={onClose}>Cancel</button><button form="crud" className="btn-primary" disabled={busy}>Save</button></>}>
      <form id="crud" onSubmit={submit} className="space-y-3"><ErrorBox error={err} />
        {fields.map((x) => <Field key={x.key} label={x.label}>
          {x.options ? <Select placeholder="– none –" options={x.options} value={f[x.key] ?? ''} onChange={(e) => setF({ ...f, [x.key]: e.target.value })} />
            : <Input type={x.type || 'text'} required={x.required} min={x.min} max={x.max} value={f[x.key] ?? ''} onChange={(e) => setF({ ...f, [x.key]: e.target.value })} />}</Field>)}
      </form>
    </Modal>
  )
}

export default function Departments() {
  const { is } = useAuth()
  const { toast } = useApp()
  const hr = is('ADMIN', 'HR')
  const [tab, setTab] = useState('departments')
  const [modal, setModal] = useState(null)
  const [del, setDel] = useState(null)
  const stats = useFetch('/departments/stats')
  const roles = useFetch('/roles')
  const depts = useFetch('/departments')
  const emps = useFetch('/employees', { size: 200, status: 'active' }, { enabled: hr && tab === 'assign' })
  const [asg, setAsg] = useState({ employee_id: '', department_id: '', role_id: '' })
  const dOpts = (depts.data || []).map((d) => ({ value: d.id, label: d.name }))
  const refresh = () => { stats.reload(); roles.reload(); depts.reload() }

  const saveDept = async (f) => {
    const body = { name: f.name, description: f.description || null, budget: Number(f.budget || 0) }
    f.id ? await api.put(`/departments/${f.id}`, body) : await api.post('/departments', body)
    toast('Department saved', 'success'); setModal(null); refresh()
  }
  const saveRole = async (f) => {
    const body = { title: f.title, department_id: f.department_id ? Number(f.department_id) : null, level: Number(f.level || 1), min_salary: Number(f.min_salary || 0), max_salary: Number(f.max_salary || 0) }
    f.id ? await api.put(`/roles/${f.id}`, body) : await api.post('/roles', body)
    toast('Role saved', 'success'); setModal(null); refresh()
  }
  const doDelete = async () => {
    try { await api.delete(`/${del.kind}/${del.id}`); toast('Deleted', 'success'); setDel(null); refresh() } catch (x) { toast(errMsg(x), 'error'); setDel(null) }
  }
  const assign = async () => {
    try { await api.post(`/employees/${asg.employee_id}/assign`, { department_id: asg.department_id ? Number(asg.department_id) : null, role_id: asg.role_id ? Number(asg.role_id) : null }); toast('Assignment updated', 'success'); refresh() } catch (x) { toast(errMsg(x), 'error') }
  }
  const actions = (kind, r, edit) => hr && <div className="flex gap-1"><button className="rounded p-1.5 text-slate-400 hover:bg-slate-100" onClick={() => setModal(edit)} aria-label="Edit"><Pencil size={15} /></button>
    <button className="rounded p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-600" onClick={() => setDel({ kind, id: r.id, name: r.name || r.title })} aria-label="Delete"><Trash2 size={15} /></button></div>

  return (
    <div>
      <PageHeader title="Departments & Roles" subtitle="Organisation structure, role assignment and department statistics"
        actions={hr && tab !== 'assign' && <button className="btn-primary" onClick={() => setModal(tab === 'roles' ? { kind: 'role', data: {} } : { kind: 'dept', data: {} })}><Plus size={16} />{tab === 'roles' ? 'New role' : 'New department'}</button>} />
      <Tabs value={tab} onChange={setTab} tabs={[{ value: 'departments', label: 'Departments' }, { value: 'roles', label: 'Roles' }, ...(hr ? [{ value: 'assign', label: 'Assignment' }] : [])]} />
      {tab === 'departments' && <Card pad={false}><DataTable loading={stats.loading} rows={stats.data} columns={[
        { key: 'name', label: 'Department', render: (r) => <b>{r.name}</b> }, { key: 'headcount', label: 'Headcount' },
        { key: 'avg_salary', label: 'Avg salary', render: (r) => fmt.money(r.avg_salary) }, { key: 'payroll_monthly', label: 'Monthly payroll', render: (r) => fmt.money(r.payroll_monthly) },
        { key: 'budget', label: 'Budget', render: (r) => fmt.money(r.budget) }, { key: 'avg_satisfaction', label: 'Satisfaction', render: (r) => `${r.avg_satisfaction}/4` },
        { key: 'avg_risk', label: 'Avg risk', render: (r) => r.avg_risk == null ? '–' : <RiskBar score={r.avg_risk} /> }, { key: 'high_risk', label: 'High risk' },
        { key: 'a', label: '', render: (r) => actions('departments', r, { kind: 'dept', data: { id: r.id, name: r.name, description: depts.data?.find((d) => d.id === r.id)?.description, budget: r.budget } }) }]} /></Card>}
      {tab === 'roles' && <Card pad={false}><DataTable loading={roles.loading} rows={roles.data} columns={[
        { key: 'title', label: 'Role', render: (r) => <b>{r.title}</b> }, { key: 'dept', label: 'Department', render: (r) => dOpts.find((d) => d.value === r.department_id)?.label || '–' },
        { key: 'level', label: 'Level' }, { key: 'sal', label: 'Salary band', render: (r) => `${fmt.money(r.min_salary)} – ${fmt.money(r.max_salary)}` },
        { key: 'a', label: '', render: (r) => actions('roles', r, { kind: 'role', data: r }) }]} /></Card>}
      {tab === 'assign' && <Card title="Assign department & role to an employee" subtitle="Updates the employee–department mapping">
        <div className="grid max-w-3xl gap-3 sm:grid-cols-3">
          <Field label="Employee"><Select placeholder="Select…" options={(emps.data?.items || []).map((e) => ({ value: e.id, label: `${e.first_name} ${e.last_name} (${e.department_name || '–'})` }))} value={asg.employee_id} onChange={(e) => setAsg({ ...asg, employee_id: e.target.value })} /></Field>
          <Field label="Department"><Select placeholder="– none –" options={dOpts} value={asg.department_id} onChange={(e) => setAsg({ ...asg, department_id: e.target.value, role_id: '' })} /></Field>
          <Field label="Role"><Select placeholder="– none –" options={(roles.data || []).filter((r) => !asg.department_id || r.department_id === Number(asg.department_id)).map((r) => ({ value: r.id, label: r.title }))} value={asg.role_id} onChange={(e) => setAsg({ ...asg, role_id: e.target.value })} /></Field></div>
        <button className="btn-primary mt-4" disabled={!asg.employee_id} onClick={assign}>Apply assignment</button></Card>}
      {modal?.kind === 'dept' && <CrudModal title={modal.data.id ? 'Edit department' : 'New department'} initial={modal.data} onClose={() => setModal(null)} onSubmit={saveDept}
        fields={[{ key: 'name', label: 'Name', required: true }, { key: 'description', label: 'Description' }, { key: 'budget', label: 'Annual budget', type: 'number', min: 0 }]} />}
      {modal?.kind === 'role' && <CrudModal title={modal.data.id ? 'Edit role' : 'New role'} initial={modal.data} onClose={() => setModal(null)} onSubmit={saveRole}
        fields={[{ key: 'title', label: 'Title', required: true }, { key: 'department_id', label: 'Department', options: dOpts }, { key: 'level', label: 'Level (1-5)', type: 'number', min: 1, max: 5 }, { key: 'min_salary', label: 'Min salary', type: 'number' }, { key: 'max_salary', label: 'Max salary', type: 'number' }]} />}
      <Confirm open={!!del} onCancel={() => setDel(null)} onConfirm={doDelete} message={`Delete "${del?.name}"? This cannot be undone.`} />
    </div>
  )
}
