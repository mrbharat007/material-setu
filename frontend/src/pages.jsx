import React, { useEffect, useMemo, useState } from 'react'
import {
  ATTACHMENT_ACCEPT, ATTACHMENT_MAX_BYTES, FAMILIES, SECTORS, api, formatBytes, sectorColor,
} from './api.js'
import { go, useDebounced } from './hooks.js'
import { RUN_STEPS, useData } from './store.jsx'
import { canReview, useAuth } from './auth.jsx'
import {
  AnimatedBar, AttrChips, AttrList, BarRow, DataState, Icon, MaterialSide, Ring,
  StatTile, StatusPill, WhyList,
} from './components.jsx'
import { BulkUploadForm, ProcurementUploadForm } from './bulkupload.jsx'

const rel = (iso) => {
  const s = Math.max(1, Math.round((Date.now() - new Date(iso).getTime()) / 1000))
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.round(s / 60)}m ago`
  if (s < 86400) return `${Math.round(s / 3600)}h ago`
  return `${Math.round(s / 86400)}d ago`
}

export function PageHeader({ title, sub, children }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {sub && <p>{sub}</p>}
      </div>
      {children && <div className="page-head__actions">{children}</div>}
    </div>
  )
}

/* ================================================================ OVERVIEW */

export function Overview() {
  const d = useData()
  const s = d.stats
  const counts = statusCounts(d.matches)

  return (
    <>
      <PageHeader
        title="One material. One national identity."
        sub="CPSEs record the same item under different codes, descriptions and units. Material Setu standardizes those records, proposes explainable cross-CPSE matches, and publishes an approved identity as a National Material Code — every local code preserved."
      />

      <DataState loading={d.loading} error={d.error}>
        <div className="stat-grid">
          <StatTile icon={Icon.materials} value={s?.materials ?? 0} label="Local material records" sub={`${s?.cpses ?? 0} CPSEs onboarded`} />
          <StatTile icon={Icon.review} value={counts.pending} label="In the steward queue" tone="accent" sub="awaiting a human decision" />
          <StatTile icon={Icon.registry} value={s?.nmc_count ?? 0} label="National Material Codes" tone="green" sub={`up to ${s?.max_cpses_linked ?? 0} CPSEs per code`} />
          <StatTile icon={Icon.link} value={s?.master_record_reduction ?? 0} label="Duplicate masters eliminated" tone="green" sub="via approved crosswalks" />
          <StatTile icon={Icon.spark} value={s?.linked_materials ?? 0} label="Local codes harmonized" sub={`${counts.approved} approved · ${counts.rejected} rejected`} />
          <button className="stat-link" onClick={() => go('/opportunities')}>
            <StatTile icon={Icon.rupee} value={fmtINR(s?.aggregation_saving_inr ?? 0)} label="Aggregation opportunity" tone="green" sub={`${s?.procurement_opportunities ?? 0} NMCs with a cross-CPSE price gap`} />
          </button>
        </div>

        {s && (
          <div className="panels">
            <div className="card panel">
              <h4>Materials by sector</h4>
              {s.by_sector.map((r) => (
                <BarRow key={r.name} name={r.name} n={r.n} max={s.by_sector[0].n}
                  color={sectorColor(r.name)} onClick={() => go('/materials')} />
              ))}
            </div>
            <div className="card panel">
              <h4>Contributing CPSEs</h4>
              {s.by_cpse.slice(0, 8).map((r) => (
                <BarRow key={r.name} name={r.name} n={r.n} max={s.by_cpse[0].n}
                  color="var(--navy-600)" onClick={() => go('/materials')} />
              ))}
            </div>
          </div>
        )}

        {s && s.by_supply_group?.length > 0 && (
          <div className="card panel">
            <h4>Materials by Federal Supply Group <span className="panel__note">NATO Codification System</span></h4>
            {s.by_supply_group.slice(0, 10).map((r) => (
              <BarRow key={r.name} name={r.name} n={r.n} max={s.by_supply_group[0].n}
                color="var(--accent)" onClick={() => go('/materials')} />
            ))}
          </div>
        )}

        {s && (
          <div className="card panel">
            <h4>Material families</h4>
            <div className="family-chips">
              {s.by_family.map((f) => (
                <span key={f.name} className="family-chip">{f.name} <b>{f.n}</b></span>
              ))}
            </div>
          </div>
        )}

        <div className="panels">
          <div className="card panel">
            <div className="panel__head">
              <h4>Recent activity</h4>
              <button className="linkbtn" onClick={() => go('/audit')}>Full trail <Icon.chevron /></button>
            </div>
            <AuditTimeline items={d.audit.slice(0, 6)} />
          </div>
          <div className="card panel callout">
            <h4>Try it</h4>
            <ol>
              <li>Open <button className="linkbtn" onClick={() => go('/materials')}>Materials</button> and add a local record — watch it get standardized live.</li>
              <li>Hit <b>Run harmonization</b> (top right) to score cross-CPSE pairs.</li>
              <li>Work the <button className="linkbtn" onClick={() => go('/review')}>Review queue</button>: approve to publish an NMC, reject a near-miss.</li>
              <li>See the crosswalks in the <button className="linkbtn" onClick={() => go('/registry')}>Registry</button>.</li>
            </ol>
            <p className="fineprint">Identity matching is not engineering substitution approval — every match keeps an explanation and a human step.</p>
          </div>
        </div>
      </DataState>
    </>
  )
}

/* ================================================================ MATERIALS */

const blankForm = {
  cpse: '', sector: '', local_code: '', description: '',
  material_family: '', manufacturer: '', manufacturer_part_no: '', uom: '',
}

function AddMaterialForm({ onClose }) {
  const { addMaterial } = useData()
  const [form, setForm] = useState(blankForm)
  const [preview, setPreview] = useState(null)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')
  const [created, setCreated] = useState(null)

  const probe = useDebounced(`${form.description}|${form.material_family}|${form.uom}`, 400)
  useEffect(() => {
    if (created) return
    if (!form.description.trim()) { setPreview(null); return }
    let alive = true
    api.standardize({ ...form, cpse: form.cpse || 'X', local_code: form.local_code || 'X' })
      .then((p) => { if (alive) setPreview(p) })
      .catch(() => { if (alive) setPreview(null) })
    return () => { alive = false }
  }, [probe]) // eslint-disable-line react-hooks/exhaustive-deps

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const ready = form.cpse && form.local_code && form.description

  const submit = async (e) => {
    e.preventDefault()
    setErr(''); setSaving(true)
    try {
      const payload = Object.fromEntries(
        Object.entries(form).map(([k, v]) => [k, v.trim() || null]),
      )
      payload.cpse = form.cpse.trim()
      payload.local_code = form.local_code.trim()
      payload.description = form.description.trim()
      const saved = await addMaterial(payload)
      setCreated(saved)
    } catch (e2) {
      setErr(e2.message)
    } finally {
      setSaving(false)
    }
  }

  if (created) {
    return (
      <div className="card add-form add-form--done">
        <div className="add-form__done-head">
          <span className="add-form__done-check"><Icon.check /></span>
          <div>
            <strong>{created.cpse} / {created.local_code}</strong> added.
            <p className="muted">Attach photos, drawings or datasheets for this record — pick as many as you need, or skip.</p>
          </div>
        </div>
        <Attachments materialId={created.id} canManage />
        <div className="add-form__foot">
          <button className="btn btn--primary" type="button" onClick={onClose}>Done</button>
        </div>
      </div>
    )
  }

  return (
    <form className="card add-form" onSubmit={submit}>
      <div className="add-form__grid">
        <label>CPSE
          <input value={form.cpse} onChange={set('cpse')} placeholder="e.g. NTPC" required />
        </label>
        <label>Sector
          <select value={form.sector} onChange={set('sector')}>
            <option value="">—</option>
            {SECTORS.map((x) => <option key={x}>{x}</option>)}
          </select>
        </label>
        <label>Local code
          <input value={form.local_code} onChange={set('local_code')} placeholder="e.g. 10-25-4471" required />
        </label>
        <label>Material family
          <select value={form.material_family} onChange={set('material_family')}>
            <option value="">—</option>
            {FAMILIES.map((x) => <option key={x}>{x}</option>)}
          </select>
        </label>
        <label className="span2">Description
          <input value={form.description} onChange={set('description')}
            placeholder="e.g. BALL BEARING DEEP GROOVE 6205 ZZ 25X52X15MM" required />
        </label>
        <label>Manufacturer
          <input value={form.manufacturer} onChange={set('manufacturer')} placeholder="optional" />
        </label>
        <label>Mfr part no.
          <input value={form.manufacturer_part_no} onChange={set('manufacturer_part_no')} placeholder="optional" />
        </label>
        <label>UOM
          <input value={form.uom} onChange={set('uom')} placeholder="e.g. NOS" />
        </label>
      </div>

      <div className="add-form__preview">
        <h5>Standardization preview</h5>
        {preview ? (
          <>
            <div className="kv"><span>normalized</span><code>{preview.normalized_description}</code></div>
            {preview.classification && preview.classification.fsc !== '9999' && (
              <div className="kv"><span>class →</span>
                <span>
                  FSC <code>{preview.classification.fsc}</code> · {preview.classification.fsc_title}
                  <span className={`conf conf--${preview.classification.confidence}`}>{preview.classification.confidence}</span>
                  <br /><span className="muted">{preview.classification.basis}</span>
                </span>
              </div>
            )}
            {preview.uom_standard && (
              <div className="kv"><span>unit →</span>
                <span>
                  {preview.uom_standard.code
                    ? <><code>{preview.uom_standard.code}</code> {preview.uom_standard.name} <span className="muted">· UN/CEFACT Rec 20</span></>
                    : <span className="muted">no Rec 20 code — “{preview.uom_standard.name}”</span>}
                </span>
              </div>
            )}
            {preview.resolved_family && <div className="kv"><span>family →</span><code>{preview.resolved_family} template</code></div>}
            <div className="kv"><span>attributes</span><AttrList attrs={preview.extracted_attributes} /></div>
          </>
        ) : (
          <p className="muted">Type a description to see how it standardizes.</p>
        )}
      </div>

      {err && <div className="formerr">{err}</div>}
      <p className="add-form__hint"><Icon.attach /> Fill in CPSE, local code &amp; description, then save — you'll attach photos, drawings or PDF/PPTX right after, on the next screen.</p>
      <div className="add-form__foot">
        <button className="btn btn--primary" disabled={!ready || saving} type="submit">
          {saving ? 'Saving…' : 'Add material'}
        </button>
        <button className="btn btn--ghost" type="button" onClick={onClose}>Cancel</button>
      </div>
    </form>
  )
}

function AttachmentThumb({ att }) {
  const [url, setUrl] = useState(null)
  const isImage = att.content_type.startsWith('image/')

  useEffect(() => {
    if (!isImage) return
    let alive = true
    let objectUrl = null
    api.attachmentBlob(att.id).then((blob) => {
      if (!alive) return
      objectUrl = URL.createObjectURL(blob)
      setUrl(objectUrl)
    }).catch(() => {})
    return () => {
      alive = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [att.id, isImage])

  if (!isImage) return <div className="attach__thumb attach__thumb--file"><Icon.file /></div>
  return url
    ? <img className="attach__thumb" src={url} alt={att.filename} />
    : <div className="attach__thumb attach__thumb--loading" />
}

async function downloadAttachment(att) {
  const blob = await api.attachmentBlob(att.id)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = att.filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 4000)
}

function Attachments({ materialId, canManage }) {
  const { toast } = useData()
  const [items, setItems] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const load = () => api.attachments(materialId).then(setItems).catch(() => setItems([]))
  useEffect(() => { load() }, [materialId]) // eslint-disable-line react-hooks/exhaustive-deps

  const onPick = async (e) => {
    const files = Array.from(e.target.files || [])
    e.target.value = ''
    if (!files.length) return

    const oversized = files.filter((f) => f.size > ATTACHMENT_MAX_BYTES).map((f) => f.name)
    const toUpload = files.filter((f) => f.size <= ATTACHMENT_MAX_BYTES)

    setErr(oversized.length ? `Too large (15 MB limit): ${oversized.join(', ')}` : '')
    if (!toUpload.length) return

    setBusy(true)
    const failed = []
    for (const file of toUpload) {
      try {
        await api.uploadAttachment(materialId, file) // eslint-disable-line no-await-in-loop
      } catch {
        failed.push(file.name)
      }
    }
    await load()
    setBusy(false)

    const okCount = toUpload.length - failed.length
    if (okCount) toast(`Attached ${okCount} file${okCount > 1 ? 's' : ''}`)
    if (failed.length) setErr((prev) => `${prev ? prev + ' · ' : ''}Failed: ${failed.join(', ')}`)
  }

  const onDelete = async (att) => {
    setBusy(true)
    try {
      await api.deleteAttachment(att.id)
      await load()
    } catch (e2) {
      toast(e2.message, true)
    } finally {
      setBusy(false)
    }
  }

  if (items === null) return <p className="muted">Loading attachments…</p>

  return (
    <div className="attach">
      {items.length > 0 && (
        <div className="attach__grid">
          {items.map((att) => (
            <div key={att.id} className="attach__card">
              <button type="button" className="attach__view" onClick={() => downloadAttachment(att)} title="Download">
                <AttachmentThumb att={att} />
              </button>
              <div className="attach__meta">
                <span className="attach__name" title={att.filename}>{att.filename}</span>
                <span className="attach__sub muted">{formatBytes(att.size_bytes)} · {att.uploaded_by || 'unknown'}</span>
              </div>
              <div className="attach__actions">
                <button type="button" className="iconbtn" title="Download" onClick={() => downloadAttachment(att)}><Icon.download /></button>
                {canManage && (
                  <button type="button" className="iconbtn iconbtn--danger" title="Remove" onClick={() => onDelete(att)}><Icon.trash /></button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      {canManage ? (
        <label className={`attach__upload ${busy ? 'is-busy' : ''}`}>
          <Icon.attach /> {busy ? 'Uploading…' : 'Attach files — image, PDF or PPTX, pick multiple'}
          <input type="file" accept={ATTACHMENT_ACCEPT} multiple onChange={onPick} disabled={busy} hidden />
        </label>
      ) : (
        !items.length && <p className="muted">No attachments.</p>
      )}
      {err && <div className="formerr">{err}</div>}
    </div>
  )
}

export function Materials() {
  const d = useData()
  const { user } = useAuth()
  const [q, setQ] = useState('')
  const [sector, setSector] = useState('')
  const [adding, setAdding] = useState(false)
  const [addMode, setAddMode] = useState('manual')
  const [openRow, setOpenRow] = useState(null)
  const query = useDebounced(q, 200)

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return d.materials.filter((m) => {
      if (sector && m.sector !== sector) return false
      if (!needle) return true
      return `${m.cpse} ${m.local_code} ${m.description} ${m.material_family || ''} ${m.manufacturer || ''} ${m.fsc || ''} ${m.fsc_title || ''} ${m.fsg_title || ''}`
        .toLowerCase().includes(needle)
    })
  }, [d.materials, query, sector])

  return (
    <>
      <PageHeader title="Local material master" sub={`${d.materials.length} records ingested from ${d.stats?.cpses ?? 0} CPSEs`}>
        {canReview(user) && (
          <button className="btn btn--primary" onClick={() => setAdding((v) => !v)}>
            <Icon.add /> {adding ? 'Close' : 'Add material'}
          </button>
        )}
      </PageHeader>

      {adding && canReview(user) && (
        <>
          <div className="tabs">
            <button className={`tab ${addMode === 'manual' ? 'is-on' : ''}`} onClick={() => setAddMode('manual')}>Manual entry</button>
            <button className={`tab ${addMode === 'bulk' ? 'is-on' : ''}`} onClick={() => setAddMode('bulk')}>Bulk upload</button>
          </div>
          {addMode === 'manual'
            ? <AddMaterialForm onClose={() => setAdding(false)} />
            : <BulkUploadForm onClose={() => setAdding(false)} />}
        </>
      )}

      <div className="toolbar">
        <div className="search">
          <Icon.search />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search code, description, manufacturer…" />
        </div>
        <div className="chipset">
          <button className={`fchip ${!sector ? 'is-on' : ''}`} onClick={() => setSector('')}>All sectors</button>
          {SECTORS.map((x) => (
            <button key={x} className={`fchip ${sector === x ? 'is-on' : ''}`} onClick={() => setSector(x)}>{x}</button>
          ))}
        </div>
      </div>

      <DataState loading={d.loading} error={d.error} empty={!rows.length} emptyText="No materials match.">
        <div className="card table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>CPSE</th><th>Local code</th><th>Description</th>
                <th>FSC</th><th>UOM</th><th>NMC</th><th aria-label="expand" />
              </tr>
            </thead>
            <tbody>
              {rows.map((m) => (
                <React.Fragment key={m.id}>
                  <tr className="table__row" onClick={() => setOpenRow(openRow === m.id ? null : m.id)}>
                    <td><span className="dot" style={{ background: sectorColor(m.sector) }} /> {m.cpse}</td>
                    <td><code>{m.local_code}</code></td>
                    <td className="td-desc">{m.description}</td>
                    <td>{m.fsc && m.fsc !== '9999'
                      ? <span className="fsc-tag" title={m.fsc_title}>{m.fsc}</span>
                      : <span className="muted">—</span>}</td>
                    <td>{m.uom_code
                      ? <span title={m.uom || ''}>{m.uom_code}</span>
                      : (m.uom || '—')}</td>
                    <td>{d.materialNmc.get(m.id)
                      ? <code className="nmc-tag">{d.materialNmc.get(m.id)}</code>
                      : <span className="muted">—</span>}</td>
                    <td className={`chev ${openRow === m.id ? 'is-open' : ''}`}><Icon.chevron /></td>
                  </tr>
                  {openRow === m.id && (
                    <tr className="table__detail">
                      <td colSpan={7}>
                        <div className="kv"><span>normalized</span><code>{m.normalized_description}</code></div>
                        <div className="kv"><span>class</span>
                          <span>{m.fsc && m.fsc !== '9999'
                            ? <>FSC <code>{m.fsc}</code> · {m.fsc_title} <span className="muted">(group {m.fsg} — {m.fsg_title})</span></>
                            : <span className="muted">unclassified — pending steward classification</span>}</span>
                        </div>
                        <div className="kv"><span>unit</span>
                          <span>{m.uom || '—'}{m.uom_code && <> → <code>{m.uom_code}</code> <span className="muted">(UN/CEFACT Rec 20)</span></>}</span>
                        </div>
                        <div className="kv"><span>extracted</span><AttrList attrs={m.extracted_attributes} /></div>
                        <div className="kv kv--attach">
                          <span>attachments</span>
                          <Attachments materialId={m.id} canManage={canReview(user)} />
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted count-line">{rows.length} of {d.materials.length} records</p>
      </DataState>
    </>
  )
}

/* ================================================================ REVIEW */

function RunPanel({ step, materials }) {
  return (
    <div className="card runpanel">
      <div className="runpanel__title">Harmonization run — {materials.toLocaleString('en-IN')} materials</div>
      {RUN_STEPS.map((label, i) => {
        const state = i < step ? 'is-done' : i === step ? 'is-active' : ''
        return (
          <div key={label} className={`run-step ${state}`}>
            <span className="run-step__dot">{i < step ? '✓' : ''}</span>{label}
          </div>
        )
      })}
    </div>
  )
}

function MatchCard({ match }) {
  const { byMaterial, decide, busy } = useData()
  const { user } = useAuth()
  const left = byMaterial.get(match.left_material_id)
  const right = byMaterial.get(match.right_material_id)
  const [leaving, setLeaving] = useState(false)

  useEffect(() => { if (match.status !== 'pending') setLeaving(false) }, [match.status])

  const act = (decision) => {
    setLeaving(true)
    setTimeout(() => decide(match.id, decision), 320)
  }

  return (
    <div className={`card match ${leaving ? 'is-leaving' : ''}`}>
      <div className="match__top">
        <Ring score={match.score} />
        <div className="match__meta">
          <div className="match__title">Proposed identity match · candidate #{match.id}</div>
          <div className="match__pairline">
            {left?.cpse} <span className="muted">↔</span> {right?.cpse}
          </div>
        </div>
        <StatusPill status={match.status} />
      </div>

      <div className="pair">
        <MaterialSide m={left} />
        <span className="pair__link"><Icon.link /></span>
        <MaterialSide m={right} />
      </div>

      <AttrChips left={left?.extracted_attributes} right={right?.extracted_attributes} />
      <WhyList lines={match.explanation} />

      <div className="match__actions">
        {match.status === 'pending' ? (
          canReview(user) ? (
            <>
              <button className="btn btn--sm btn--approve" disabled={busy} onClick={() => act('approved')}>
                <Icon.check /> Approve identity
              </button>
              <button className="btn btn--sm btn--reject" disabled={busy} onClick={() => act('rejected')}>
                <Icon.x /> Reject
              </button>
              <span className="match__decided">AI proposes · you decide</span>
            </>
          ) : (
            <span className="match__decided">Awaiting a steward decision — you have view-only access</span>
          )
        ) : (
          <span className="match__decided">
            {match.status} by {match.reviewer || 'steward'}{match.review_note ? ` — ${match.review_note}` : ''}
          </span>
        )}
      </div>
    </div>
  )
}

export function Review() {
  const d = useData()
  const [tab, setTab] = useState('pending')
  const [expanded, setExpanded] = useState(false)
  const counts = statusCounts(d.matches)
  const CAP = 8

  const filtered = d.matches
    .filter((m) => tab === 'all' || m.status === tab)
    .sort((a, b) => b.score - a.score)
  const shown = expanded ? filtered : filtered.slice(0, CAP)

  return (
    <>
      <PageHeader title="Steward review queue" sub="AI proposes cross-CPSE identity matches with an explanation. A steward approves or rejects each one." />

      {d.runStep >= 0 && <RunPanel step={d.runStep} materials={d.materials.length} />}

      <div className="tabs">
        {['pending', 'approved', 'rejected', 'all'].map((t) => (
          <button key={t} className={`tab ${tab === t ? 'is-on' : ''}`}
            onClick={() => { setTab(t); setExpanded(false) }}>
            {t}<span className="tab__count">{counts[t] ?? d.matches.length}</span>
          </button>
        ))}
      </div>

      <DataState
        loading={d.loading} error={d.error}
        empty={!filtered.length}
        emptyText={d.matches.length ? `Nothing ${tab}.` : 'No candidates yet — run harmonization.'}
      >
        <div className="queue">
          {shown.map((m) => <MatchCard key={m.id} match={m} />)}
          {filtered.length > CAP && (
            <button className="btn btn--ghost" onClick={() => setExpanded((v) => !v)}>
              {expanded ? 'Show fewer' : `Show all ${filtered.length}`}
            </button>
          )}
        </div>
      </DataState>
    </>
  )
}

/* ================================================================ REGISTRY */

function NmcCard({ rec }) {
  const { byMaterial } = useData()
  const canon = byMaterial.get(rec.canonical_material_id)
  const cpses = new Set(rec.local_material_ids.map((id) => byMaterial.get(id)?.cpse).filter(Boolean))
  return (
    <div className="card nmc">
      <div className="nmc__code">{rec.nmc}</div>
      {rec.fsc && rec.fsc !== '9999' && (
        <div className="nmc__fsc" title={`Federal Supply Group ${rec.fsg} — ${rec.fsg_title}`}>
          FSC {rec.fsc} · {rec.fsc_title}
        </div>
      )}
      <div className="nmc__canon">
        <span>canonical: </span>{canon ? canon.description : `material ${rec.canonical_material_id}`}
      </div>
      <div className="cross">
        {rec.local_material_ids.map((id) => {
          const m = byMaterial.get(id)
          return (
            <span key={id} className="cross__item">
              <span className="dot" style={{ background: sectorColor(m?.sector) }} />
              <code>{m ? `${m.cpse} / ${m.local_code}` : id}</code>
            </span>
          )
        })}
      </div>
      <div className="nmc__foot">{cpses.size} CPSEs linked · {rec.local_material_ids.length} local codes</div>
    </div>
  )
}

export function Registry() {
  const d = useData()
  const [q, setQ] = useState('')
  const needle = q.trim().toLowerCase()
  const rows = d.nmc.filter((r) => {
    if (!needle) return true
    const codes = r.local_material_ids.map((id) => d.byMaterial.get(id))
      .map((m) => m ? `${m.cpse} ${m.local_code} ${m.description}` : '').join(' ')
    return `${r.nmc} ${r.explanation} ${r.fsc || ''} ${r.fsc_title || ''} ${r.fsg_title || ''} ${codes}`.toLowerCase().includes(needle)
  })

  return (
    <>
      <PageHeader
        title="National Material Registry"
        sub={`${d.nmc.length} National Material Codes · ${d.stats?.master_record_reduction ?? 0} duplicate masters eliminated · every local code preserved as a crosswalk`}
      />
      <div className="toolbar">
        <div className="search">
          <Icon.search />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search NMC, CPSE, description…" />
        </div>
      </div>
      <DataState loading={d.loading} error={d.error} empty={!rows.length}
        emptyText="Approved identities are published here as National Material Codes.">
        <div className="registry">
          {rows.map((r) => <NmcCard key={r.nmc} rec={r} />)}
        </div>
      </DataState>
    </>
  )
}

/* ================================================================ AUDIT */

export function AuditTimeline({ items }) {
  if (!items.length) return <div className="statebox">No activity yet.</div>
  return (
    <div className="audit">
      {items.map((a) => {
        const kind = a.action.includes('approved') ? 'is-approved'
          : a.action.includes('rejected') ? 'is-rejected'
            : a.action.includes('run') ? 'is-run' : ''
        return (
          <div key={a.id} className={`aud ${kind}`}>
            <div className="aud__line">
              <b>{a.action}</b>
              {a.details?.nmc ? ` → ${a.details.nmc}` : ''}
              {a.details?.note ? ` · ${a.details.note}` : ''}
              {a.action === 'matches.run' ? ` · ${a.details.candidates} candidates from ${a.details.materials} materials` : ''}
              {a.action === 'material.ingested' ? ` · ${a.details.cpse} / ${a.details.local_code}` : ''}
            </div>
            <div className="aud__meta">{a.actor} · {rel(a.created_at)}</div>
          </div>
        )
      })}
    </div>
  )
}

export function Audit() {
  const d = useData()
  const [kind, setKind] = useState('all')
  const kinds = ['all', 'material.ingested', 'matches.run', 'match.approved', 'match.rejected']
  const items = d.audit.filter((a) => kind === 'all' || a.action === kind)

  return (
    <>
      <PageHeader title="Audit trail" sub="Every ingestion, harmonization run and steward decision is recorded, with the actor." />
      <div className="chipset">
        {kinds.map((k) => (
          <button key={k} className={`fchip ${kind === k ? 'is-on' : ''}`} onClick={() => setKind(k)}>
            {k === 'all' ? 'All events' : k}
          </button>
        ))}
      </div>
      <DataState loading={d.loading} error={d.error} empty={!items.length} emptyText="No events.">
        <div className="card panel"><AuditTimeline items={items} /></div>
      </DataState>
    </>
  )
}

/* ================================================================ OPPORTUNITIES */

function fmtINR(n) {
  if (n == null) return '—'
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(1)} L`
  if (n >= 1e3) return `₹${(n / 1e3).toFixed(0)}k`
  return `₹${Math.round(n).toLocaleString('en-IN')}`
}
const rupee = (n) => `₹${Math.round(n).toLocaleString('en-IN')}`

