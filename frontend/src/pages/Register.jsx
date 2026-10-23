import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, errMsg } from '../api'
import { Field, Input, ErrorBox, Spinner } from '../components/ui'
import { AuthShell } from './Login'

export default function Register() {
  const nav = useNavigate()
  const [f, setF] = useState({ full_name: '', email: '', password: '', confirm: '' })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const submit = async (e) => {
    e.preventDefault(); setErr('')
    if (f.password !== f.confirm) return setErr('Passwords do not match')
    setBusy(true)
    try { await api.post('/auth/register', { full_name: f.full_name, email: f.email, password: f.password }); nav('/login', { replace: true }) }
    catch (x) { setErr(errMsg(x)) } finally { setBusy(false) }
  }
  return (
    <AuthShell title="Create your account" subtitle="Self-registered accounts start with the Employee role" footer={<>Already registered? <Link className="text-brand-600 hover:underline" to="/login">Sign in</Link></>}>
      <form onSubmit={submit} className="space-y-4">
        <ErrorBox error={err} />
        <Field label="Full name"><Input required minLength={2} value={f.full_name} onChange={set('full_name')} /></Field>
        <Field label="Work email" hint="Use your company email to link your employee profile automatically"><Input type="email" required value={f.email} onChange={set('email')} /></Field>
        <Field label="Password" hint="Min 8 characters, with letters and digits"><Input type="password" required minLength={8} value={f.password} onChange={set('password')} /></Field>
        <Field label="Confirm password"><Input type="password" required value={f.confirm} onChange={set('confirm')} /></Field>
        <button className="btn-primary w-full" disabled={busy}>{busy ? <Spinner className="!text-white" /> : 'Create account'}</button>
      </form>
    </AuthShell>
  )
}
