import { useState } from 'react'
import { Brain, Play, Target, Gauge, ShieldCheck, Download } from 'lucide-react'
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell } from 'recharts'
import { api, errMsg, fmt, download } from '../api'
import { useAuth } from '../context/AuthContext'
import { useApp, useLive } from '../context/AppContext'
import { useFetch, useDebounced } from '../hooks/useFetch'
import { Card, PageHeader, StatCard, DataTable, Pagination, RiskBadge, Badge, Select, Input, ErrorBox, Empty, RiskBar, Tabs } from '../components/ui'

export default function Predictions() {
  const { is } = useAuth()
  const { toast } = useApp()
  const hr = is('ADMIN', 'HR')
  const [tab, setTab] = useState('employees')
  const [q, setQ] = useState({ risk_level: '', department_id: '', search: '' })
  const [page, setPage] = useState(1)
  const [busy, setBusy] = useState(false)
  const search = useDebounced(q.search)
  const model = useFetch('/models/active')
  const preds = useFetch('/ai/predictions/latest', { ...Object.fromEntries(Object.entries({ ...q, search }).filter(([, v]) => v)), page, size: 12 })
  const depPred = useFetch('/ai/predictions/departments')
  const depts = useFetch('/departments')
  useLive(['risk_update'], () => { preds.reload(); depPred.reload() })
  const m = model.data
  const runAll = async () => {
    setBusy(true)
    try { const { data } = await api.post('/ai/predict/all'); toast(`Predicted ${data.predicted} employees: ${data.high} high, ${data.medium} medium, ${data.low} low`, 'success'); preds.reload(); depPred.reload() } catch (x) { toast(errMsg(x), 'error') } finally { setBusy(false) }
  }
  const imp = m ? Object.entries(m.feature_importance || {}).slice(0, 8).map(([k, v]) => ({ name: k.replace(/_/g, ' '), value: +(v * 100).toFixed(2) })) : []
  return (
    <div>
      <PageHeader title="AI Prediction Engine" subtitle="Attrition risk %, confidence, explainable drivers and department-level predictions" actions={<>
        <button className="btn-ghost" onClick={() => download('/reports/attrition', { format: 'xlsx' })}><Download size={15} />Export</button>
        {hr && <button className="btn-primary" disabled={busy || !m} onClick={runAll}><Play size={15} />{busy ? 'Running…' : 'Run predictions for all'}</button>}</>} />
      {model.error ? <Card><Empty title="No active model" hint={hr ? 'Go to Datasets & Models, upload a dataset and train a model.' : 'Ask HR to train a model.'} /></Card> : m && <>
        <div className="mb-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Model" value={m.algorithm} hint={`Trained ${fmt.ago(m.created_at)} on ${m.train_rows} rows`} icon={Brain} />
          <StatCard label="ROC-AUC" value={m.roc_auc} hint={`cross-val ${m.cv_roc_auc}`} icon={Gauge} tone="emerald" />
          <StatCard label="Accuracy" value={fmt.pct(m.accuracy, 1)} hint={`F1 ${m.f1}`} icon={Target} tone="sky" />
          <StatCard label="Precision / Recall" value={`${fmt.pct(m.precision)} / ${fmt.pct(m.recall)}`} hint="on held-out test set" icon={ShieldCheck} tone="amber" />
        </div>
        <Card title="What drives attrition in this model" subtitle="Permutation importance (drop in ROC-AUC when the feature is shuffled)" className="mb-5">
          <div className="h-60"><ResponsiveContainer><BarChart data={imp} layout="vertical" margin={{ left: 40 }}><CartesianGrid strokeDasharray="3 3" horizontal={false} /><XAxis type="number" fontSize={11} unit="%" /><YAxis type="category" dataKey="name" fontSize={11} width={150} /><Tooltip formatter={(v) => `${v}%`} />
            <Bar dataKey="value" radius={[0, 4, 4, 0]}>{imp.map((_, i) => <Cell key={i} fill={i < 3 ? '#6366f1' : '#a5b4fc'} />)}</Bar></BarChart></ResponsiveContainer></div></Card></>}
      <Tabs value={tab} onChange={setTab} tabs={[{ value: 'employees', label: 'Employee predictions', count: preds.data?.total }, { value: 'departments', label: 'Department predictions' }]} />
      {tab === 'employees' ? <Card pad={false}>
        <div className="flex flex-wrap gap-3 border-b border-slate-100 p-4">
          <Input className="!w-60" placeholder="Search employee…" value={q.search} onChange={(e) => { setQ({ ...q, search: e.target.value }); setPage(1) }} />
          <Select className="!w-44" placeholder="All departments" options={(depts.data || []).map((d) => ({ value: d.id, label: d.name }))} value={q.department_id} onChange={(e) => { setQ({ ...q, department_id: e.target.value }); setPage(1) }} />
          <Select className="!w-36" placeholder="Any risk" options={['high', 'medium', 'low']} value={q.risk_level} onChange={(e) => { setQ({ ...q, risk_level: e.target.value }); setPage(1) }} /></div>
        <ErrorBox error={preds.error} />
        <DataTable loading={preds.loading} rows={preds.data?.items} rowKey="employee_id" empty={<Empty title="No predictions" hint="Run predictions for all employees." />} columns={[
          { key: 'employee_name', label: 'Employee', render: (r) => <div><b>{r.employee_name}</b><div className="text-xs text-slate-400">{r.department}</div></div> },
          { key: 'risk', label: 'Risk', render: (r) => <RiskBar score={r.risk_score} /> }, { key: 'level', label: 'Level', render: (r) => <RiskBadge level={r.risk_level} /> },
          { key: 'conf', label: 'Confidence', render: (r) => `${r.confidence_percentage}%` },
          { key: 'f', label: 'Top drivers', render: (r) => <div className="flex flex-wrap gap-1">{r.top_factors.slice(0, 3).map((f) => <Badge key={f.feature} tone="info">{f.label} +{f.impact}</Badge>)}</div> },
          { key: 't', label: 'Updated', render: (r) => <span className="text-xs text-slate-400">{fmt.ago(r.created_at)}</span> }]} />
        <Pagination page={page} size={12} total={preds.data?.total} onPage={setPage} /></Card> :
        <Card pad={false}><DataTable loading={depPred.loading} rows={depPred.data} rowKey="department" columns={[
          { key: 'department', label: 'Department', render: (r) => <b>{r.department}</b> }, { key: 'headcount', label: 'Headcount' },
          { key: 'avg_risk', label: 'Avg risk', render: (r) => <RiskBar score={r.avg_risk} /> }, { key: 'expected_leavers_12m', label: 'Expected leavers (12m)', render: (r) => <b>{r.expected_leavers_12m}</b> },
          { key: 'high', label: 'High', render: (r) => <Badge tone="high">{r.high}</Badge> }, { key: 'medium', label: 'Medium', render: (r) => <Badge tone="medium">{r.medium}</Badge> }, { key: 'low', label: 'Low', render: (r) => <Badge tone="low">{r.low}</Badge> },
          { key: 'avg_confidence', label: 'Avg confidence', render: (r) => fmt.pct(r.avg_confidence) }]} /></Card>}
    </div>
  )
}