function OpportunityCard({ o }) {
  const maxAvg = Math.max(...o.per_cpse.map((c) => c.avg_price))
  return (
    <div className="card opp">
      <div className="opp__head">
        <div>
          <div className="opp__nmc">{o.nmc}</div>
          <div className="opp__desc">{o.description}</div>
          <div className="opp__fsc">FSC {o.fsc} · {o.fsc_title}</div>
        </div>
        <div className="opp__save">
          <span>{fmtINR(o.estimated_saving_inr)}</span>
          <small>est. annual saving</small>
        </div>
      </div>

      <div className="opp__stats">
        <div><b>{o.cpse_count}</b> CPSEs buying</div>
        <div><b>{o.price_spread_ratio}×</b> price spread</div>
        <div><b>{rupee(o.min_unit_price)}</b>–{rupee(o.max_unit_price)} / {o.uom || 'unit'}</div>
        <div><b>{o.total_quantity.toLocaleString('en-IN')}</b> {o.uom || 'units'} · {o.order_count} POs</div>
      </div>

      <div className="opp__bars">
        {o.per_cpse.map((c) => (
          <div key={c.cpse} className="opp__bar">
            <span className="opp__bar-cpse">{c.cpse}{c.cpse === o.best_price_cpse && <span className="opp__best">best</span>}</span>
            <AnimatedBar
              pct={Math.max(6, (c.avg_price / maxAvg) * 100)}
              color={c.cpse === o.best_price_cpse ? 'var(--green)' : 'var(--navy-600)'}
            />
            <span className="opp__bar-price">{rupee(c.avg_price)}</span>
          </div>
        ))}
      </div>
      <div className="opp__foot">
        If every CPSE procured this at {o.best_price_cpse}’s rate ({rupee(o.min_unit_price)}), the
        combined spend of {fmtINR(o.total_value_inr)} drops by {fmtINR(o.estimated_saving_inr)} — a
        single aggregated tender opportunity.
      </div>
    </div>
  )
}

