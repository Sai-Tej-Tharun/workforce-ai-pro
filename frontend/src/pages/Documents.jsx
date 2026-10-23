import { useRef, useState } from 'react'
import { Upload, Download, Trash2, FileText } from 'lucide-react'
import { api, errMsg, fmt, download } from '../api'
import { useAuth } from '../context/AuthContext'
import { useApp } from '../context/AppContext'
import { useFetch } from '../hooks/useFetch'
import { Card, PageHeader, DataTable, Badge, Select, Field, Empty, Confirm } from '../components/ui'

const TYPES = ['resume', 'id_proof', 'contract', 'certificate', 'offer_letter', 'payslip', 'other']
const ALLOWED = ['.pdf', '.png', '.jpg', '.jpeg', '.docx', '.xlsx', '.txt', '.csv']
const size = (b) => (b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`)

export default function Documents() {
  const { is, user } = useAuth()
  const { toast } = useApp()
  const hr = is('ADMIN', 'HR')
  const [emp, setEmp] = useState('')
  const [type, setType] = useState('other')
  const [busy, setBusy] = useState(false)
  const [del, setDel] = useState(null)
  const [drag, setDrag] = useState(false)
  const input = useRef()
  const emps = useFetch('/employees', { size: 200, status: 'active' }, { enabled: hr })
  const docs = useFetch('/documents', { employee_id: emp || undefined })
  const upload = async (file) => {
    if (!file) return
    const ext = '.' + file.name.split('.').pop().toLowerCase()
    if (!ALLOWED.includes(ext)) return toast(`File type ${ext} is not allowed (${ALLOWED.join(', ')})`, 'error')
    if (file.size > 10 * 1024 * 1024) return toast('File exceeds 10 MB', 'error')
    const fd = new FormData(); fd.append('file', file); fd.append('doc_type', type); if (hr && emp) fd.append('employee_id', emp)
    setBusy(true)
    try { await api.post('/documents', fd); toast('Document uploaded', 'success'); docs.reload() } catch (x) { toast(errMsg(x), 'error') } finally { setBusy(false); if (input.current) input.current.value = '' }
  }
  const remove = async () => { try { await api.delete(`/documents/${del.id}`); toast('Deleted', 'success'); setDel(null); docs.reload() } catch (x) { toast(errMsg(x), 'error'); setDel(null) } }
  const empName = (id) => { const e = emps.data?.items?.find((x) => x.id === id); return e ? `${e.first_name} ${e.last_name}` : `#${id}` }
  return (
    <div>
      <PageHeader title="Documents" subtitle="Employee documents with type and content validation" />
      <Card className="mb-5">
        <div className="grid gap-4 md:grid-cols-[1fr_auto]">
          <div onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)} onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files[0]) }}
            className={`flex cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed p-8 text-center ${drag ? 'border-brand-500 bg-brand-50' : 'border-slate-300'}`} onClick={() => input.current.click()}>
            <Upload className="text-slate-400" /><div className="text-sm font-medium">{busy ? 'Uploading…' : 'Drop a file here or click to browse'}</div><div className="text-xs text-slate-400">{ALLOWED.join(' ')} · max 10 MB</div>
            <input ref={input} type="file" hidden accept={ALLOWED.join(',')} onChange={(e) => upload(e.target.files[0])} /></div>
          <div className="space-y-3 md:w-64"><Field label="Document type"><Select options={TYPES} value={type} onChange={(e) => setType(e.target.value)} /></Field>
            {hr && <Field label="Employee"><Select placeholder="Myself" options={(emps.data?.items || []).map((e) => ({ value: e.id, label: `${e.first_name} ${e.last_name}` }))} value={emp} onChange={(e) => setEmp(e.target.value)} /></Field>}</div></div>
      </Card>
      <Card title="Files" pad={false}>
        <DataTable loading={docs.loading} rows={docs.data} empty={<Empty title="No documents" hint="Uploaded files appear here." />} columns={[
          { key: 'original_name', label: 'File', render: (r) => <span className="flex items-center gap-2"><FileText size={16} className="text-slate-400" />{r.original_name}</span> },
          { key: 'doc_type', label: 'Type', render: (r) => <Badge tone="info">{r.doc_type}</Badge> }, ...(hr ? [{ key: 'employee_id', label: 'Employee', render: (r) => empName(r.employee_id) }] : []),
          { key: 'size_bytes', label: 'Size', render: (r) => size(r.size_bytes) }, { key: 'created_at', label: 'Uploaded', render: (r) => fmt.dt(r.created_at) },
          { key: 'a', label: '', render: (r) => <div className="flex gap-1"><button className="rounded p-1.5 text-slate-500 hover:bg-slate-100" onClick={() => download(`/documents/${r.id}/download`)} aria-label="Download"><Download size={15} /></button>
            <button className="rounded p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-600" onClick={() => setDel(r)} aria-label="Delete"><Trash2 size={15} /></button></div> }]} />
      </Card>
      <Confirm open={!!del} onCancel={() => setDel(null)} onConfirm={remove} message={`Delete "${del?.original_name}"?`} />
    </div>
  )
}
