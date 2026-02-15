import { useEffect, useState } from 'react'
import { useAuthStore } from '../stores/authStore'
import { endpoints } from '../api/endpoints'

export function useAuth() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const token = useAuthStore((s) => s.token)
  const setAuth = useAuthStore((s) => s.setAuth)

  useEffect(() => {
    if (token) {
      setLoading(false)
      return
    }

    async function authenticate() {
      try {
        // Get initData from Telegram WebApp
        const tg = (window as any).Telegram?.WebApp
        const initData = tg?.initData

        if (!initData) {
          setError('Not running inside Telegram')
          setLoading(false)
          return
        }

        const res = await endpoints.auth(initData)
        setAuth(res.token, res.role, res.telegram_id, res.first_name)
      } catch (e: any) {
        setError(e.message || 'Auth failed')
      } finally {
        setLoading(false)
      }
    }

    authenticate()
  }, [token, setAuth])

  return { loading, error, authenticated: !!token }
}
