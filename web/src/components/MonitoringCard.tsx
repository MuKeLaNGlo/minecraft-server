import { useMonitoringWs } from '../hooks/useMonitoring'

function MetricBar({ label, value, max, unit, color }: {
  label: string; value: number; max: number; unit: string; color: string
}) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <span className="text-hint text-xs font-medium">{label}</span>
        <span className="text-xs font-mono font-semibold">
          {value}{unit}
          {max !== 100 && <span className="text-hint font-normal"> / {max}{unit}</span>}
        </span>
      </div>
      <div className="progress-track">
        <div className={`progress-fill ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function tpsColor(tps: number | null | undefined): string {
  if (tps == null) return 'text-gray-400'
  if (tps >= 18) return 'text-[var(--color-success)]'
  if (tps >= 15) return 'text-[var(--color-warning)]'
  return 'text-[var(--color-danger)]'
}

export function MonitoringCard() {
  const { data, connected } = useMonitoringWs()

  if (!data || !data.running) {
    return (
      <div className="card">
        <div className="flex items-center gap-2.5 mb-2">
          <h2 className="text-base font-bold tracking-tight">Мониторинг</h2>
          <div className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-[var(--color-success)]' : 'bg-[var(--color-danger)]'}`} />
        </div>
        <p className="text-hint text-sm">
          {!connected ? 'Подключение...' : 'Сервер оффлайн'}
        </p>
      </div>
    )
  }

  const memPct = data.memory_limit_mb
    ? Math.round((data.memory_mb! / data.memory_limit_mb) * 100)
    : 0

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <h2 className="text-base font-bold tracking-tight">Мониторинг</h2>
          <div className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-[var(--color-success)]' : 'bg-[var(--color-danger)]'}`} />
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className={`text-lg font-bold font-mono leading-none ${tpsColor(data.tps)}`}>
              {data.tps ?? '—'}
            </div>
            <div className="text-[10px] text-hint mt-0.5">TPS</div>
          </div>
          <div className="text-right">
            <div className="text-lg font-bold font-mono leading-none">{data.players_online ?? 0}</div>
            <div className="text-[10px] text-hint mt-0.5">Игроков</div>
          </div>
        </div>
      </div>

      <div className="space-y-3">
        <MetricBar
          label="TPS"
          value={data.tps ?? 0}
          max={20}
          unit=""
          color="bg-[var(--color-success)]"
        />
        <MetricBar
          label="RAM"
          value={data.memory_mb ?? 0}
          max={data.memory_limit_mb ?? 1}
          unit=" МБ"
          color={memPct > 85 ? 'bg-[var(--color-danger)]' : memPct > 70 ? 'bg-[var(--color-warning)]' : 'bg-[var(--color-info)]'}
        />
        <MetricBar
          label="CPU"
          value={data.cpu_percent ?? 0}
          max={100}
          unit="%"
          color={data.cpu_percent! > 80 ? 'bg-[var(--color-danger)]' : 'bg-[var(--color-purple)]'}
        />
      </div>
    </div>
  )
}
