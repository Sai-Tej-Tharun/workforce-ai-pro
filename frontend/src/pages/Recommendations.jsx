import { useState } from 'react'
import { Lightbulb, Users, Building2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useFetch } from '../hooks/useFetch'
import { Card, PageHeader, Badge, Select, Loading, Empty, Tabs, DataTable, RiskBar } from '../components/ui'
import { fmt } from '../api'

const Tip = ({ t }) => <li className="flex gap-3 rounded-lg border border-slate-100 bg-white p-3"><Lightbulb size={18} className={t.priority === 'high' ? 'text-rose-500' : t.priority === 'medium' ? 'text-amber-500' : 'text-emerald-500'} />
  <div><div className="flex items-center gap-2 text-sm font-semibold">{t.area}<Badge tone={t.priority === 'high' ? 'high' : t.priority === 'medium' ? 'medium' : 'low'}>{t.priority}</Badge></div><div className="text-sm text-slate-600">{t.recommendation}</div></div></li>

export default function Recommendations() {
  const { is, user } = useAuth()
  const staff = is('ADMIN', 'HR', 'MANAGER')
  const [tab, setTab] = useState(staff ? 'workforce' : 'me')
  const [emp, setEmp] = useState(String(user.employee_id || ''))
  const [dept, setDept] = useState('')
  const emps = useFetch('/employees', { size: 200, status: 'active' }, { enabled: staff })
  const depts = useFetch('/departments')
  const wf = useFetch('/recommendations/workforce', {}, { enabled: staff && tab === 'workforce' })
  const team = useFetch('/recommendations/team', {}, { enabled: staff && tab === 'team' })
  const dr = useFetch(`/recommendations/department/${dept}`, {}, { enabled: staff && tab === 'department' && !!dept })
  const er = useFetch(`/recommendations/employee/${emp}`, {}, { enabled: tab === 'me' && !!emp })
  return (
    <div>
      <PageHeader title="AI Recommendations" subtitle="Rule-based decision support built on risk drivers, performance, attendance and goals" />
      <Tabs value={tab} onChange={setTab} tabs={[...(staff ? [{ value: 'workforce', label: 'Workforce optimisation' }, { value: 'department', label: 'Department' }, { value: 'team', label: 'Team insights' }] : []), { value: 'me', label: staff ? 'Employee' : 'My suggestions' }]} />
      {tab === 'workforce' && (wf.loading ? <Loading /> : <ul className="grid gap-3 lg:grid-cols-2">{wf.data?.map((t, i) => <Tip key={i} t={t} />)}</ul>)}
      {tab === 'department' && <><div className="mb-4 max-w-xs"><Select placeholder="Select department…" options={(depts.data || []).map((d) => ({ value: d.id, label: d.name }))} value={dept} onChange={(e) => setDept(e.target.value)} /></div>
        {dr.data && <Card title={dr.data.department} subtitle={`${dr.data.headcount} employees · avg risk ${fmt.pct(dr.data.avg_risk, 1)}`}>{dr.data.recommendations.length === 0 ? <Empty title="No dominant risk drivers" /> :
          <ul className="space-y-2">{dr.data.recommendations.map((r) => <li key={r.driver} className="rounded-lg bg-slate-50 p-3 text-sm"><b>{r.action}</b> <Badge tone="info">{r.employees_affected} employees</Badge><div className="text-slate-600">{r.detail}</div></li>)}</ul>}</Card>}</>}
      {tab === 'team' && <Card pad={false}><DataTable rowKey="manager" rows={team.data} loading={team.loading} columns={[{ key: 'manager', label: 'Manager', render: (r) => <b>{r.manager}</b> }, { key: 'team_size', label: 'Team' }, { key: 'avg_rating', label: 'Avg rating' }, { key: 'avg_goal_progress', label: 'Goals %' },
        { key: 'avg_risk', label: 'Avg risk', render: (r) => r.avg_risk == null ? '–' : <RiskBar score={r.avg_risk} /> }, { key: 'insights', label: 'Insights', render: (r) => <ul className="text-xs text-slate-600">{r.insights.map((i) => <li key={i}>• {i}</li>)}</ul> }]} /></Card>}
      {tab === 'me' && <>{staff && <div className="mb-4 max-w-xs"><Select placeholder="Select employee…" options={(emps.data?.items || []).map((e) => ({ value: e.id, label: `${e.first_name} ${e.last_name}` }))} value={emp} onChange={(e) => setEmp(e.target.value)} /></div>}
        {!emp ? <Empty title="No employee selected" /> : er.loading ? <Loading /> : er.data && <div className="grid gap-5 lg:grid-cols-2">
          <Card title="Improvement suggestions"><ul className="space-y-2">{er.data.improvement_suggestions.map((t, i) => <Tip key={i} t={{ ...t, recommendation: t.recommendation }} />)}</ul></Card>
          {er.data.retention_actions && <Card title="Retention actions" subtitle={`Current risk level: ${er.data.risk_level || 'n/a'}`}>{er.data.retention_actions.length === 0 ? <Empty title="No retention actions needed" /> :
            <ul className="space-y-2">{er.data.retention_actions.map((a) => <li key={a.title} className="rounded-lg bg-slate-50 p-3 text-sm"><b>{a.title}</b> <span className="text-xs text-slate-400">driver: {a.driver}</span><div className="text-slate-600">{a.action}</div></li>)}</ul>}</Card>}</div>}</>}
    </div>
  )
}
