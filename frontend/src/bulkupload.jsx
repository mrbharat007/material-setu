import React, { useMemo, useRef, useState } from 'react'
import * as XLSX from 'xlsx'
import { api } from './api.js'
import { useData } from './store.jsx'
import { useAuth } from './auth.jsx'
import { go } from './hooks.js'
import { Icon, StatTile } from './components.jsx'

/* ================================================================ template */

// [header, required] — shown to the user and used to build the CSV template.
export const TEMPLATE_COLUMNS = [
  ['CPSE Code', true],
  ['Material Code', true],
  ['Material Description', true],
  ['UOM', true],
  ['Category', false],
  ['Specification', false],
  ['Material Type', false],
  ['Manufacturer', false],
  ['Manufacturer Part Number', false],
  ['Size', false],
  ['Grade', false],
  ['Standard', false],
]

const EXAMPLE_ROW = [
  'NTPC', '10-25-4471', 'BALL BEARING DEEP GROOVE 6205 ZZ 25X52X15MM', 'NOS',
  'Bearing', 'Deep groove, single row, shielded', 'Spare part', 'SKF', '6205-2Z',
  '25x52x15mm', '—', 'ISO 15',
]

function csvCell(v) {
  const s = String(v ?? '')
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

export function downloadTemplate() {
  const headers = TEMPLATE_COLUMNS.map(([h]) => h)
  const csv = [headers, EXAMPLE_ROW].map((r) => r.map(csvCell).join(',')).join('\r\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'material_bulk_upload_template.csv'
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/* ================================================================ parsing */

// Header text → canonical field. "attributes.x" lands in the free-form
// attributes bag the backend already carries on every material.
const HEADER_ALIASES = {
  'cpse code': 'cpse', 'cpse': 'cpse',
  'material code': 'local_code', 'local code': 'local_code', 'local_code': 'local_code', 'code': 'local_code',
  'material description': 'description', 'description': 'description',
  'category': 'material_family', 'material family': 'material_family',
  'uom': 'uom', 'unit': 'uom', 'unit of measure': 'uom',
  'specification': 'attributes.specification', 'spec': 'attributes.specification',
  'material type': 'attributes.material_type',
  'manufacturer': 'manufacturer',
  'manufacturer part number': 'manufacturer_part_no', 'mfr part no': 'manufacturer_part_no',
  'mfr part no.': 'manufacturer_part_no', 'part number': 'manufacturer_part_no',
  'size': 'attributes.size',
  'grade': 'attributes.grade',
  'standard': 'attributes.standard',
}

const REQUIRED_TARGETS = ['cpse', 'local_code', 'description', 'uom']
const FIELD_LABELS = {
  cpse: 'CPSE Code',
  local_code: 'Material Code',
  description: 'Material Description',
  uom: 'UOM',
}

// "prod_quantity", "Prod-Qty", "PROD QUANTITY" all normalize to the same
// key ("prod quantity") so header aliases don't have to enumerate every
// underscore/hyphen/case variant a spreadsheet might use.
const normHeader = (h) => String(h || '').trim().toLowerCase().replace(/[_-]+/g, ' ').replace(/\s+/g, ' ')

export const VALID_CATEGORIES = new Set([
  'bearing', 'cable', 'valve', 'fastener', 'pipe', 'motor', 'plate',
  'electrical', 'instrument', 'gasket', 'seal', 'hose', 'filter', 'grease',
])

/** Parses a .csv or .xlsx File into row objects keyed by our canonical field
 * names, plus a client-side "does this look OK" pass. The backend is the
 * source of truth — this is only for the preview / fast feedback. */
export async function parseSpreadsheet(file) {
  const buf = await file.arrayBuffer()
  // raw:true is load-bearing: without it SheetJS "helpfully" sniffs
  // date/number-looking CSV cells and reformats them — a code like
  // "10-25-4471" silently becomes a mangled date otherwise.
  const wb = XLSX.read(buf, { type: 'array', raw: true, codepage: 65001 })
  const sheet = wb.Sheets[wb.SheetNames[0]]
  if (!sheet) return { headerFields: new Set(), rows: [] }

  const raw = XLSX.utils.sheet_to_json(sheet, { defval: '', raw: true })
  const firstRowHeaders = new Set(
    Object.keys(raw[0] || {}).map((h) => HEADER_ALIASES[normHeader(h)]).filter(Boolean),
  )

  const rows = raw.map((line, i) => {
    const out = { row: i + 2, cpse: '', local_code: '', description: '', uom: '', material_family: '', manufacturer: '', manufacturer_part_no: '', attributes: {} }
    for (const [key, value] of Object.entries(line)) {
      const target = HEADER_ALIASES[normHeader(key)]
      if (!target) continue
      const v = value == null ? '' : String(value).trim()
      if (!v) continue
      if (target.startsWith('attributes.')) out.attributes[target.slice(11)] = v
      else out[target] = v
    }
    return out
  })

  return { headerFields: firstRowHeaders, rows }
}

/** Client-side hint only — missing/invalid fields, never authoritative. */
export function checkRow(row, defaultCpse) {
  const cpse = row.cpse || defaultCpse || ''
  const missing = []
  if (!cpse.trim()) missing.push('CPSE code')
  if (!row.local_code.trim()) missing.push('Material code')
  if (!row.description.trim()) missing.push('Material description')
  if (!row.uom.trim()) missing.push('UOM')
  if (missing.length) return { ok: false, reason: `Missing ${missing.join(', ')}` }
  if (row.material_family && !VALID_CATEGORIES.has(row.material_family.trim().toLowerCase())) {
    return { ok: false, reason: `Invalid category: ${row.material_family}` }
  }
  return { ok: true, reason: '' }
}

const CHUNK_SIZE = 500

function chunk(arr, size) {
  const out = []
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size))
  return out
}

/* ================================================================ component */

const ACCEPT = '.csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel'

export function BulkUploadForm({ onClose }) {
  const d = useData()
  const { toast, reload, runMatching } = d
  const [cpse, setCpse] = useState('')
  const [fileName, setFileName] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const [parsed, setParsed] = useState(null) // { headerFields, rows }
  const [parseErr, setParseErr] = useState('')
  const [progress, setProgress] = useState(null) // { done, total }
  const [result, setResult] = useState(null) // { created, errors, total }
  const inputRef = useRef(null)

  const knownCpses = useMemo(
    () => [...new Set(d.materials.map((m) => m.cpse))].sort(),
    [d.materials],
  )

  const preview = useMemo(() => {
    if (!parsed) return null
    const checked = parsed.rows.map((r) => ({ ...r, _check: checkRow(r, cpse) }))
    const ok = checked.filter((r) => r._check.ok).length
    const missingCols = REQUIRED_TARGETS.filter(
      (t) => t !== 'cpse' && !parsed.headerFields.has(t),
    )
    return { rows: checked, ok, bad: checked.length - ok, missingCols }
  }, [parsed, cpse])

  const loadFile = async (file) => {
    setParseErr('')
    setResult(null)
    setParsed(null)
    if (!/\.(csv|xlsx)$/i.test(file.name)) {
      setParseErr('Only .csv or .xlsx files are accepted.')
      return
    }
    setFileName(file.name)
    try {
      const out = await parseSpreadsheet(file)
      if (!out.rows.length) {
        setParseErr('No data rows found in this file.')
        return
      }
      setParsed(out)
    } catch (e) {
      setParseErr(`Could not read this file: ${e.message}`)
    }
  }

  const onPick = (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (file) loadFile(file)
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) loadFile(file)
  }

  const reset = () => {
    setParsed(null); setResult(null); setFileName(''); setParseErr(''); setProgress(null)
  }

  const upload = async () => {
    if (!preview) return
    const rows = preview.rows.map(({ _check, ...r }) => ({ ...r, cpse: r.cpse || cpse }))
    const batches = chunk(rows, CHUNK_SIZE)
    setProgress({ done: 0, total: rows.length })

    const created = []
    const errors = []
    for (const batch of batches) {
      try {
        const res = await api.bulkIngest(batch) // eslint-disable-line no-await-in-loop
        created.push(...res.created)
        errors.push(...res.errors)
      } catch (e) {
        for (const r of batch) {
          errors.push({ row: r.row, cpse: r.cpse, local_code: r.local_code, reason: e.message || 'Upload failed' })
        }
      }
      setProgress((p) => ({ ...p, done: Math.min(p.done + batch.length, rows.length) }))
    }

    setResult({ total: rows.length, created, errors })
    await reload()
    if (created.length) toast(`Imported ${created.length} material${created.length > 1 ? 's' : ''}`)
  }

  const newIds = useMemo(() => new Set((result?.created || []).map((m) => m.id)), [result])

  const relatedMatches = useMemo(() => {
    if (!newIds.size) return []
    return d.matches.filter((m) => newIds.has(m.left_material_id) || newIds.has(m.right_material_id))
  }, [d.matches, newIds])

  const withinUpload = relatedMatches.filter(
    (m) => newIds.has(m.left_material_id) && newIds.has(m.right_material_id),
  ).length
  const matchedExisting = relatedMatches.length - withinUpload
  const pendingApprovals = relatedMatches.filter((m) => m.status === 'pending').length

  /* ---------------------------------------------------------- results screen */
  if (result) {
    return (
      <div className="card add-form bulk">
        <div className="bulk__summary stat-grid">
          <StatTile icon={Icon.file} value={result.total} label="Total uploaded" />
          <StatTile icon={Icon.check} value={result.created.length} label="Successfully processed" tone="green" />
          <StatTile icon={Icon.x} value={result.errors.length} label="Validation failures" tone="accent" />
        </div>

        {relatedMatches.length > 0 && (
          <div className="bulk__summary stat-grid">
            <StatTile icon={Icon.link} value={matchedExisting} label="Matched to existing catalog" />
            <StatTile icon={Icon.spark} value={withinUpload} label="Duplicates within this upload" />
            <StatTile icon={Icon.review} value={pendingApprovals} label="Pending approvals" tone="accent" />
          </div>
        )}

        {result.created.length > 0 && (
          <div className="bulk__actions">
            <button className="btn btn--ghost btn--sm" disabled={d.busy} onClick={() => runMatching()}>
              <Icon.spark /> {d.busy ? 'Running AI matching…' : relatedMatches.length ? 'Re-run AI matching' : 'Run AI matching for duplicates'}
            </button>
            {relatedMatches.length > 0 && (
              <button className="btn btn--ghost btn--sm" onClick={() => go('/review')}>
                Open review queue <Icon.chevron />
              </button>
            )}
          </div>
        )}

        {result.errors.length > 0 && (
          <div className="bulk__errors">
            <h5>Row-level errors ({result.errors.length})</h5>
            <div className="bulk__errors-list">
              {result.errors.slice(0, 200).map((e, i) => (
                <div key={i} className="bulk__error-row">
                  <span className="bulk__error-row-n">Row {e.row}</span>
                  <span>{e.cpse || '—'} / {e.local_code || '—'}</span>
                  <span className="bulk__error-reason">{e.reason}</span>
                </div>
              ))}
              {result.errors.length > 200 && (
                <p className="muted">…and {result.errors.length - 200} more.</p>
              )}
            </div>
          </div>
        )}

        <div className="add-form__foot">
          <button className="btn btn--ghost" type="button" onClick={reset}>Upload another file</button>
          <button className="btn btn--primary" type="button" onClick={onClose}>Done</button>
        </div>
      </div>
    )
  }

  /* ---------------------------------------------------------- uploading */
  if (progress) {
    const pct = progress.total ? Math.round((progress.done / progress.total) * 100) : 0
    return (
      <div className="card add-form bulk">
        <h5>Uploading &amp; analyzing…</h5>
        <div className="bulk__progress">
          <div className="bulk__progress-bar"><div className="bulk__progress-fill" style={{ width: `${pct}%` }} /></div>
          <span className="muted">{progress.done.toLocaleString('en-IN')} / {progress.total.toLocaleString('en-IN')} rows</span>
        </div>
      </div>
    )
  }

  /* ---------------------------------------------------------- pick / preview */
  return (
    <div className="card add-form bulk">
      <div className="bulk__grid">
        <label>CPSE (default for rows without one)
          <input value={cpse} onChange={(e) => setCpse(e.target.value)} list="bulk-cpse-list" placeholder="e.g. NTPC" />
          <datalist id="bulk-cpse-list">
            {knownCpses.map((c) => <option key={c} value={c} />)}
          </datalist>
        </label>
        <button type="button" className="btn btn--ghost btn--sm bulk__template" onClick={downloadTemplate}>
          <Icon.download /> Download template
        </button>
      </div>

      <div
        className={`bulk-drop ${dragOver ? 'is-drag' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
      >
        <Icon.file />
        <p><strong>Drag &amp; drop</strong> a CSV or Excel (.xlsx) file here, or click to choose one</p>
        {fileName && <p className="bulk-drop__file muted">{fileName}</p>}
        <input ref={inputRef} type="file" accept={ACCEPT} hidden onChange={onPick} />
      </div>

      {parseErr && <div className="formerr">{parseErr}</div>}

      {preview && (
        <>
          {preview.missingCols.length > 0 && (
            <div className="formerr">
              Missing required column{preview.missingCols.length > 1 ? 's' : ''}: {preview.missingCols.map((c) => FIELD_LABELS[c] || c).join(', ')}.
              Fix the file's header row and re-upload.
            </div>
          )}
          <div className="count-line">
            <strong>{preview.rows.length.toLocaleString('en-IN')}</strong> records parsed —{' '}
            <span style={{ color: 'var(--green)' }}>{preview.ok.toLocaleString('en-IN')} look valid</span>
            {preview.bad > 0 && <> · <span style={{ color: 'var(--amber)' }}>{preview.bad.toLocaleString('en-IN')} have issues</span></>}
          </div>

          <div className="table-wrap bulk-preview">
            <table className="table">
              <thead>
                <tr><th>Row</th><th>CPSE</th><th>Code</th><th className="td-desc">Description</th><th>UOM</th><th>Status</th></tr>
              </thead>
              <tbody>
                {preview.rows.slice(0, 20).map((r) => (
                  <tr key={r.row}>
                    <td className="muted">{r.row}</td>
                    <td>{r.cpse || cpse || <span className="muted">—</span>}</td>
                    <td>{r.local_code || <span className="muted">—</span>}</td>
                    <td className="td-desc">{r.description || <span className="muted">—</span>}</td>
                    <td>{r.uom || <span className="muted">—</span>}</td>
                    <td>
                      {r._check.ok
                        ? <span className="conf conf--high">ok</span>
                        : <span className="conf conf--low" title={r._check.reason}>issue</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {preview.rows.length > 20 && <p className="muted" style={{ padding: '8px 14px' }}>…and {preview.rows.length - 20} more rows.</p>}
          </div>
        </>
      )}

      <p className="add-form__hint"><Icon.attach /> Invalid rows are skipped and reported after upload — nothing is deleted, so you can fix your file and re-upload just the corrected rows.</p>

      <div className="add-form__foot">
        <button
          className="btn btn--primary"
          type="button"
          disabled={!preview || preview.missingCols.length > 0}
          onClick={upload}
        >
          Upload &amp; analyze
        </button>
        <button className="btn btn--ghost" type="button" onClick={onClose}>Cancel</button>
      </div>
    </div>
  )
}

/* ================================================================ procurement upload */
// CSV only (no .xlsx) — a genuine Excel date cell round-trips through a
// serial number with timezone-dependent drift; plain CSV text dates don't
// have that problem, and dates are the one field here that must be exact.

export const PROCUREMENT_TEMPLATE_COLUMNS = [
  ['CPSE Code', true],
  ['Material Code', true],
  ['Order Date (YYYY-MM-DD)', true],
  ['Quantity', true],
  ['Unit Price INR', true],
  ['PO Number', true],
  ['Supplier', false],
]

const PROCUREMENT_EXAMPLE_ROW = ['NTPC', '10-25-4471', '2024-01-15', '100', '250.50', 'NTPC/PO/2024/00123', 'Acme Bearings Ltd']

export function downloadProcurementTemplate() {
  const headers = PROCUREMENT_TEMPLATE_COLUMNS.map(([h]) => h)
  const csv = [headers, PROCUREMENT_EXAMPLE_ROW].map((r) => r.map(csvCell).join(',')).join('\r\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'procurement_bulk_upload_template.csv'
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

const PROC_HEADER_ALIASES = {
  'cpse code': 'cpse', 'cpse': 'cpse',
  'material code': 'local_code', 'local code': 'local_code', 'code': 'local_code',
  'order date': 'order_date', 'order date (yyyy-mm-dd)': 'order_date', 'po date': 'order_date', 'date': 'order_date',
  'transaction date': 'order_date', 'purchase date': 'order_date',
  'quantity': 'quantity', 'qty': 'quantity', 'prod quantity': 'quantity', 'product quantity': 'quantity',
  'production quantity': 'quantity', 'order quantity': 'quantity', 'ordered quantity': 'quantity', 'prod qty': 'quantity',
  'unit price inr': 'unit_price_inr', 'unit price (inr)': 'unit_price_inr', 'unit price': 'unit_price_inr', 'price': 'unit_price_inr',
  'po number': 'po_number', 'po no': 'po_number', 'po no.': 'po_number',
  'supplier': 'supplier', 'vendor': 'supplier',
}

const PROC_REQUIRED = ['cpse', 'local_code', 'order_date', 'quantity', 'unit_price_inr', 'po_number']
const PROC_FIELD_LABELS = {
  cpse: 'CPSE Code', local_code: 'Material Code', order_date: 'Order Date',
  quantity: 'Quantity', unit_price_inr: 'Unit Price', po_number: 'PO Number',
}

/** "15-01-2024" or "15/01/2024" (day-first, per Indian convention) → ISO.
 * Already-ISO ("2024-01-15") strings pass through untouched. Anything else
 * is left as-is so the backend's stricter check reports a clear error. */
function normalizeDate(v) {
  const s = String(v ?? '').trim()
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s
  const m = s.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/)
  if (m) {
    const [, d, mo, y] = m
    return `${y}-${mo.padStart(2, '0')}-${d.padStart(2, '0')}`
  }
  return s
}

export async function parseProcurementCsv(file) {
  const buf = await file.arrayBuffer()
  const wb = XLSX.read(buf, { type: 'array', raw: true, codepage: 65001 })
  const sheet = wb.Sheets[wb.SheetNames[0]]
  if (!sheet) return { headerFields: new Set(), rows: [] }

  const raw = XLSX.utils.sheet_to_json(sheet, { defval: '', raw: true })
  const headerFields = new Set(
    Object.keys(raw[0] || {}).map((h) => PROC_HEADER_ALIASES[normHeader(h)]).filter(Boolean),
  )

  const rows = raw.map((line, i) => {
    const out = { row: i + 2, cpse: '', local_code: '', order_date: '', quantity: '', unit_price_inr: '', po_number: '', supplier: '' }
    for (const [key, value] of Object.entries(line)) {
      const target = PROC_HEADER_ALIASES[normHeader(key)]
      if (!target) continue
      const v = value == null ? '' : String(value).trim()
      if (!v) continue
      out[target] = target === 'order_date' ? normalizeDate(v) : v
    }
    return out
  })

  return { headerFields, rows }
}

export function checkProcurementRow(row) {
  const missing = PROC_REQUIRED.filter((f) => !row[f].trim())
  if (missing.length) return { ok: false, reason: `Missing ${missing.map((f) => PROC_FIELD_LABELS[f]).join(', ')}` }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(row.order_date)) {
    return { ok: false, reason: `Invalid date format: ${row.order_date} (expected YYYY-MM-DD)` }
  }
  if (!Number.isFinite(Number(row.quantity)) || Number(row.quantity) <= 0) {
    return { ok: false, reason: `Invalid quantity: ${row.quantity}` }
  }
  if (!Number.isFinite(Number(row.unit_price_inr)) || Number(row.unit_price_inr) <= 0) {
    return { ok: false, reason: `Invalid unit price: ${row.unit_price_inr}` }
  }
  return { ok: true, reason: '' }
}

const PROC_ACCEPT = '.csv,text/csv'

export function ProcurementUploadForm() {
  const d = useData()
  const { user } = useAuth()
  const { toast, reload } = d
  const [fileName, setFileName] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const [parsed, setParsed] = useState(null)
  const [parseErr, setParseErr] = useState('')
  const [progress, setProgress] = useState(null)
  const [result, setResult] = useState(null)
  const [clearing, setClearing] = useState(false)
  const [confirmClear, setConfirmClear] = useState(false)
  const inputRef = useRef(null)

  const preview = useMemo(() => {
    if (!parsed) return null
    const checked = parsed.rows.map((r) => ({ ...r, _check: checkProcurementRow(r) }))
    const ok = checked.filter((r) => r._check.ok).length
    const missingCols = PROC_REQUIRED.filter((t) => !parsed.headerFields.has(t))
    return { rows: checked, ok, bad: checked.length - ok, missingCols }
  }, [parsed])

  const loadFile = async (file) => {
    setParseErr(''); setResult(null); setParsed(null)
    if (!/\.csv$/i.test(file.name)) {
      setParseErr('Only .csv files are accepted for procurement data (Excel dates round-trip unreliably — export your sheet as CSV first).')
      return
    }
    setFileName(file.name)
    try {
      const out = await parseProcurementCsv(file)
      if (!out.rows.length) { setParseErr('No data rows found in this file.'); return }
      setParsed(out)
    } catch (e) {
      setParseErr(`Could not read this file: ${e.message}`)
    }
  }

  const onPick = (e) => { const f = e.target.files?.[0]; e.target.value = ''; if (f) loadFile(f) }
  const onDrop = (e) => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files?.[0]; if (f) loadFile(f) }
  const reset = () => { setParsed(null); setResult(null); setFileName(''); setParseErr(''); setProgress(null) }

  const upload = async () => {
    if (!preview) return
    const rows = preview.rows.map(({ _check, ...r }) => r)
    const batches = chunk(rows, CHUNK_SIZE)
    setProgress({ done: 0, total: rows.length })

    let imported = 0
    const errors = []
    for (const batch of batches) {
      try {
        const res = await api.bulkIngestProcurement(batch) // eslint-disable-line no-await-in-loop
        imported += res.imported
        errors.push(...res.skipped)
      } catch (e) {
        for (const r of batch) errors.push({ row: r.row, cpse: r.cpse, local_code: r.local_code, reason: e.message || 'Upload failed' })
      }
      setProgress((p) => ({ ...p, done: Math.min(p.done + batch.length, rows.length) }))
    }

    setResult({ total: rows.length, imported, errors })
    await reload()
    if (imported) toast(`Imported ${imported} procurement record${imported > 1 ? 's' : ''}`)
  }

  const doClear = async () => {
    setClearing(true)
    try {
      const res = await api.clearProcurement()
      toast(`Cleared ${res.deleted} procurement record${res.deleted === 1 ? '' : 's'}`)
      await reload()
    } catch (e) {
      toast(e.message, true)
    } finally {
      setClearing(false)
      setConfirmClear(false)
    }
  }

  return (
    <div className="card add-form bulk">
      {user?.role === 'admin' && (
        <div className="bulk__danger">
          <div>
            <strong>Demo / synthetic data</strong>
            <p className="muted">The seed script fills this table with randomly generated prices for the demo. Clear it before relying on real uploaded numbers, so nothing mixes.</p>
          </div>
          {confirmClear ? (
            <div className="bulk__actions">
              <button className="btn btn--reject btn--sm" disabled={clearing} onClick={doClear}>
                {clearing ? 'Clearing…' : 'Yes, delete all procurement records'}
              </button>
              <button className="btn btn--ghost btn--sm" disabled={clearing} onClick={() => setConfirmClear(false)}>Cancel</button>
            </div>
          ) : (
            <button className="btn btn--ghost btn--sm" onClick={() => setConfirmClear(true)}>
              <Icon.trash /> Clear demo data
            </button>
          )}
        </div>
      )}

      {result ? (
        <>
          <div className="bulk__summary stat-grid">
            <StatTile icon={Icon.file} value={result.total} label="Total uploaded" />
            <StatTile icon={Icon.check} value={result.imported} label="Successfully imported" tone="green" />
            <StatTile icon={Icon.x} value={result.errors.length} label="Skipped" tone="accent" />
          </div>

          {result.errors.length > 0 && (
            <div className="bulk__errors">
              <h5>Row-level errors ({result.errors.length})</h5>
              <div className="bulk__errors-list">
                {result.errors.slice(0, 200).map((e, i) => (
                  <div key={i} className="bulk__error-row">
                    <span className="bulk__error-row-n">Row {e.row}</span>
                    <span>{e.cpse || '—'} / {e.local_code || '—'}</span>
                    <span className="bulk__error-reason">{e.reason}</span>
                  </div>
                ))}
                {result.errors.length > 200 && <p className="muted">…and {result.errors.length - 200} more.</p>}
              </div>
            </div>
          )}

          {result.imported > 0 && (
            <p className="add-form__hint">
              <Icon.spark /> Numbers on this page update automatically. Opportunities only appear for materials already published under a National Material Code — approve pending matches in the review queue if a material you just added spend for isn't showing up yet.
            </p>
          )}

          <div className="add-form__foot">
            <button className="btn btn--ghost" type="button" onClick={reset}>Upload another file</button>
          </div>
        </>
      ) : progress ? (
        <>
          <h5>Uploading…</h5>
          <div className="bulk__progress">
            <div className="bulk__progress-bar"><div className="bulk__progress-fill" style={{ width: `${progress.total ? Math.round((progress.done / progress.total) * 100) : 0}%` }} /></div>
            <span className="muted">{progress.done.toLocaleString('en-IN')} / {progress.total.toLocaleString('en-IN')} rows</span>
          </div>
        </>
      ) : (
        <>
          <div className="bulk__grid">
            <button type="button" className="btn btn--ghost btn--sm bulk__template" onClick={downloadProcurementTemplate}>
              <Icon.download /> Download template
            </button>
          </div>

          <div
            className={`bulk-drop ${dragOver ? 'is-drag' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
          >
            <Icon.file />
            <p><strong>Drag &amp; drop</strong> a CSV file here, or click to choose one</p>
            {fileName && <p className="bulk-drop__file muted">{fileName}</p>}
            <input ref={inputRef} type="file" accept={PROC_ACCEPT} hidden onChange={onPick} />
          </div>

          {parseErr && <div className="formerr">{parseErr}</div>}

          {preview && (
            <>
              {preview.missingCols.length > 0 && (
                <div className="formerr">
                  Missing required column{preview.missingCols.length > 1 ? 's' : ''}: {preview.missingCols.map((c) => PROC_FIELD_LABELS[c]).join(', ')}. Fix the file's header row and re-upload.
                </div>
              )}
              <div className="count-line">
                <strong>{preview.rows.length.toLocaleString('en-IN')}</strong> records parsed —{' '}
                <span style={{ color: 'var(--green)' }}>{preview.ok.toLocaleString('en-IN')} look valid</span>
                {preview.bad > 0 && <> · <span style={{ color: 'var(--amber)' }}>{preview.bad.toLocaleString('en-IN')} have issues</span></>}
              </div>

              <div className="table-wrap bulk-preview">
                <table className="table">
                  <thead>
                    <tr><th>Row</th><th>CPSE</th><th>Code</th><th>Date</th><th>Qty</th><th>Price</th><th>PO</th><th>Status</th></tr>
                  </thead>
                  <tbody>
                    {preview.rows.slice(0, 20).map((r) => (
                      <tr key={r.row}>
                        <td className="muted">{r.row}</td>
                        <td>{r.cpse || <span className="muted">—</span>}</td>
                        <td>{r.local_code || <span className="muted">—</span>}</td>
                        <td>{r.order_date || <span className="muted">—</span>}</td>
                        <td>{r.quantity || <span className="muted">—</span>}</td>
                        <td>{r.unit_price_inr || <span className="muted">—</span>}</td>
                        <td>{r.po_number || <span className="muted">—</span>}</td>
                        <td>
                          {r._check.ok
                            ? <span className="conf conf--high">ok</span>
                            : <span className="conf conf--low" title={r._check.reason}>issue</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {preview.rows.length > 20 && <p className="muted" style={{ padding: '8px 14px' }}>…and {preview.rows.length - 20} more rows.</p>}
              </div>
            </>
          )}

          <p className="add-form__hint"><Icon.attach /> Each row must match an existing material by CPSE + Material Code — add materials first if a CPSE's catalog isn't in the system yet.</p>

          <div className="add-form__foot">
            <button className="btn btn--primary" type="button" disabled={!preview || preview.missingCols.length > 0} onClick={upload}>
              Upload &amp; analyze
            </button>
          </div>
        </>
      )}
    </div>
  )
}
