import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api } from './api.js'

const Ctx = createContext(null)
export const useData = () => useContext(Ctx)

export const RUN_STEPS = [
  'Standardizing descriptions & units',
  'Extracting engineering attributes',
  'Scoring cross-CPSE candidate pairs',
  'Ranking & explaining matches',
]

export function DataProvider({ children }) {
  const [data, setData] = useState({ stats: null, materials: [], matches: [], nmc: [], audit: [], opportunities: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [toasts, setToasts] = useState([])
  const [runStep, setRunStep] = useState(-1)
  const [busy, setBusy] = useState(false)

  const toast = useCallback((msg, err = false) => {
    const id = Math.random()
    setToasts((t) => [...t, { id, msg, err }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3800)
  }, [])

  const reload = useCallback(async () => {
    // Each panel loads independently — one failing endpoint must not blank the
    // whole dashboard.
    const keys = ['stats', 'materials', 'matches', 'nmc', 'audit', 'opportunities']
    const calls = [api.stats(), api.materials(), api.matches(), api.nmc(), api.audit(), api.opportunities()]
    const settled = await Promise.allSettled(calls)

    const next = {}
    const failed = []
    settled.forEach((r, i) => {
      if (r.status === 'fulfilled') next[keys[i]] = r.value
      else failed.push(keys[i])
    })
    // A 401 anywhere already cleared the token (api.js) → AuthProvider logs out.

    setData((prev) => ({
      stats: next.stats ?? prev.stats,
      materials: next.materials ?? prev.materials ?? [],
      matches: next.matches ?? prev.matches ?? [],
      nmc: next.nmc ?? prev.nmc ?? [],
      audit: next.audit ?? prev.audit ?? [],
      opportunities: next.opportunities ?? prev.opportunities ?? [],
    }))
    setError(failed.length === keys.length ? 'Cannot reach the API' : null)
    setLoading(false)
  }, [])

  useEffect(() => { reload() }, [reload])

  const runMatching = useCallback(async () => {
    setBusy(true)
    setRunStep(0)
    const ticker = setInterval(
      () => setRunStep((s) => (s < RUN_STEPS.length - 1 ? s + 1 : s)),
      650,
    )
    try {
      await api.runMatching(0.6)
      await new Promise((r) => setTimeout(r, 500))
      clearInterval(ticker)
      setRunStep(RUN_STEPS.length)
      await new Promise((r) => setTimeout(r, 400))
      await reload()
      toast('Harmonization run complete')
    } catch (e) {
      toast(e.message, true)
    } finally {
      clearInterval(ticker)
      setRunStep(-1)
      setBusy(false)
    }
  }, [reload, toast])

  const decide = useCallback(async (id, decision, note) => {
    setBusy(true)
    try {
      const res = await api.decide(id, decision, note || null)
      await reload()
      toast(
        decision === 'approved'
          ? `Published ${res.nmc?.nmc || 'National Material Code'}`
          : 'Match rejected — recorded in audit trail',
      )
    } catch (e) {
      toast(e.message, true)
    } finally {
      setBusy(false)
    }
  }, [reload, toast])

  const addMaterial = useCallback(async (material) => {
    const [saved] = await api.ingest(material)
    await reload()
    toast(`Added ${material.cpse} / ${material.local_code}`)
    return saved
  }, [reload, toast])

  const byMaterial = useMemo(
    () => new Map(data.materials.map((m) => [m.id, m])),
    [data.materials],
  )
  const materialNmc = useMemo(() => {
    const map = new Map()
    for (const rec of data.nmc) {
      for (const id of rec.local_material_ids) map.set(id, rec.nmc)
    }
    return map
  }, [data.nmc])

  const value = {
    ...data,
    loading,
    error,
    toasts,
    runStep,
    busy,
    reload,
    toast,
    runMatching,
    decide,
    addMaterial,
    byMaterial,
    materialNmc,
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
