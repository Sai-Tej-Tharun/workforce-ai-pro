import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, errMsg } from '../api'
import { Field, Input, ErrorBox, Spinner } from '../components/ui'
import { AuthShell } from './Login'

export default function ResetPassword() {
  const [sp] = useSearchParams()
  const nav = useNavigate()
  const [token, setToken] = useState(sp.get('token') || '')
  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e) => {
    e.preventDefault(); setErr('')
    if (pw !== pw2) return setErr('Passwords do not match')
    setBusy(true)
    try { await api.post('/auth/reset-password', { token, new_password: pw }); nav('/login', { replace: true }) } catch (x) { setErr(errMsg(x)) } finally { setBusy(false) }
  }
  return (
    <AuthShell title="Reset password" subtitle="Choose a new password" footer={<Link className="text-brand-600 hover:underline" to="/login">Back to sign in</Link>}>
      <form onSubmit={submit} className="space-y-4">
        <ErrorBox error={err} />
        {!sp.get('token') && <Field label="Reset token"><Input required value={token} onChange={(e) => setToken(e.target.value)} /></Field>}
        <Field label="New password" hint="Min 8 characters, letters and digits"><Input type="password" required minLength={8} value={pw} onChange={(e) => setPw(e.target.value)} /></Field>
        <Field label="Confirm password"><Input type="password" required value={pw2} onChange={(e) => setPw2(e.target.value)} /></Field>
        <button className="btn-primary w-full" disabled={busy}>{busy ? <Spinner className="!text-white" /> : 'Update password'}</button>
      </form>
    </AuthShell>
  )
}
