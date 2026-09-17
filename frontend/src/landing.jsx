import React from 'react'
import { Logo } from './components.jsx'
import { useAuth } from './auth.jsx'
import { useInView, useScrolled } from './hooks.js'

const PROBLEM_COSTS = [
  'Duplicate purchase orders for items already sitting in another CPSE’s warehouse',
  'Missed joint and bulk-procurement opportunities across the group',
  'Slower audits — no single source of truth for what a material even is',
  'Obsolete stock piling up because no one can see it group-wide',
]

const FEATURES = [
  {
    title: 'Standardize',
    body: 'Descriptions and units are normalized on ingest — NOS, No. and PC all become “each”, sqmm becomes sq mm.',
  },
  {
    title: 'Extract attributes',
    body: 'Family-aware templates pull the attributes that actually matter — bore, voltage, grade, rating — out of messy free-text descriptions.',
  },
  {
    title: 'Match, explained',
    body: 'Every proposed duplicate comes with a plain-language reason — never just a score you have to trust blindly.',
  },
  {
    title: 'Human-in-the-loop',
    body: 'A steward approves or rejects each candidate. A match is never treated as approval to substitute one part for another.',
  },
  {
    title: 'National Material Code',
    body: 'An approved identity gets one code and a full crosswalk back to every CPSE’s original local code.',
  },
  {
    title: 'Audited end to end',
    body: 'Every ingestion, harmonization run and steward decision is recorded against the person who made it.',
  },
  {
    title: 'Attach evidence',
    body: 'Drop a photo, drawing, datasheet PDF or vendor PPTX onto any record — stewards see it right in the review queue.',
  },
]

const STEPS = [
  ['Ingest', 'Bring in records from each CPSE’s SAP or ERP system, or a CSV export.'],
  ['Standardize', 'Units, dimensions and material class get pulled out of the raw description.'],
  ['Match', 'Likely duplicates get ranked by how closely their attributes actually line up.'],
  ['Approve', 'A steward reviews every proposed match before anything becomes official.'],
  ['Publish', 'One code, with a crosswalk back to every local code it replaces.'],
]

const TRUST = ['Role-based access', 'Full audit trail', 'Duplicate-match dashboard', 'Reversible ERP sync']

function Reveal({ as: Tag = 'div', className = '', children, ...rest }) {
  const [ref, shown] = useInView()
  return (
    <Tag ref={ref} className={`reveal ${shown ? 'is-visible' : ''} ${className}`.trim()} {...rest}>
      {children}
    </Tag>
  )
}

export function Landing() {
  const { user } = useAuth()
  const scrolled = useScrolled()

  return (
    <div className="lp">
      <header className={`lp__nav ${scrolled ? 'is-scrolled' : ''}`}>
        <div className="lp__nav-inner">
          <a className="lp__brand" href="#/">
            <Logo size={30} />
            <span>Material Setu</span>
          </a>
          <nav className="lp__navlinks">
            <a href="#problem">Why</a>
            <a href="#features">Features</a>
            <a href="#flow">How it works</a>
            {user ? (
              <a className="btn btn--primary btn--sm" href="#/app">Open dashboard</a>
            ) : (
              <>
                <a href="#/login">Sign in</a>
                <a className="btn btn--primary btn--sm" href="#/register">Get started</a>
              </>
            )}
          </nav>
        </div>
      </header>

      <section className="lp__hero">
        <div className="lp__hero-copy">
          <span className="lp__eyebrow">For CPSE procurement &amp; engineering teams</span>
          <h1>One material.<br />One national identity.</h1>
          <p>
            CPSEs record the same item under different codes, descriptions and units.
            Material Setu standardizes those records, proposes explainable cross-CPSE
            matches, and publishes an approved identity as a National Material Code —
            every local code preserved.
          </p>
          <div className="lp__cta">
            {user ? (
              <a className="btn btn--primary" href="#/app">Open dashboard</a>
            ) : (
              <>
                <a className="btn btn--primary" href="#/register">Create an account</a>
                <a className="btn btn--ghost" href="#/login">Sign in</a>
              </>
            )}
          </div>
          <p className="lp__note">Human-in-the-loop · explainable matches · full audit trail</p>
        </div>

        <div className="lp__hero-card">
          <div className="lp__glow" aria-hidden="true" />
          <div className="lp__chip lp__chip--a">NTPC · 10-25-4471</div>
          <div className="lp__chip lp__chip--b">ONGC · BRG-6205-ZZ</div>
          <div className="lp__chip lp__chip--c">SAIL · B/6205/2Z</div>
          <div className="lp__hero-nmc">
            <span>NMC-00000042</span>
            <small>Ball bearing, deep groove, 6205 ZZ · 25×52×15 mm</small>
            <em>3 CPSEs linked · 3 local codes preserved</em>
          </div>
        </div>
      </section>

      <Reveal as="section" className="lp__section" id="problem">
        <h2>The same bearing has three different names</h2>
        <p className="lp__lede">
          Every CPSE names and codes its materials differently in its own ERP. The same
          bearing, valve or cable can carry three unrelated local codes across three
          CPSEs, with nothing linking them — so no one can answer a simple question.
        </p>
        <p className="lp__pullquote">“Do we already own this item somewhere else in the group?”</p>
        <ul className="lp__ticklist">
          {PROBLEM_COSTS.map((line) => <li key={line}>{line}</li>)}
        </ul>
      </Reveal>

      <Reveal as="section" className="lp__section lp__section--tint" id="features">
        <h2>What it does</h2>
        <div className="lp__grid">
          {FEATURES.map((f) => (
            <div key={f.title} className="lp__feature">
              <h3>{f.title}</h3>
              <p>{f.body}</p>
            </div>
          ))}
        </div>
      </Reveal>

      <Reveal as="section" className="lp__section lp__section--flow" id="flow">
        <h2>How it works</h2>
        <ol className="lp__flow lp__flow--5">
          {STEPS.map(([t, b], i) => (
            <li key={t}>
              <span className="lp__flow-n">{i + 1}</span>
              <div>
                <strong>{t}</strong>
                <p>{b}</p>
              </div>
            </li>
          ))}
        </ol>
        <div className="lp__callout">
          A match is never an approval to substitute one part for another — every
          explanation stays in plain language, and an engineer signs off separately
          on any substitution.
        </div>
        <div className="lp__pills">
          {TRUST.map((g) => <span key={g} className="lp__pill">{g}</span>)}
        </div>
      </Reveal>

      <Reveal as="section" className="lp__final">
        <h2>Ready to harmonize your material master?</h2>
        <a className="btn btn--primary" href={user ? '#/app' : '#/register'}>
          {user ? 'Open dashboard' : 'Get started'}
        </a>
      </Reveal>

      <footer className="lp__foot">
        <Logo size={22} />
        <span>Material Setu · Identity matching is not engineering substitution approval.</span>
      </footer>
    </div>
  )
}