export function Opportunities() {
  const d = useData()
  const { user } = useAuth()
  const [uploading, setUploading] = useState(false)
  const list = [...d.opportunities].sort((a, b) => b.estimated_saving_inr - a.estimated_saving_inr)
  const total = list.reduce((s, o) => s + o.estimated_saving_inr, 0)
  const spend = list.reduce((s, o) => s + o.total_value_inr, 0)

  return (
    <>
      <PageHeader
        title="Collaborative procurement"
        sub="Once duplicates are harmonized under one National Material Code, the spend behind it becomes visible across CPSEs — and so does the price gap for the identical item. Each row is a tender-aggregation opportunity."
      >
        {canReview(user) && (
          <button className="btn btn--primary" onClick={() => setUploading((v) => !v)}>
            <Icon.add /> {uploading ? 'Close' : 'Upload procurement data'}
          </button>
        )}
      </PageHeader>

      {uploading && canReview(user) && <ProcurementUploadForm />}

      <DataState loading={d.loading} error={d.error} empty={!list.length}
        emptyText="Publish some National Material Codes first — opportunities are computed per NMC with cross-CPSE spend.">
        <div className="stat-grid opp-grid">
          <StatTile value={fmtINR(total)} label="Estimated annual saving" tone="green" sub="vs. each CPSE's best achieved price" />
          <StatTile value={list.length} label="Aggregation opportunities" tone="accent" sub="NMCs bought by 2+ CPSEs with a price gap" />
          <StatTile value={fmtINR(spend)} label="Spend under review" sub="across the harmonized codes" />
        </div>
        <div className="opps">
          {list.map((o) => <OpportunityCard key={o.nmc} o={o} />)}
        </div>
      </DataState>
    </>
  )
}

