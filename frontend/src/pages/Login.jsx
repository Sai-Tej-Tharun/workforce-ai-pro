import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Brain, ShieldCheck, Activity } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { errMsg } from '../api'
import { Field, Input, ErrorBox, Spinner } from '../components/ui'

export function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="hidden flex-col justify-between bg-gradient-to-br from-slate-900 via-indigo-950 to-brand-700 p-12 text-white lg:flex">
        <div className="flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/15 text-lg font-bold">W</div><span className="text-lg font-semibold">WorkForce AI Pro</span></div>
        <div>
          <h2 className="text-3xl font-semibold leading-tight">Predict attrition.<br />Act before it happens.</h2>
          <p className="mt-3 max-w-md text-indigo-100">HR attrition prediction and workforce intelligence — real-time risk scoring, automated alerts and guided retention workflows.</p>
          <ul className="mt-8 space-y-4 text-sm text-indigo-100">
            <li className="flex items-center gap-3"><Brain size={20} /> ML-powered risk with explainable drivers</li>
            <li className="flex items-center gap-3"><Activity size={20} /> Live monitoring and instant HR alerts</li>
            <li className="flex items-center gap-3"><ShieldCheck size={20} /> Role-based access, audit trail, JWT security</li>
          </ul>
        </div>
        <div className="text-xs text-indigo-200/70">© WorkForce AI Pro</div>
      </div>
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
          <p className="mb-6 mt-1 text-sm text-slate-500">{subtitle}</p>
          {children}
          <div className="mt-6 text-center text-sm text-slate-500">{footer}</div>
        </div>
      </div>
    </div>
  )
}

const DEMO = [['Admin', 'admin@workforce.ai', 'Admin@123'], ['HR', 'hr@workforce.ai', 'Hr@12345'], ['Manager', 'manager@workforce.ai', 'Manager@123'], ['Employee', 'employee@workforce.ai', 'Employee@123']]

export default function Login() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e) => {
    e.preventDefault(); setErr(''); setBusy(true)
    try { await login(email.trim(), password); nav('/') } catch (x) { setErr(errMsg(x)) } finally { setBusy(false) }
  }
  return (
    <AuthShell title="Welcome back" subtitle="Sign in to your workspace"
      footer={<><Link className="text-brand-600 hover:underline" to="/register">Create account</Link> · <Link className="text-brand-600 hover:underline" to="/forgot-password">Forgot password?</Link></>}>
      <form onSubmit={submit} className="space-y-4">
        <ErrorBox error={err} />
        <Field label="Email"><Input type="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" /></Field>
        <Field label="Password"><Input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" /></Field>
        <button className="btn-primary w-full" disabled={busy}>{busy ? <Spinner className="!text-white" /> : 'Sign in'}</button>
      </form>
      <div className="mt-6 rounded-lg border border-dashed border-slate-300 p-3">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Demo accounts (click to fill)</div>
        <div className="grid grid-cols-2 gap-2">
          {DEMO.map(([r, e, p]) => <button key={r} type="button" onClick={() => { setEmail(e); setPassword(p) }} className="btn-ghost !py-1.5 text-xs">{r}</button>)}
        </div>
      </div>
    </AuthShell>
  )
}
