import { useEffect, useRef, useState } from 'react'
import { useAuthStore } from '../stores/authStore'
import type { MonitoringData } from '../api/endpoints'

export function useMonitoringWs() {
  const [data, setData] = useState<MonitoringData | null>(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const token = useAuthStore((s) => s.token)

  useEffect(() => {
    if (!token) return

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${proto}//${host}/ws/monitoring`

    function connect() {
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        setTimeout(connect, 3000)
      }
      ws.onerror = () => ws.close()
      ws.onmessage = (e) => {
        try {
          setData(JSON.parse(e.data))
        } catch {}
      }
    }

    connect()

    return () => {
      wsRef.current?.close()
    }
  }, [token])

  return { data, connected }
}
