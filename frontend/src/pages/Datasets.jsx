import { useRef, useState } from 'react'
import { Upload, Download, Cpu, Trash2, Check, FileSpreadsheet } from 'lucide-react'
import { api, errMsg, fmt, download } from '../api'
import { useApp } from '../context/AppContext'
import { useFetch } from '../hooks/useFetch'
import { Card, PageHeader, DataTable, Badge, Modal, Empty, ErrorBox, Tabs, Confirm, Field, Input } from '../components/ui'

export default function Datasets() {
  const { toast } = useApp()
  const ds = useFetch('/datasets')
  const models = useFetch('/models')
  const [tab, setTab] = useState('datasets')
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(null)
  const [report, setReport] = useState(null)
  const [del, setDel] = useState(null)
  const [upErr, setUpErr] = useState('')
  const [result, setResult] = useState(null)
  const input = useRef()

  const upload = async (file) => {
    if (!file) return
    setUpErr(''); setBusy('upload')
    const fd = new FormData(); fd.append('file', file); if (name) fd.append('name', name)
    try { const { data } = await api.post('/datasets/upload', fd); toast(`Uploaded v${data.version}: ${data.rows_valid} valid, ${data.rows_failed} failed, ${data.rows_duplicate} duplicates`, data.rows_failed ? 'warning' : 'success'); ds.reload() } catch (x) { setUpErr(errMsg(x)) } finally { setBusy(null); input.current.value = '' }
  }
  const train = async (d) => {
    setBusy(`t${d.id}`)
    try { const { data } = await api.post(`/datasets/${d.id}/train`); setResult(data); toast(`Model trained – ROC-AUC ${data.roc_auc}`, 'success'); models.reload() } catch (x) { toast(errMsg(x), 'error') } finally { setBusy(null) }
  }
  const activate = async (m) => { try { await api.post(`/models/${m.id}/activate`); toast('Model activated', 'success'); models.reload() } catch (x) { toast(errMsg(x), 'error') } }
  const remove = async () => { try { await api.delete(`/datasets/${del.id}`); setDel(null); ds.reload() } catch (x) { toast(errMsg(x), 'error') } }
  const openReport = async (d) => { const { data } = await api.get(`/datasets/${d.id}`); setReport(data) }

  return (
    <div>
      <PageHeader title="Datasets & Models" subtitle="Upload, validate and version HR datasets; train and activate prediction models" actions={<button className="btn-ghost" onClick={() => download('/datasets/template', {}, 'dataset_template.csv')}><Download size={15} />CSV template</button>} />
      <Card title="Upload dataset" subtitle="CSV or Excel. Required: attrition, age, monthly_income, job_satisfaction, years_at_company, overtime. IBM-HR column names are recognised automatically." className="mb-5">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Dataset name (new version if it exists)"><Input className="!w-72" placeholder="hr_attrition_baseline" value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <button className="btn-primary" disabled={busy === 'upload'} onClick={() => input.current.click()}><Upload size={15} />{busy === 'upload' ? 'Validating…' : 'Choose file'}</button>
          <input ref={input} type="file" hidden accept=".csv,.xlsx" onChange={(e) => upload(e.target.files[0])} /></div>
        <div className="mt-3"><ErrorBox error={upErr} /></div>
      </Card>
      <Tabs value={tab} onChange={setTab} tabs={[{ value: 'datasets', label: 'Datasets', count: ds.data?.length }, { value: 'models', label: 'Trained models', count: models.data?.length }]} />
      {tab === 'datasets' && <Card pad={false}><DataTable loading={ds.loading} rows={ds.data} empty={<Empty title="No datasets" hint="Upload one above (sample: sample_data/hr_attrition_sample.csv)." />} columns={[
        { key: 'name', label: 'Dataset', render: (r) => <span className="flex items-center gap-2"><FileSpreadsheet size={16} className="text-slate-400" /><b>{r.name}</b><Badge tone="info">v{r.version}</Badge></span> },
        { key: 'rows_total', label: 'Rows' }, { key: 'rows_valid', label: 'Valid', render: (r) => <span className="text-emerald-600">{r.rows_valid}</span> },
        { key: 'rows_failed', label: 'Failed', render: (r) => r.rows_failed ? <button className="font-medium text-rose-600 underline" onClick={() => openReport(r)}>{r.rows_failed}</button> : 0 },
        { key: 'rows_duplicate', label: 'Duplicates' }, { key: 'attrition_rate', label: 'Attrition rate', render: (r) => fmt.pct(r.attrition_rate, 1) }, { key: 'created_at', label: 'Uploaded', render: (r) => fmt.dt(r.created_at) },
        { key: 'a', label: '', render: (r) => <div className="flex gap-1"><button className="btn-primary !px-2.5 !py-1 text-xs" disabled={!!busy} onClick={() => train(r)}><Cpu size={13} />{busy === `t${r.id}` ? 'Training…' : 'Train'}</button>
          <button className="rounded p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-600" onClick={() => setDel(r)} aria-label="Delete dataset"><Trash2 size={15} /></button></div> }]} /></Card>}
      {tab === 'models' && <Card pad={false}><DataTable loading={models.loading} rows={models.data} empty={<Empty title="No models yet" />} columns={[
        { key: 'id', label: 'Model', render: (r) => <span><b>#{r.id}</b> {r.algorithm} {r.is_active && <Badge tone="low">active</Badge>}</span> }, { key: 'roc_auc', label: 'ROC-AUC' }, { key: 'cv_roc_auc', label: 'CV AUC' },
        { key: 'accuracy', label: 'Accuracy', render: (r) => fmt.pct(r.accuracy, 1) }, { key: 'precision', label: 'Precision', render: (r) => fmt.pct(r.precision, 1) }, { key: 'recall', label: 'Recall', render: (r) => fmt.pct(r.recall, 1) }, { key: 'f1', label: 'F1' },
        { key: 'comparison', label: 'Candidates (CV AUC)', render: (r) => <span className="text-xs text-slate-500">{r.comparison?.map((c) => `${c.algorithm.replace('Classifier', '')} ${c.cv_roc_auc}`).join(' · ')}</span> },
        { key: 'created_at', label: 'Trained', render: (r) => fmt.ago(r.created_at) }, { key: 'a', label: '', render: (r) => !r.is_active && <button className="btn-ghost !px-2 !py-1 text-xs" onClick={() => activate(r)}><Check size={13} />Activate</button> }]} /></Card>}
      {report && <Modal open onClose={() => setReport(null)} wide title={`Failed records – ${report.name} v${report.version}`} footer={<><button className="btn-ghost" onClick={() => download(`/datasets/${report.id}/failed-report`)}><Download size={15} />Download CSV</button><button className="btn-primary" onClick={() => setReport(null)}>Close</button></>}>
        <div className="max-h-96 overflow-y-auto"><DataTable rowKey="row" dense rows={report.failed_report} columns={[{ key: 'row', label: 'Row (incl. header)' }, { key: 'reason', label: 'Reason' }]} /></div></Modal>}
      {result && <Modal open onClose={() => setResult(null)} title="Training complete" footer={<button className="btn-primary" onClick={() => setResult(null)}>Done</button>}>
        <div className="grid grid-cols-2 gap-3 text-sm"><div>Algorithm: <b>{result.algorithm}</b></div><div>ROC-AUC: <b>{result.roc_auc}</b></div><div>Accuracy: <b>{fmt.pct(result.accuracy, 1)}</b></div><div>Majority baseline: <b>{fmt.pct(result.majority_baseline_accuracy, 1)}</b></div>
          <div>Precision: <b>{fmt.pct(result.precision, 1)}</b></div><div>Recall: <b>{fmt.pct(result.recall, 1)}</b></div><div>F1: <b>{result.f1}</b></div><div>Decision threshold: <b>{result.threshold}</b></div></div>
        <p className="mt-3 text-xs text-slate-500">The model is now active. Run predictions for all employees on the AI Predictions page to refresh risk scores.</p></Modal>}
      <Confirm open={!!del} onCancel={() => setDel(null)} onConfirm={remove} message={`Delete dataset "${del?.name}" v${del?.version}? Models trained on it are kept.`} />
    </div>
  )
}
