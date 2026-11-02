import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { authApi, getToken, setToken } from '../lib/api'
import type { TokenResponse, User } from '../lib/types'

interface AuthContextValue {
  user: User | null
  loading: boolean
  isAdmin: boolean
  isStaff: boolean
  login: (phone: string, password: string) => Promise<void>
  loginByPhone: (phoneToken: string) => Promise<void>
  register: (data: { phone_token: string; password: string; full_name: string; email?: string; consent_personal_data: boolean }) => Promise<void>
  logout: () => void
  setSession: (data: TokenResponse) => void
  reload: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const setSession = useCallback((data: TokenResponse) => {
    setToken(data.access_token)
    setUser(data.user)
  }, [])

  const reload = useCallback(async () => {
    if (!getToken()) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      const me = await authApi.me()
      setUser(me)
    } catch {
      setToken(null)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  useEffect(() => {
    const onExpired = () => {
      setToken(null)
      setUser(null)
    }
    window.addEventListener('auth:expired', onExpired)
    return () => window.removeEventListener('auth:expired', onExpired)
  }, [])

  const login = useCallback(async (phone: string, password: string) => {
    const data = await authApi.login(phone, password)
    setSession(data)
  }, [setSession])

  const loginByPhone = useCallback(async (phoneToken: string) => {
    const data = await authApi.loginByPhone(phoneToken)
    setSession(data)
  }, [setSession])

  const register = useCallback(
    async (data: { phone_token: string; password: string; full_name: string; email?: string; consent_personal_data: boolean }) => {
      const result = await authApi.register(data)
      setSession(result)
    },
    [setSession],
  )

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      isAdmin: user?.role === 'admin',
      isStaff: user?.role === 'admin' || user?.role === 'seller',
      login,
      loginByPhone,
      register,
      logout,
      setSession,
      reload,
    }),
    [user, loading, login, loginByPhone, register, logout, setSession, reload],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}
