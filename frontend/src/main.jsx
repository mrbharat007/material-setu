import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { API } from './api.js'
import { go, useRoute } from './hooks.js'
import { AuthProvider, ROLE_LABEL, canReview, useAuth } from './auth.jsx'
import { DataProvider, useData } from './store.jsx'
import { Icon, Logo, Spinner, Toasts } from './components.jsx'
import { Audit, Materials, Opportunities, Overview, Registry, Review, Team } from './pages.jsx'
import { Landing } from './landing.jsx'
import { Login, Register } from './authpages.jsx'
import './styles.css'

const NAV = [
  { path: '/', label: 'Overview', icon: Icon.overview },
  { path: '/materials', label: 'Materials', icon: Icon.materials },
  { path: '/review', label: 'Review queue', icon: Icon.review, badge: 'pending' },
  { path: '/registry', label: 'Registry', icon: Icon.registry, badge: 'nmc' },
  { path: '/opportunities', label: 'Procurement', icon: Icon.rupee },
  { path: '/audit', label: 'Audit trail', icon: Icon.audit },
  { path: '/team', label: 'Team & access', icon: Icon.team, admin: true },
]

const PAGES = {
  '/': Overview,
  '/materials': Materials,
  '/review': Review,
  '/registry': Registry,
  '/opportunities': Opportunities,
  '/audit': Audit,
  '/team': Team,
}

const PUBLIC = new Set(['/login', '/register'])

function Sidebar({ route, open, onClose }) {
  const d = useData()
  const { user } = useAuth()
  const items = NAV.filter((item) => !item.admin || user?.role === 'admin')
  const badge = {
    pending: d.matches.filter((m) => m.status === 'pending').length,
    nmc: d.nmc.length,
  }
  return (
    <>
      <div className={`scrim ${open ? 'is-on' : ''}`} onClick={onClose} />
      <aside className={`sidebar ${open ? 'is-open' : ''}`}>
        <a className="sidebar__brand" href="#/" onClick={onClose}>
          <Logo />
          <div>
            <strong>Material Setu</strong>
            <span>Unified Material Master</span>
          </div>
        </a>
        <nav className="sidebar__nav">
          {items.map((item) => {
            const active = route === item.path
            const count = item.badge ? badge[item.badge] : 0
            return (
              <a key={item.path} href={`#${item.path}`} onClick={onClose}
                className={`navitem ${active ? 'is-active' : ''}`}>
                <span className="navitem__icon"><item.icon /></span>
                {item.label}
                {count > 0 && <span className="navitem__badge">{count}</span>}
                {active && <span className="navitem__bar" />}
              </a>
            )
          })}
        </nav>
        <div className="sidebar__foot">
          <a href={`${API}/docs`} target="_blank" rel="noreferrer">API docs ↗</a>
          <span>SIH 2026</span>
        </div>
      </aside>
    </>
  )
}

function UserMenu() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  if (!user) return null
  const initials = user.name.split(/\s+/).slice(0, 2).map((s) => s[0]).join('').toUpperCase()
  return (
    <div className="usermenu">
      <button className="usermenu__btn" onClick={() => setOpen((v) => !v)}>
        <span className="usermenu__av">{initials}</span>
        <span className="usermenu__name">{user.name}</span>
        <span className={`role-pill role-pill--${user.role}`}>{ROLE_LABEL[user.role]}</span>
      </button>
      {open && (
        <>
          <div className="usermenu__scrim" onClick={() => setOpen(false)} />
          <div className="usermenu__pop">
            <div className="usermenu__id">
              <strong>{user.name}</strong>
              <span>{user.email}</span>
              {user.cpse && <span>{user.cpse}</span>}
            </div>
            <button className="usermenu__item" onClick={() => { setOpen(false); logout() }}>
              Sign out
            </button>
          </div>
        </>
      )}
    </div>
  )
}

function Topbar({ route, onMenu }) {
  const d = useData()
  const { user } = useAuth()
  const title = (NAV.find((n) => n.path === route) || { label: 'Material Setu' }).label
  const running = d.runStep >= 0
  return (
    <header className="topbar">
      <button className="iconbtn only-mobile" onClick={onMenu} aria-label="Menu">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 6h16M4 12h16M4 18h16" /></svg>
      </button>
      <div className="topbar__title">{title}</div>
      <div className="topbar__spacer" />
      <span className={`conn ${d.error ? 'is-bad' : 'is-ok'}`} title={d.error || 'API connected'}>
        <span className="conn__dot" /> {d.error ? 'API offline' : 'connected'}
      </span>
      <button className="btn btn--primary btn--sm topbar__run"
        disabled={d.busy || !canReview(user)}
        title={canReview(user) ? 'Run harmonization' : 'Requires steward or admin role'}
        onClick={() => { d.runMatching(); go('/review') }}>
        <Icon.run /> <span>{running ? 'Running…' : 'Run harmonization'}</span>
      </button>
      <UserMenu />
    </header>
  )
}

function Shell({ route }) {
  const [menu, setMenu] = useState(false)
  const d = useData()
  const Page = PAGES[route] || Overview

  return (
    <div className="layout">
      <Sidebar route={route} open={menu} onClose={() => setMenu(false)} />
      <div className="main">
        <Topbar route={route} onMenu={() => setMenu(true)} />
        <main className="content" key={route}>
          <Page />
        </main>
      </div>
      <Toasts items={d.toasts} />
    </div>
  )
}

function FullLoader() {
  return (
    <div className="fullload">
      <Logo size={40} />
      <Spinner />
    </div>
  )
}

function Root() {
  const route = useRoute()
  const { user, ready } = useAuth()

  // Keep the URL honest as auth state settles.
  useEffect(() => {
    if (!ready) return
    if (user && (route === '/welcome' || route === '/login' || route === '/register')) {
      go('/')
    } else if (!user && route !== '/register') {
      go('/login')
    } else if (user && route === '/team' && user.role !== 'admin') {
      go('/')
    } else if (user && route !== '/' && !PAGES[route] && !PUBLIC.has(route)) {
      go('/')  // unknown hash → dashboard home
    }
  }, [user, ready, route])

  if (!ready) return <FullLoader />

  if (!user) {
    if (route === '/register') return <Register />
    return <Login />
  }

  const allowed = PAGES[route] && (route !== '/team' || user.role === 'admin')

  return (
    <DataProvider>
      <Shell route={allowed ? route : '/'} />
    </DataProvider>
  )
}

createRoot(document.getElementById('root')).render(
  <AuthProvider>
    <Root />
  </AuthProvider>,
)
