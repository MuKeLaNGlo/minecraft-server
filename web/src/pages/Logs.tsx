import { useRef, useEffect, useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useLogsWs } from '../hooks/useLogs'
import { useAuthStore } from '../stores/authStore'
import { endpoints } from '../api/endpoints'

// Classify log lines for coloring
function lineClass(line: string): string {
  if (/\bERROR\b|\bFATAL\b|\bException\b/i.test(line)) return 'text-[var(--color-danger)]'
  if (/\bWARN\b/i.test(line)) return 'text-[var(--color-warning)]'
  return ''
}

// Extract timestamp prefix for dimming
function splitTimestamp(line: string): [string, string] {
  const m = line.match(/^(\[\d{2}:\d{2}:\d{2}])(.*)/)
  if (m) return [m[1], m[2]]
  return ['', line]
}

function LogLine({ line }: { line: string }) {
  const cls = lineClass(line)
  const [ts, rest] = splitTimestamp(line)
  return (
    <div className={cls || undefined}>
      {ts && <span className="text-hint/40">{ts}</span>}
      {rest}
    </div>
  )
}

export function Logs() {
  const role = useAuthStore((s) => s.role)
  const isAdmin = role === 'admin' || role === 'super_admin'

  const { lines, connected, paused, clear, togglePause } = useLogsWs()
  const containerRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const [newCount, setNewCount] = useState(0)
  const prevLenRef = useRef(0)

  // History: older logs loaded on demand
  const [historyLines, setHistoryLines] = useState<string[]>([])
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const data = await endpoints.logsHistory(2000)
      setHistoryLines(data.lines)
      setHistoryLoaded(true)
    } catch {}
    setHistoryLoading(false)
  }, [])

  // All lines = history + live
  const allLines = historyLoaded ? [...historyLines, ...lines] : lines

  // Track new lines when autoscroll is off
  useEffect(() => {
    if (autoScroll) {
      setNewCount(0)
    } else if (!paused) {
      const added = lines.length - prevLenRef.current
      if (added > 0) setNewCount((c) => c + added)
    }
    prevLenRef.current = lines.length
  }, [lines.length, autoScroll, paused])

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [allLines, autoScroll])

  // Detect scroll position to toggle auto-scroll
  const onScroll = useCallback(() => {
    const el = containerRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
    setAutoScroll(atBottom)
  }, [])

  const scrollToBottom = useCallback(() => {
    const el = containerRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
    setAutoScroll(true)
    setNewCount(0)
  }, [])

  if (!isAdmin) {
    return <p className="text-hint text-sm text-center py-8">Доступ только для админов</p>
  }

  return (
    <div className="relative flex flex-col" style={{ height: 'calc(100vh - env(safe-area-inset-top, 0px) - 120px)' }}>
      {/* Header bar */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${connected ? 'bg-[var(--color-success)]' : 'bg-[var(--color-danger)]'}`}
            style={connected ? { boxShadow: '0 0 6px rgba(52,211,153,0.5)' } : undefined}
          />
          <span className="text-hint text-xs">
            {paused ? 'Пауза' : connected ? 'Live' : 'Нет соединения'}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-hint text-[10px]">{allLines.length}</span>
          <button
            className={`btn text-xs py-1 px-2.5 ${paused ? 'btn-primary' : 'btn-ghost'}`}
            onClick={togglePause}
          >
            {paused ? '▶' : '⏸'}
          </button>
          <button className="btn btn-ghost text-xs py-1 px-2" onClick={clear}>
            Очистить
          </button>
        </div>
      </div>

      {/* Log terminal */}
      <div
        ref={containerRef}
        onScroll={onScroll}
        className="flex-1 overflow-y-auto bg-black/20 border border-white/4 rounded-xl p-3 font-mono text-[11px] leading-[1.6] overscroll-contain"
      >
        {/* Load history button */}
        {!historyLoaded && (
          <div className="text-center pb-3 mb-3 border-b border-white/5">
            <button
              className="btn btn-ghost text-xs py-1.5 px-3"
              onClick={loadHistory}
              disabled={historyLoading}
            >
              {historyLoading ? 'Загрузка...' : '↑ Загрузить старые логи'}
            </button>
          </div>
        )}

        {allLines.length === 0 && (
          <p className="text-hint text-center py-8">Ожидание логов...</p>
        )}
        {allLines.map((line, i) => (
          <LogLine key={i} line={line} />
        ))}
      </div>

      {/* Floating "new lines" badge */}
      {!autoScroll && newCount > 0 && (
        <button
          className="absolute left-1/2 -translate-x-1/2 bottom-2 btn btn-primary text-xs py-1.5 px-3 shadow-lg flex items-center gap-1.5 z-10"
          onClick={scrollToBottom}
        >
          <span>↓</span>
          <span>{newCount} {newCount === 1 ? 'новая строка' : newCount < 5 ? 'новые строки' : 'новых строк'}</span>
        </button>
      )}

      {!autoScroll && newCount === 0 && (
        <button
          className="absolute left-1/2 -translate-x-1/2 bottom-2 btn btn-ghost text-xs py-1.5 px-3 shadow-lg z-10"
          onClick={scrollToBottom}
        >
          ↓ Вниз
        </button>
      )}
    </div>
  )
}
