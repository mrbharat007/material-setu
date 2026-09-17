import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, getToken, onAuthChange, setToken } from './api.js'
import { go } from './hooks.js'

const Ctx = createContext(null)
export const useAuth = () => useContext(Ctx)

export const ROLE_LABEL = {
  steward: 'Steward',
  admin: 'Administrator',
}

/** Steward and admin can act on the review queue and ingest materials. */
export const canReview = (user) => !!user && (user.role === 'steward' || user.role === 'admin')

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)

  // Restore a session from a stored token on first load.
  useEffect(() => {
    if (!getToken()) {
      setReady(true)
      return
    }
    let alive = true
    api.me()
      .then((u) => { if (alive) setUser(u) })
      .catch(() => { if (alive) setToken(null) })
      .finally(() => { if (alive) setReady(true) })
    return () => { alive = false }
  }, [])

  // A 401 anywhere (expired/invalid token) clears the token — drop the session.
  useEffect(() => onAuthChange((tok) => { if (!tok) setUser(null) }), [])

  const finish = useCallback((res) => {
    setToken(res.access_token)
    setUser(res.user)
    return res.user
  }, [])

  const login = useCallback(
    (email, password) => api.login({ email, password }).then(finish),
    [finish],
  )

  const register = useCallback(
    (payload) => api.register(payload).then(finish),
    [finish],
  )

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
    go('/login')
  }, [])

  return (
    <Ctx.Provider value={{ user, ready, login, register, logout }}>
      {children}
    </Ctx.Provider>
  )
}
