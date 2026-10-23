import { lazy, Suspense, Component } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import { Loading, PageHeader } from './components/ui'

// Route-level code splitting (lazy loading)
const P = (f) => lazy(f)
const Login = P(() => import('./pages/Login'))
const Register = P(() => import('./pages/Register'))
const ForgotPassword = P(() => import('./pages/ForgotPassword'))
const ResetPassword = P(() => import('./pages/ResetPassword'))
const Dashboard = P(() => import('./pages/Dashboard'))
const Employees = P(() => import('./pages/Employees'))
const Departments = P(() => import('./pages/Departments'))
const Attendance = P(() => import('./pages/Attendance'))
const Leave = P(() => import('./pages/Leave'))
const Payroll = P(() => import('./pages/Payroll'))
const Performance = P(() => import('./pages/Performance'))
const Tasks = P(() => import('./pages/Tasks'))
const Documents = P(() => import('./pages/Documents'))
const Predictions = P(() => import('./pages/Predictions'))
const RiskMonitor = P(() => import('./pages/RiskMonitor'))
const Interventions = P(() => import('./pages/Interventions'))
const Attrition = P(() => import('./pages/Attrition'))
const Forecast = P(() => import('./pages/Forecast'))
const Recommendations = P(() => import('./pages/Recommendations'))
const LiveFeed = P(() => import('./pages/LiveFeed'))
const Datasets = P(() => import('./pages/Datasets'))
const Chat = P(() => import('./pages/Chat'))
const Notifications = P(() => import('./pages/Notifications'))
const Reports = P(() => import('./pages/Reports'))
const AuditLogs = P(() => import('./pages/AuditLogs'))
const Users = P(() => import('./pages/Users'))
const Account = P(() => import('./pages/Account'))

class Boundary extends Component {
  state = { err: null }
  static getDerivedStateFromError(err) { return { err } }
  render() {
    if (this.state.err) return (
      <div className="card p-8 text-center"><div className="font-semibold text-rose-700">Something went wrong rendering this page.</div>
        <div className="mt-1 text-sm text-slate-500">{String(this.state.err.message || this.state.err)}</div>
        <button className="btn-primary mt-4" onClick={() => this.setState({ err: null })}>Try again</button></div>)
    return this.props.children
  }
}

function Guard({ roles, children }) {
  const { user } = useAuth()
  if (roles && !roles.includes(user.role)) return (
    <div><PageHeader title="Access denied" subtitle={`Your role (${user.role}) cannot view this page.`} /></div>)
  return children
}

function Protected() {
  const { user, booting } = useAuth()
  if (booting) return <Loading label="Restoring session…" />
  if (!user) return <Navigate to="/login" replace />
  return <Layout />
}

const AHM = ['ADMIN', 'HR', 'MANAGER'], AH = ['ADMIN', 'HR']
export default function App() {
  const { user, booting } = useAuth()
  return (
    <Boundary>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/login" element={user && !booting ? <Navigate to="/" replace /> : <Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route element={<Protected />}>
            <Route index element={<Dashboard />} />
            <Route path="employees" element={<Employees />} />
            <Route path="departments" element={<Guard roles={AHM}><Departments /></Guard>} />
            <Route path="attendance" element={<Attendance />} />
            <Route path="leave" element={<Leave />} />
            <Route path="payroll" element={<Payroll />} />
            <Route path="performance" element={<Performance />} />
            <Route path="tasks" element={<Tasks />} />
            <Route path="documents" element={<Documents />} />
            <Route path="predictions" element={<Guard roles={AHM}><Predictions /></Guard>} />
            <Route path="risk-monitor" element={<Guard roles={AHM}><RiskMonitor /></Guard>} />
            <Route path="interventions" element={<Guard roles={AHM}><Interventions /></Guard>} />
            <Route path="attrition" element={<Guard roles={AHM}><Attrition /></Guard>} />
            <Route path="forecast" element={<Guard roles={AH}><Forecast /></Guard>} />
            <Route path="recommendations" element={<Recommendations />} />
            <Route path="live" element={<Guard roles={AHM}><LiveFeed /></Guard>} />
            <Route path="datasets" element={<Guard roles={AH}><Datasets /></Guard>} />
            <Route path="chat" element={<Chat />} />
            <Route path="notifications" element={<Notifications />} />
            <Route path="reports" element={<Guard roles={AHM}><Reports /></Guard>} />
            <Route path="audit" element={<Guard roles={AH}><AuditLogs /></Guard>} />
            <Route path="users" element={<Guard roles={AH}><Users /></Guard>} />
            <Route path="account" element={<Account />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </Boundary>
  )
}
