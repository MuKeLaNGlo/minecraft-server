import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { endpoints } from '../api/endpoints'
import { useAuthStore } from '../stores/authStore'

function formatUptime(startedAt: string): string {
  if (!startedAt) return ''
  const start = new Date(startedAt)
  const now = new Date()
  const diff = Math.floor((now.getTime() - start.getTime()) / 1000)
  const hours = Math.floor(diff / 3600)
  const mins = Math.floor((diff % 3600) / 60)
  if (hours > 0) return `${hours}ч ${mins}м`
  return `${mins}м`
}

export function ServerStatus() {
  const role = useAuthStore((s) => s.role)
  const isAdmin = role === 'admin' || role === 'super_admin'
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['serverStatus'],
    queryFn: endpoints.serverStatus,
    refetchInterval: 10000,
  })

  const startMut = useMutation({
    mutationFn: endpoints.serverStart,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['serverStatus'] }),
  })
  const stopMut = useMutation({
    mutationFn: endpoints.serverStop,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['serverStatus'] }),
  })
  const restartMut = useMutation({
    mutationFn: endpoints.serverRestart,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['serverStatus'] }),
  })

  const acting = startMut.isPending || stopMut.isPending || restartMut.isPending

  if (isLoading) return <div className="skeleton h-36" />

  const running = data?.running ?? false

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <div className={`w-2.5 h-2.5 rounded-full ${running ? 'bg-[var(--color-success)]' : 'bg-[var(--color-danger)]'}`}
            style={running ? { boxShadow: '0 0 8px rgba(52, 211, 153, 0.5)' } : undefined}
          />
          <h2 className="text-base font-bold tracking-tight">Сервер</h2>
        </div>
        <span className={`badge ${running ? 'badge-green' : 'badge-red'}`}>
          {running ? 'Онлайн' : 'Оффлайн'}
        </span>
      </div>

      {running && data && (
        <div className="grid grid-cols-2 gap-x-4 gap-y-3 mb-4">
          {data.tps !== undefined && (
            <div>
              <div className="text-hint text-xs mb-0.5">TPS</div>
              <div className={`text-lg font-bold font-mono ${
                data.tps >= 18 ? 'text-[var(--color-success)]' : data.tps >= 15 ? 'text-[var(--color-warning)]' : 'text-[var(--color-danger)]'
              }`}>{data.tps}</div>
            </div>
          )}
          <div>
            <div className="text-hint text-xs mb-0.5">Игроки</div>
            <div className="text-lg font-bold font-mono">
              {data.players?.count ?? 0}<span className="text-hint font-normal text-sm">/{data.players?.max ?? 0}</span>
            </div>
          </div>
          <div>
            <div className="text-hint text-xs mb-0.5">RAM</div>
            <div className="text-sm font-mono font-medium">{data.memory_mb} МБ</div>
          </div>
          <div>
            <div className="text-hint text-xs mb-0.5">CPU</div>
            <div className="text-sm font-mono font-medium">{data.cpu_percent}%</div>
          </div>
          {data.started_at && (
            <div className="col-span-2">
              <div className="text-hint text-xs mb-0.5">Аптайм</div>
              <div className="text-sm font-mono font-medium">{formatUptime(data.started_at)}</div>
            </div>
          )}
        </div>
      )}

      {isAdmin && (
        <div className="flex gap-2">
          {!running ? (
            <button className="btn btn-green flex-1" onClick={() => startMut.mutate()} disabled={acting}>
              Запустить
            </button>
          ) : (
            <>
              <button className="btn btn-yellow flex-1" onClick={() => restartMut.mutate()} disabled={acting}>
                Рестарт
              </button>
              <button className="btn btn-red flex-1" onClick={() => stopMut.mutate()} disabled={acting}>
                Стоп
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
