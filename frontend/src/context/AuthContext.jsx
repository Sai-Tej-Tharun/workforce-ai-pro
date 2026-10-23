import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, tokens } from '../api'

const Ctx = createContext(null)
export const useAuth = () => useContext(Ctx)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(tokens.user)
  const [booting, setBooting] = useState(!!tokens.access)

  const logout = useCallback(() => { tokens.clear(); setUser(null) }, [])

  // Session validation on load + when the token silently expires (interceptor emits wf:logout)
  useEffect(() => {
    window.addEventListener('wf:logout', logout)
    if (tokens.access) {
      api.get('/auth/session')
        .then(({ data }) => { setUser(data.user); tokens.set({ user: data.user }) })
        .catch(() => logout())
        .finally(() => setBooting(false))
    }
    return () => window.removeEventListener('wf:logout', logout)
  }, [logout])

  const login = useCallback(async (email, password) => {
    const body = new URLSearchParams({ username: email, password })
    const { data } = await api.post('/auth/login', body, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
    tokens.set(data)
    setUser(data.user)
    return data.user
  }, [])

  const value = useMemo(() => ({
    user, booting, login, logout,
    is: (...roles) => !!user && roles.includes(user.role),
  }), [user, booting, login, logout])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
