import { useState } from 'react'
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, Legend, BarChart, Bar, Line, ComposedChart } from 'recharts'
import { useFetch } from '../hooks/useFetch'
import { Card, PageHeader, StatCard, Loading, ErrorBox, DataTable, Badge, Field, Input, Select, Progress } from '../components/ui'
import { fmt } from '../api'
import { TrendingUp, UserMinus, Users, ShieldCheck } from 'lucide-react'

export default function Forecast() {
  const [months, setMonths] = useState(12)
  const [hires, setHires] = useState('')
  const [dept, setDept] = useState('')
  const depts = useFetch('/departments')
  const f = useFetch('/analytics/forecast', { months, monthly_hires: hires === '' ? undefined : Number(hires), department_id: dept || undefined })
  const st = useFetch('/analytics/stability')
  const d = f.data
  return (
    <div>
      <PageHeader title="Forecast & Stability" subtitle="Survival-model attrition forecast, workforce growth projection and department stability scores" />
      <Card className="mb-5"><div className="flex flex-wrap items-end gap-3">
        <Field label="Horizon"><Select className="!w-36" options={[6, 12, 24, 36].map((m) => ({ value: m, label: `${m} months` }))} value={months} onChange={(e) => setMonths(Number(e.target.value))} /></Field>
        <Field label="Department"><Select className="!w-48" placeholder="Whole company" options={(depts.data || []).map((x) => ({ value: x.id, label: x.name }))} value={dept} onChange={(e) => setDept(e.target.value)} /></Field>
        <Field label="Hires / month" hint={d ? `blank = historical rate (${d.monthly_hires_assumed})` : ''}><Input className="!w-32" type="number" min="0" step="0.5" placeholder="auto" value={hires} onChange={(e) => setHires(e.target.value)} /></Field></div></Card>
      <ErrorBox error={f.error} onRetry={f.reload} />
      {f.loading && !d ? <Loading /> : d && <>
        <div className="mb-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Current headcount" value={d.current_headcount} icon={Users} /><StatCard label={`Expected leavers (${months}m)`} value={d.months.at(-1).cumulative_leavers} hint={`avg risk ${fmt.pct(d.avg_risk, 1)}`} icon={UserMinus} tone="rose" />
          <StatCard label="Projected headcount" value={d.months.at(-1).projected_headcount} hint={`with ${d.monthly_hires_assumed} hires/month`} icon={TrendingUp} tone="emerald" /><StatCard label="12-month retention" value={`${d.yearly[0].retention_rate}%`} icon={ShieldCheck} tone="sky" /></div>
        <div className="grid gap-5 lg:grid-cols-2">
          <Card title="Workforce growth projection"><div className="h-72"><ResponsiveContainer><AreaChart data={d.months}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="month" fontSize={11} tickFormatter={(v) => v.slice(2)} /><YAxis fontSize={11} domain={['auto', 'auto']} /><Tooltip /><Legend />
            <Area type="monotone" dataKey="projected_headcount" stroke="#10b981" fill="#10b98122" name="With hiring" /><Area type="monotone" dataKey="headcount_no_hiring" stroke="#ef4444" fill="#ef444422" name="No hiring" /></AreaChart></ResponsiveContainer></div></Card>
          <Card title="Expected attrition per month"><div className="h-72"><ResponsiveContainer><ComposedChart data={d.months}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="month" fontSize={11} tickFormatter={(v) => v.slice(2)} /><YAxis yAxisId="l" fontSize={11} /><YAxis yAxisId="r" orientation="right" fontSize={11} /><Tooltip /><Legend />
            <Bar yAxisId="l" dataKey="expected_leavers" fill="#f59e0b" name="Leavers in month" radius={[3, 3, 0, 0]} /><Line yAxisId="r" dataKey="cumulative_leavers" stroke="#ef4444" strokeWidth={2} dot={false} name="Cumulative" /></ComposedChart></ResponsiveContainer></div></Card></div>
        <Card title="Yearly forecast" className="mt-5" pad={false}><DataTable rowKey="year" rows={d.yearly} columns={[{ key: 'year', label: 'Horizon', render: (r) => `Year ${r.year}` }, { key: 'expected_leavers', label: 'Expected leavers' }, { key: 'retained', label: 'Retained of current staff' }, { key: 'retention_rate', label: 'Retention', render: (r) => `${r.retention_rate}%` }, { key: 'projected_headcount', label: 'Projected headcount', render: (r) => <b>{r.projected_headcount}</b> }]} /></Card></>}
      <Card title="Department stability" subtitle="Score = 100 − 160% × (0.55·avg risk + 0.25·high-risk share + 0.20·low-satisfaction share)" className="mt-5" pad={false}>
        {st.loading && !st.data ? <Loading /> : <DataTable rowKey="department_id" rows={st.data?.departments} columns={[
          { key: 'department', label: 'Department', render: (r) => <b>{r.department}</b> }, { key: 'headcount', label: 'Headcount' },
          { key: 'stability_score', label: 'Stability score', render: (r) => <div className="flex w-44 items-center gap-2"><Progress value={r.stability_score} tone={r.stability_score >= 75 ? 'emerald' : r.stability_score >= 55 ? 'amber' : 'rose'} /><b className="w-10 text-right tabular-nums">{r.stability_score}</b></div> },
          { key: 'grade', label: 'Grade', render: (r) => <Badge>{r.grade}</Badge> }, { key: 'avg_risk', label: 'Avg risk', render: (r) => fmt.pct(r.avg_risk, 1) }, { key: 'high_risk_count', label: 'High risk' }, { key: 'forecast_retention_12m', label: 'Forecast retention 12m', render: (r) => `${r.forecast_retention_12m}%` }]} />}</Card>
    </div>
  )
}
