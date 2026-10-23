import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, errMsg } from '../api'
import { Field, Input, ErrorBox, Spinner } from '../components/ui'
import { AuthShell } from './Login'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [res, setRes] = useState(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e) => {
    e.preventDefault(); setErr(''); setBusy(true)
    try { setRes((await api.post('/auth/forgot-password', { email })).data) } catch (x) { setErr(errMsg(x)) } finally { setBusy(false) }
  }
  return (
    <AuthShell title="Forgot password" subtitle="We'll send a reset link to your email" footer={<Link className="text-brand-600 hover:underline" to="/login">Back to sign in</Link>}>
      {res ? (
        <div className="space-y-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
          <p>{res.message}</p>
          {res.dev_reset_token && (
            <div className="rounded-md bg-white p-3 text-slate-700">
              <div className="mb-1 text-xs font-semibold uppercase text-slate-400">Dev mode – no email server configured</div>
              <Link className="break-all text-brand-600 underline" to={`/reset-password?token=${res.dev_reset_token}`}>Open reset page</Link>
            </div>
          )}
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <ErrorBox error={err} />
          <Field label="Email"><Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
          <button className="btn-primary w-full" disabled={busy}>{busy ? <Spinner className="!text-white" /> : 'Send reset link'}</button>
        </form>
      )}
    </AuthShell>
  )
}
