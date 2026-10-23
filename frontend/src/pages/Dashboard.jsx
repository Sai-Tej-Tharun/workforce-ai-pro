import { Link } from 'react-router-dom'
import { Users, UserCheck, CalendarClock, Wallet, ShieldAlert, Brain, HandHelping, Clock, Target } from 'lucide-react'
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend, PieChart, Pie, Cell, AreaChart, Area } from 'recharts'
import { useAuth } from '../context/AuthContext'
import { useLive } from '../context/AppContext'
import { useFetch } from '../hooks/useFetch'
import { Card, StatCard, PageHeader, Loading, ErrorBox, Badge, Progress, CHART_COLORS } from '../components/ui'
import { fmt } from '../api'

const RISK_COLORS = { low: '#10b981', medium: '#f59e0b', high: '#ef4444' }
const shortDate = (d) => d?.slice(5)

function StaffDashboard({ d, user }) {
  const dist = Object.entries(d.risk.distribution).map(([k, v]) => ({ name: k, value: v }))
  const att = d.attendance_today
  const isHR = user.role !== 'MANAGER'
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Active employees" value={d.employees.total} hint={`${d.employees.new_hires_30d} hired in last 30 days`} icon={Users} />
        <StatCard label="Present today" value={att.present + att.late} hint={`${att.late} late · ${att.absent} absent · ${att.on_leave} on leave`} icon={UserCheck} tone="emerald" />
        <StatCard label="High-risk employees" value={d.risk.distribution.high} hint={`Predicted leavers (12m): ${d.risk.predicted_leavers_12m}`} icon={ShieldAlert} tone="rose" />
        <StatCard label="Open interventions" value={d.open_interventions} hint={`${d.open_alerts} open alerts · ${d.pending_leave} pending leave`} icon={HandHelping} tone="amber" />
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Card title="Attendance – last 14 days" className="lg:col-span-2">
          <div className="h-64"><ResponsiveContainer>
            <BarChart data={d.attendance_trend.map((x) => ({ ...x, date: shortDate(x.date) }))}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="date" fontSize={11} /><YAxis fontSize={11} /><Tooltip /><Legend />
              <Bar dataKey="present" stackId="a" fill="#10b981" /><Bar dataKey="late" stackId="a" fill="#f59e0b" /><Bar dataKey="absent" stackId="a" fill="#ef4444" radius={[3, 3, 0, 0]} /></BarChart>
          </ResponsiveContainer></div>
        </Card>
        <Card title="Attrition risk distribution" subtitle={d.risk.avg != null ? `Average risk ${fmt.pct(d.risk.avg, 1)}` : 'No predictions yet'}>
          {d.risk.avg == null ? <div className="py-10 text-center text-sm text-slate-400">Train a model in Datasets &amp; Models</div> :
            <div className="h-64"><ResponsiveContainer><PieChart><Pie data={dist} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={3} label={({ name, value }) => `${name} ${value}`}>
              {dist.map((x) => <Cell key={x.name} fill={RISK_COLORS[x.name]} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer></div>}
        </Card>
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Card title="Department analytics" className="lg:col-span-2" pad={false}>
          <table className="w-full"><thead className="bg-slate-50"><tr><th className="th">Department</th><th className="th">Headcount</th>{isHR && <th className="th">Avg salary</th>}<th className="th">Avg risk</th></tr></thead>
            <tbody className="divide-y divide-slate-100">{d.departments.map((x) => (
              <tr key={x.name}><td className="td font-medium">{x.name}</td><td className="td">{x.headcount}</td>{isHR && <td className="td">{fmt.money(x.avg_salary)}</td>}
                <td className="td w-48">{x.avg_risk == null ? '–' : <div className="flex items-center gap-2"><Progress value={x.avg_risk * 100} tone={x.avg_risk >= .35 ? 'rose' : x.avg_risk >= .2 ? 'amber' : 'emerald'} /><span className="w-10 text-xs tabular-nums">{fmt.pct(x.avg_risk)}</span></div>}</td></tr>))}</tbody></table>
        </Card>
        {d.payroll.trend.length > 0 ? (
          <Card title="Payroll overview" subtitle={`Monthly cost ${fmt.money(d.payroll.monthly_cost)}`}>
            <div className="h-56"><ResponsiveContainer><AreaChart data={d.payroll.trend}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="label" fontSize={11} /><YAxis fontSize={11} tickFormatter={(v) => `${Math.round(v / 1000)}k`} /><Tooltip formatter={(v) => fmt.money(v)} />
              <Area type="monotone" dataKey="gross" stroke="#6366f1" fill="#6366f133" /><Area type="monotone" dataKey="net" stroke="#10b981" fill="#10b98133" /></AreaChart></ResponsiveContainer></div>
          </Card>
        ) : (
          <Card title="Workforce"><div className="space-y-3 text-sm"><div className="flex justify-between"><span className="text-slate-500">Avg tenure</span><b>{d.employees.avg_tenure} yrs</b></div>
            <div className="flex justify-between"><span className="text-slate-500">Avg job satisfaction</span><b>{d.employees.avg_satisfaction}/4</b></div></div></Card>
        )}
      </div>
    </>
  )
}

function EmployeeDashboard({ d }) {
  if (!d.linked) return <Card><div className="py-8 text-center text-sm text-slate-500">Your account is not linked to an employee profile yet. Ask HR to link it.</div></Card>
  const days = d.attendance_month.days
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Days present (month)" value={(days.present || 0) + (days.late || 0) + (days.half_day || 0)} hint={`${days.late || 0} late · ${days.absent || 0} absent`} icon={Clock} tone="emerald" />
        <StatCard label="Overtime (month)" value={`${d.attendance_month.overtime}h`} icon={CalendarClock} tone="amber" />
        <StatCard label="Open tasks" value={d.open_tasks} icon={Target} />
        <StatCard label="Latest net pay" value={d.latest_payslip ? fmt.money(d.latest_payslip.net_pay) : '–'} hint={d.latest_payslip ? `${d.latest_payslip.month}/${d.latest_payslip.year}` : ''} icon={Wallet} tone="sky" />
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card title="Leave balance" actions={<Link to="/leave" className="text-xs text-brand-600 hover:underline">Apply leave</Link>}>
          <div className="space-y-3">{d.leave_balance.map((b) => (
            <div key={b.leave_type}><div className="mb-1 flex justify-between text-sm"><span>{b.leave_type}</span><span className="text-slate-500">{b.remaining} of {b.quota} left</span></div><Progress value={(b.used + b.pending) / (b.quota || 1) * 100} /></div>))}</div>
        </Card>
        <Card title="My goals" actions={<Link to="/performance" className="text-xs text-brand-600 hover:underline">All goals</Link>}>
          <div className="space-y-3">{d.goals.length === 0 && <div className="text-sm text-slate-400">No goals yet</div>}{d.goals.map((g) => (
            <div key={g.id}><div className="mb-1 flex justify-between text-sm"><span>{g.title}</span><Badge>{g.status}</Badge></div><Progress value={g.progress} tone={g.status === 'at_risk' ? 'rose' : 'brand'} /></div>))}</div>
        </Card>
      </div>
    </>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const { data, loading, error, reload } = useFetch('/analytics/dashboard')
  useLive(['risk_update'], () => reload())  // dashboard refreshes when the AI engine recalculates
  return (
    <div>
      <PageHeader title={`Welcome, ${user.full_name.split(' ')[0]}`} subtitle={user.role === 'EMPLOYEE' ? 'Your personal workspace' : 'Workforce overview — updates live as risk is recalculated'}
        actions={user.role !== 'EMPLOYEE' && <Link to="/predictions" className="btn-primary"><Brain size={16} />AI Predictions</Link>} />
      <ErrorBox error={error} onRetry={reload} />
      {loading && !data ? <Loading /> : data && (data.scope === 'EMPLOYEE' ? <EmployeeDashboard d={data} /> : <StaffDashboard d={data} user={user} />)}
    </div>
  )
}
