import React, { useEffect, useMemo, useState } from 'react'
import { sectorColor } from './api.js'
import { useCountUp } from './hooks.js'

/* ----------------------------------------------------------------- icons */

const P = (d) => (props) =>
  (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...props}>
      {d}
    </svg>
  )

export const Icon = {
  overview: P(<><rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" /></>),
  materials: P(<><path d="M12 3 3 7.5 12 12l9-4.5L12 3Z" /><path d="M3 12l9 4.5L21 12" /><path d="M3 16.5 12 21l9-4.5" /></>),
  review: P(<><path d="M4 5h16v11H8l-4 4V5Z" /><path d="m9 10 2 2 4-4" /></>),
  registry: P(<><path d="M4 7h16M4 12h16M4 17h16" /><circle cx="8" cy="7" r="0" /></>),
  audit: P(<><path d="M6 3h9l5 5v13H6V3Z" /><path d="M15 3v5h5" /><path d="M9 13h6M9 17h4" /></>),
  run: P(<><path d="m7 4 12 8-12 8V4Z" /></>),
  add: P(<><path d="M12 5v14M5 12h14" /></>),
  search: P(<><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>),
  spark: P(<><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18" /></>),
  link: P(<><path d="M9 15 15 9" /><path d="M11 6.5 13 4.5a4 4 0 0 1 6 6l-2 2" /><path d="M13 17.5 11 19.5a4 4 0 0 1-6-6l2-2" /></>),
  check: P(<><path d="m5 12 4 4 10-10" /></>),
  x: P(<><path d="M6 6l12 12M18 6 6 18" /></>),
  chevron: P(<><path d="m9 6 6 6-6 6" /></>),
  team: P(<><circle cx="9" cy="8" r="3.2" /><path d="M3.5 20a5.5 5.5 0 0 1 11 0" /><path d="M16 5.2a3.2 3.2 0 0 1 0 5.6" /><path d="M17.5 20a5.5 5.5 0 0 0-3-4.9" /></>),
  rupee: P(<><path d="M7 5h10M7 9h10" /><path d="M7 13h4c3.3 0 5-1.8 5-4s-1.7-4-5-4H8" /><path d="M8 13l7 6" /></>),
  attach: P(<><path d="M21 12.5 12.5 21a4.5 4.5 0 0 1-6.4-6.4L15 5.7a3 3 0 0 1 4.3 4.3L10.4 19a1.5 1.5 0 0 1-2.1-2.1l8-8" /></>),
  download: P(<><path d="M12 4v12M7 12l5 5 5-5" /><path d="M5 20h14" /></>),
  image: P(<><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="8.5" cy="9.5" r="1.6" /><path d="m21 16-5.2-5.2a2 2 0 0 0-2.8 0L4 20" /></>),
  file: P(<><path d="M6 3h9l5 5v13H6V3Z" /><path d="M15 3v5h5" /></>),
  trash: P(<><path d="M4 7h16" /><path d="M9 7V4h6v3" /><path d="M6 7l1 13h10l1-13" /></>),
}

/* ----------------------------------------------------------------- logo */

export function Logo({ size = 34 }) {
  return (
    <svg className="logo" width={size} height={size} viewBox="0 0 40 40" aria-label="Material Setu">
      <rect x="1" y="1" width="38" height="38" rx="11" fill="url(#lg)" />
      <defs>
        <linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ff8a2a" />
          <stop offset="1" stopColor="#ff6a00" />
        </linearGradient>
      </defs>
      <path className="logo__span" d="M9 25 Q20 9 31 25" fill="none" stroke="#10243e"
        strokeWidth="2.6" strokeLinecap="round" />
      <circle className="logo__node logo__node--l" cx="9" cy="25" r="3.4" fill="#10243e" />
      <circle className="logo__node logo__node--r" cx="31" cy="25" r="3.4" fill="#10243e" />
      <line x1="9" y1="30" x2="31" y2="30" stroke="#10243e" strokeWidth="2.2" strokeLinecap="round" opacity="0.55" />
    </svg>
  )
}

/* ----------------------------------------------------------------- data states */

export const Spinner = () => <span className="spinner" aria-label="loading" />

export function DataState({ loading, error, empty, emptyText, children }) {
  if (loading) return <div className="statebox"><Spinner /> Loading…</div>
  if (error) return <div className="statebox statebox--err">{String(error)}</div>
  if (empty) return <div className="statebox">{emptyText || 'Nothing here yet.'}</div>
  return children
}

/* ----------------------------------------------------------------- stat tile */

export function StatTile({ value, label, sub, tone, icon: I }) {
  const n = useCountUp(typeof value === 'number' ? value : 0)
  return (
    <div className={`stat ${tone ? `stat--${tone}` : ''}`}>
      {I && <span className="stat__icon"><I /></span>}
      <div className="stat__value">{typeof value === 'number' ? n.toLocaleString('en-IN') : value}</div>
      <div className="stat__label">{label}</div>
      {sub && <div className="stat__sub">{sub}</div>}
    </div>
  )
}

/* ----------------------------------------------------------------- bar row */

// Renders at 0 and grows to `pct` a tick after mount — a bare inline width
// never animates, since the CSS transition needs a prior value to move
// from. Shared by the overview bars and the opportunity price bars.
export function AnimatedBar({ pct, color }) {
  const [w, setW] = useState(0)
  useEffect(() => {
    const id = requestAnimationFrame(() => setW(pct))
    return () => cancelAnimationFrame(id)
  }, [pct])
  return (
    <span className="bar-track">
      <span className="bar-fill" style={{ width: `${w}%`, background: color }} />
    </span>
  )
}

export function BarRow({ name, n, max, color, onClick }) {
  const pct = Math.max(4, Math.round((n / max) * 100))
  return (
    <button type="button" className="bar-row" onClick={onClick} disabled={!onClick}>
      <span className="bar-row__name" title={name}>{name}</span>
      <AnimatedBar pct={pct} color={color} />
      <span className="bar-row__n">{n}</span>
    </button>
  )
}

/* ----------------------------------------------------------------- score ring */

const RING_R = 22
const RING_C = 2 * Math.PI * RING_R

export function Ring({ score, size = 54 }) {
  const pct = Math.round(score * 100)
  const tone = score >= 0.8 ? 'var(--green)' : score >= 0.68 ? 'var(--accent)' : 'var(--amber)'
  return (
    <svg className="ring" width={size} height={size} viewBox="0 0 54 54" aria-label={`${pct}% confidence`}>
      <circle className="ring__track" cx="27" cy="27" r={RING_R} fill="none" strokeWidth="5" />
      <circle
        cx="27" cy="27" r={RING_R} fill="none" strokeWidth="5" stroke={tone}
        strokeLinecap="round" strokeDasharray={RING_C} strokeDashoffset={RING_C * (1 - score)}
        style={{ transform: 'rotate(-90deg)', transformOrigin: '50% 50%', transition: 'stroke-dashoffset 1s cubic-bezier(.2,.7,.3,1)' }}
      />
      <text className="ring__num" x="27" y="27" textAnchor="middle" dominantBaseline="central">{pct}</text>
    </svg>
  )
}

/* ----------------------------------------------------------------- material side */

export function MaterialSide({ m }) {
  if (!m) return <div className="side"><p className="side__desc">material not loaded</p></div>
  return (
    <div className="side">
      <div className="side__cpse">
        <span className="dot" style={{ background: sectorColor(m.sector) }} />
        {m.cpse}
        <span className="side__sector">· {m.sector || 'Unclassified'}</span>
      </div>
      <div className="side__code">{m.local_code}</div>
      <p className="side__desc">{m.description}</p>
      <div className="side__foot">
        {m.material_family && <span>{m.material_family}</span>}
        {m.uom && <span>UOM {m.uom}</span>}
        {m.manufacturer && <span>{m.manufacturer}</span>}
      </div>
    </div>
  )
}

/* ----------------------------------------------------------------- attr chips */

export function attrDiff(a = {}, b = {}) {
  const keys = [...new Set([...Object.keys(a), ...Object.keys(b)])].sort()
  return keys.map((k) => {
    const inA = k in a
    const inB = k in b
    const same = inA && inB && JSON.stringify(a[k]) === JSON.stringify(b[k])
    const conflict = inA && inB && !same
    const val = inA ? a[k] : b[k]
    const show = Array.isArray(val) ? val.join('×') : val
    return { k, same, conflict, both: inA && inB, text: `${k}: ${show}` }
  })
}

export function AttrChips({ left, right }) {
  const diffs = useMemo(() => attrDiff(left, right), [left, right])
  if (!diffs.length) return null
  return (
    <div className="attrs">
      {diffs.map((d) => (
        <span key={d.k} className={`attr ${d.same ? 'attr--match' : d.conflict ? 'attr--conflict' : ''}`}>
          {d.both ? d.text : d.k}
        </span>
      ))}
    </div>
  )
}

export function AttrList({ attrs }) {
  const entries = Object.entries(attrs || {})
  if (!entries.length) return <span className="muted">no attributes extracted</span>
  return (
    <div className="attrs">
      {entries.map(([k, v]) => (
        <span key={k} className="attr">{k}: {Array.isArray(v) ? v.join('×') : String(v)}</span>
      ))}
    </div>
  )
}

/* ----------------------------------------------------------------- why list */

export function WhyList({ lines }) {
  return (
    <ul className="why">
      {lines.map((line, i) => (
        <li key={i} className={/conflict|reduced|differs/.test(line) ? 'is-warn' : ''}>{line}</li>
      ))}
    </ul>
  )
}

export const StatusPill = ({ status }) => (
  <span className={`status status--${status}`}>{status}</span>
)

/* ----------------------------------------------------------------- toasts */

export function Toasts({ items }) {
  return (
    <div className="toast-wrap">
      {items.map((t) => (
        <div key={t.id} className={`toast ${t.err ? 'is-err' : ''}`}>{t.msg}</div>
      ))}
    </div>
  )
}
