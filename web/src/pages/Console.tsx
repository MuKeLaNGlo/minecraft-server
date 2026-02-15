import { useState, useRef, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { endpoints } from '../api/endpoints'
import { useAuthStore } from '../stores/authStore'

interface LogEntry {
  type: 'command' | 'response' | 'error'
  text: string
  time: string
}

function timeStr() {
  const d = new Date()
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
}

export function Console() {
  const [input, setInput] = useState('')
  const [history, setHistory] = useState<LogEntry[]>([])
  const [cmdHistory, setCmdHistory] = useState<string[]>([])
  const [histIdx, setHistIdx] = useState(-1)
  const logRef = useRef<HTMLDivElement>(null)
  const role = useAuthStore((s) => s.role)

  const execMut = useMutation({
    mutationFn: (cmd: string) => endpoints.consoleExecute(cmd),
    onSuccess: (data) => {
      if (data.success) {
        setHistory((h) => [...h, { type: 'response', text: data.response || '(пусто)', time: timeStr() }])
      } else {
        setHistory((h) => [...h, { type: 'error', text: data.error || 'Ошибка', time: timeStr() }])
      }
    },
    onError: (err: Error) => {
      setHistory((h) => [...h, { type: 'error', text: err.message, time: timeStr() }])
    },
  })

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: 'smooth' })
  }, [history])

  function submit() {
    const cmd = input.trim()
    if (!cmd) return
    setHistory((h) => [...h, { type: 'command', text: cmd, time: timeStr() }])
    setCmdHistory((h) => [cmd, ...h.filter((c) => c !== cmd)].slice(0, 50))
    setHistIdx(-1)
    setInput('')
    execMut.mutate(cmd)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') {
      e.preventDefault()
      submit()
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (cmdHistory.length > 0) {
        const next = Math.min(histIdx + 1, cmdHistory.length - 1)
        setHistIdx(next)
        setInput(cmdHistory[next])
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (histIdx > 0) {
        const next = histIdx - 1
        setHistIdx(next)
        setInput(cmdHistory[next])
      } else {
        setHistIdx(-1)
        setInput('')
      }
    }
  }

  if (!role || role === 'public') {
    return <p className="text-hint text-sm text-center py-8">Нет доступа</p>
  }

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - env(safe-area-inset-top, 0px) - 120px)' }}>
      {/* Log area */}
      <div
        ref={logRef}
        className="flex-1 overflow-y-auto bg-black/20 border border-white/4 rounded-xl p-3 font-mono text-xs space-y-1"
      >
        {history.length === 0 && (
          <p className="text-hint">RCON-консоль. Введите команду ниже.</p>
        )}
        {history.map((entry, i) => (
          <div key={i}>
            <span className="text-hint/50 mr-2 text-[10px]">[{entry.time}]</span>
            {entry.type === 'command' && (
              <span className="text-[var(--color-info)]">{'> '}{entry.text}</span>
            )}
            {entry.type === 'response' && (
              <span className="text-[var(--color-success)] whitespace-pre-wrap">{entry.text}</span>
            )}
            {entry.type === 'error' && (
              <span className="text-[var(--color-danger)]">{entry.text}</span>
            )}
          </div>
        ))}
        {execMut.isPending && (
          <div className="text-hint" style={{ animation: 'pulse-soft 1.5s ease-in-out infinite' }}>
            Выполнение...
          </div>
        )}
      </div>

      {/* Input */}
      <div className="flex gap-2 mt-3">
        <input
          className="input flex-1 font-mono text-sm"
          placeholder="Введите команду..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
        />
        <button
          className="btn btn-primary px-4"
          onClick={submit}
          disabled={execMut.isPending || !input.trim()}
        >
          ▶
        </button>
      </div>
    </div>
  )
}
