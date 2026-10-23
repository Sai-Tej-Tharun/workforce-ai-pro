import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend, LineChart, Line, ComposedChart, PieChart, Pie, Cell } from 'recharts'
import { useLive } from '../context/AppContext'
import { useFetch } from '../hooks/useFetch'
import { Card, PageHeader, StatCard, Loading, ErrorBox, DataTable, RiskBar } from '../components/ui'
import { fmt } from '../api'
import { UserMinus, Percent, Brain, Users } from 'lucide-react'

const RC = { low: '#10b981', medium: '#f59e0b', high: '#ef4444' }
export default function Attrition() {
  const { data: d, loading, error, reload } = useFetch('/analytics/attrition')
  useLive(['risk_update'], reload)
  if (loading && !d) return <Loading />
  if (error) return <ErrorBox error={error} onRetry={reload} />
  const s = d.stats
  const dist = Object.entries(s.risk_distribution).map(([name, value]) => ({ name, value }))
  return (
    <div>
      <PageHeader title="Attrition Analytics" subtitle="Actual turnover, predicted attrition, department analysis and risk trends" />
      <div className="mb-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Leavers (12 months)" value={s.leavers_12m} icon={UserMinus} tone="rose" /><StatCard label="Turnover rate (12m)" value={`${s.turnover_rate_12m}%`} icon={Percent} tone="amber" />
        <StatCard label="Predicted attrition" value={s.predicted_attrition_rate == null ? '–' : `${s.predicted_attrition_rate}%`} hint={`≈ ${s.predicted_leavers_12m ?? '–'} leavers next 12m`} icon={Brain} />
        <StatCard label="Active headcount" value={s.active_headcount} icon={Users} tone="emerald" /></div>
      <div className="grid gap-5 lg:grid-cols-3">
        <Card title="Monthly turnover trend" subtitle="Leavers and hires vs turnover rate" className="lg:col-span-2"><div className="h-72"><ResponsiveContainer>
          <ComposedChart data={d.monthly_turnover}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="month" fontSize={11} tickFormatter={(v) => v.slice(2)} /><YAxis yAxisId="l" fontSize={11} /><YAxis yAxisId="r" orientation="right" fontSize={11} unit="%" /><Tooltip /><Legend />
            <Bar yAxisId="l" dataKey="hires" fill="#a5b4fc" name="Hires" /><Bar yAxisId="l" dataKey="leavers" fill="#ef4444" name="Leavers" /><Line yAxisId="r" type="monotone" dataKey="turnover_rate" stroke="#f59e0b" strokeWidth={2} name="Turnover %" /></ComposedChart></ResponsiveContainer></div></Card>
        <Card title="Current risk distribution"><div className="h-72"><ResponsiveContainer><PieChart><Pie data={dist} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={3} label={({ name, value }) => `${name} ${value}`}>{dist.map((x) => <Cell key={x.name} fill={RC[x.name]} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer></div></Card>
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card title="Average predicted risk over time" subtitle="From stored prediction history">{d.risk_trend.length < 2 ? <div className="py-10 text-center text-sm text-slate-400">Not enough history yet</div> :
          <div className="h-64"><ResponsiveContainer><LineChart data={d.risk_trend}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="date" fontSize={11} tickFormatter={(v) => v.slice(5)} /><YAxis fontSize={11} unit="%" /><Tooltip formatter={(v) => `${v}%`} /><Line type="monotone" dataKey="avg_risk" stroke="#6366f1" strokeWidth={2} dot={{ r: 3 }} name="Avg risk" /></LineChart></ResponsiveContainer></div>}</Card>
        <Card title="Risk by tenure band"><div className="h-64"><ResponsiveContainer><BarChart data={d.tenure_analysis}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="band" fontSize={11} /><YAxis fontSize={11} unit="%" /><Tooltip /><Bar dataKey="avg_risk" fill="#6366f1" radius={[4, 4, 0, 0]} name="Avg risk %" /></BarChart></ResponsiveContainer></div></Card>
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Card title="Department-wise attrition" className="lg:col-span-2" pad={false}><DataTable rowKey="department" rows={d.departments} columns={[
          { key: 'department', label: 'Department', render: (r) => <b>{r.department}</b> }, { key: 'headcount', label: 'Headcount' }, { key: 'leavers_12m', label: 'Leavers 12m' },
          { key: 'turnover_rate_12m', label: 'Actual turnover', render: (r) => `${r.turnover_rate_12m}%` }, { key: 'predicted_avg_risk', label: 'Predicted risk', render: (r) => r.predicted_avg_risk == null ? '–' : <RiskBar score={r.predicted_avg_risk / 100} /> }, { key: 'high_risk', label: 'High risk' }]} /></Card>
        <Card title="Top attrition drivers" subtitle="Across medium/high-risk employees">{d.top_drivers.length === 0 ? <div className="text-sm text-slate-400">No data</div> :
          <div className="space-y-2.5">{d.top_drivers.map((x) => <div key={x.driver}><div className="flex justify-between text-sm"><span>{x.driver}</span><b>{x.employees}</b></div><div className="h-1.5 rounded-full bg-slate-100"><div className="h-full rounded-full bg-rose-400" style={{ width: `${(x.employees / d.top_drivers[0].employees) * 100}%` }} /></div></div>)}</div>}</Card>
      </div>
    </div>
  )
}