/* ================================================================ TEAM (admin) */

const ROLES = ['steward', 'admin']
const ROLE_HINT = {
  steward: 'Ingest materials, run harmonization, approve / reject matches',
  admin: 'Everything, plus user management and demo reset',
}

export function Team() {
  const { user } = useAuth()
  const { toast } = useData()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [savingId, setSavingId] = useState(null)

  const load = () => {
    setLoading(true)
    api.users()
      .then((rows) => { setUsers(rows); setError(null) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }
  useEffect(load, [])

  const changeRole = async (u, role) => {
    if (role === u.role) return
    setSavingId(u.id)
    try {
      const updated = await api.setUserRole(u.id, role)
      setUsers((list) => list.map((x) => (x.id === updated.id ? updated : x)))
      toast(`${updated.name} is now ${role}`)
    } catch (e) {
      toast(e.message, true)
      load()
    } finally {
      setSavingId(null)
    }
  }

  const admins = users.filter((u) => u.role === 'admin').length

  return (
    <>
      <PageHeader
        title="Team & access"
        sub="New sign-ups start as a steward and can work the review queue right away. Promote a colleague to admin for full control."
      />
      <DataState loading={loading} error={error} empty={!users.length} emptyText="No users yet.">
        <div className="card table-wrap">
          <table className="table">
            <thead>
              <tr><th>User</th><th>CPSE</th><th>Joined</th><th>Role</th></tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isSelf = u.id === user.id
                const lockLastAdmin = u.role === 'admin' && admins <= 1
                return (
                  <tr key={u.id}>
                    <td>
                      <div className="team__name">
                        {u.name}{isSelf && <span className="team__you">you</span>}
                      </div>
                      <div className="muted team__email">{u.email}</div>
                    </td>
                    <td>{u.cpse || '—'}</td>
                    <td className="muted">{u.created_at ? new Date(u.created_at).toLocaleDateString('en-IN') : '—'}</td>
                    <td>
                      <select
                        className="team__role"
                        value={u.role}
                        disabled={savingId === u.id || lockLastAdmin}
                        title={lockLastAdmin ? 'The last administrator cannot be demoted' : ROLE_HINT[u.role]}
                        onChange={(e) => changeRole(u, e.target.value)}
                      >
                        {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                      </select>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <div className="team__legend">
          {ROLES.map((r) => (
            <div key={r}><span className={`role-pill role-pill--${r}`}>{r}</span> {ROLE_HINT[r]}</div>
          ))}
        </div>
      </DataState>
    </>
  )
}

/* ================================================================ helpers */

function statusCounts(matches) {
  return {
    pending: matches.filter((m) => m.status === 'pending').length,
    approved: matches.filter((m) => m.status === 'approved').length,
    rejected: matches.filter((m) => m.status === 'rejected').length,
    all: matches.length,
  }
}
