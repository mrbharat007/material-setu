import React, { useState } from 'react'
import { Logo } from './components.jsx'
import { useAuth } from './auth.jsx'
import { go } from './hooks.js'

function AuthShell({ title, sub, children, foot }) {
  return (
    <div className="auth">
      <div className="auth__panel">
        <a className="auth__brand" href="#/">
          <Logo size={32} />
          <div>
            <strong>Material Setu</strong>
            <span>Unified Material Master</span>
          </div>
        </a>
        <h1>{title}</h1>
        {sub && <p className="auth__sub">{sub}</p>}
        {children}
        {foot && <div className="auth__foot">{foot}</div>}
      </div>
      <div className="auth__aside">
        <blockquote>
          “One material, one trusted national identity — while every CPSE keeps its
          existing local code.”
        </blockquote>
      </div>
    </div>
  )
}

export function Login() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setErr(''); setBusy(true)
    try {
      await login(email.trim(), password)
      go('/app')
    } catch (e2) {
      setErr(e2.message || 'Could not sign in')
    } finally {
      setBusy(false)
    }
  }

  const quickLogin = async (quickEmail, quickPassword) => {
    setEmail(quickEmail)
    setPassword(quickPassword)
    setErr(''); setBusy(true)
    try {
      await login(quickEmail, quickPassword)
      go('/app')
    } catch (e2) {
      setErr(e2.message || 'Could not sign in')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell
      title="Sign in"
      sub="Access the harmonization dashboard."
      foot={<>New here? <a href="#/register">Create an account</a></>}
    >
      <form className="auth__form" onSubmit={submit}>
        <label>Email or Username
          <input type="text" autoComplete="username" value={email}
            placeholder="admin or steward@material-setu.gov.in"
            onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>Password
          <input type="password" autoComplete="current-password" value={password}
            onChange={(e) => setPassword(e.target.value)} required />
        </label>
        {err && <div className="formerr">{err}</div>}
        <button className="btn btn--primary" type="submit" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      
      <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid var(--border, rgba(255,255,255,0.1))' }}>
        <p style={{ margin: '0 0 10px', fontSize: '12px', fontWeight: 600, color: 'var(--ink-muted, #888)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          One-Click Demo Login:
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            disabled={busy}
            onClick={() => quickLogin('admin@material-setu.gov.in', 'materialsetu')}
            title="Administrator access"
          >
            🛡️ Admin
          </button>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            disabled={busy}
            onClick={() => quickLogin('steward@material-setu.gov.in', 'materialsetu')}
            title="Steward review access"
          >
            📋 Steward
          </button>
        </div>
      </div>
    </AuthShell>
  )
}

export function Register() {
  const { register } = useAuth()
  const [form, setForm] = useState({ name: '', email: '', password: '', cpse: '' })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setErr(''); setBusy(true)
    try {
      await register({
        name: form.name.trim(),
        email: form.email.trim(),
        password: form.password,
        cpse: form.cpse.trim() || null,
      })
      go('/app')
    } catch (e2) {
      setErr(e2.message || 'Could not create the account')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell
      title="Create an account"
      sub="New accounts start as a steward — an administrator can promote you further."
      foot={<>Already registered? <a href="#/login">Sign in</a></>}
    >
      <form className="auth__form" onSubmit={submit}>
        <label>Full name
          <input value={form.name} onChange={set('name')} required />
        </label>
        <label>Email
          <input type="email" autoComplete="username" value={form.email}
            onChange={set('email')} required />
        </label>
        <label>Password
          <input type="password" autoComplete="new-password" minLength={8}
            value={form.password} onChange={set('password')} required />
          <small className="auth__hint">At least 8 characters.</small>
        </label>
        <label>CPSE <span className="auth__opt">(optional)</span>
          <input value={form.cpse} onChange={set('cpse')} placeholder="e.g. NTPC" />
        </label>
        {err && <div className="formerr">{err}</div>}
        <button className="btn btn--primary" type="submit" disabled={busy}>
          {busy ? 'Creating…' : 'Create account'}
        </button>
      </form>
    </AuthShell>
  )
}
