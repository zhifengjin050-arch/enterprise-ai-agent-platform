import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react"
import { getMe, login as apiLogin } from "@/lib/api"
import { clearSession, getAccessToken, getStoredUser, setSession, type AuthUser } from "@/lib/auth"

interface AuthState {
  user: AuthUser | null
  ready: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(getStoredUser())
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const token = getAccessToken()
    if (!token) {
      setReady(true)
      return
    }
    getMe()
      .then((profile) => {
        setUser(profile)
        setSession(token, profile)
      })
      .catch(() => {
        clearSession()
        setUser(null)
      })
      .finally(() => setReady(true))
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const result = await apiLogin(username, password)
    setSession(result.access_token, result.user)
    setUser(result.user)
  }, [])

  const logout = useCallback(() => {
    clearSession()
    setUser(null)
    window.location.assign("/login")
  }, [])

  const value = useMemo(() => ({ user, ready, login, logout }), [user, ready, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used within AuthProvider")
  return ctx
}
