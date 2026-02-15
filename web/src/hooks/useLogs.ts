import { useEffect, useRef, useState, useCallback } from 'react'
import { useAuthStore } from '../stores/authStore'

const MAX_LINES = 3000

export function useLogsWs() {
  const [lines, setLines] = useState<string[]>([])
  const [connected, setConnected] = useState(false)
  const [paused, setPaused] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const pausedRef = useRef(false)
  const token = useAuthStore((s) => s.token)

  const clear = useCallback(() => setLines([]), [])

  // Keep ref in sync so WS callback sees latest value
  pausedRef.current = paused

  useEffect(() => {
    if (!token) return

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${proto}//${host}/ws/logs`
    let destroyed = false

    function connect() {
      if (destroyed) return
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        if (!destroyed) setTimeout(connect, 3000)
      }
      ws.onerror = () => ws.close()
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          if (msg.type === 'initial') {
            setLines(msg.lines.slice(-MAX_LINES))
          } else if (msg.type === 'new') {
            // When paused, silently drop new lines
            if (pausedRef.current) return
            setLines((prev) => {
              const combined = [...prev, ...msg.lines]
              return combined.length > MAX_LINES
                ? combined.slice(-MAX_LINES)
                : combined
            })
          }
        } catch {}
      }
    }

    connect()

    return () => {
      destroyed = true
      wsRef.current?.close()
    }
  }, [token])

  const togglePause = useCallback(() => {
    setPaused((p) => !p)
  }, [])

  return { lines, connected, paused, clear, togglePause }
}
